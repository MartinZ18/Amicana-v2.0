"""Sesión en cookie httpOnly + CSRF + chequeo de Origin, de punta a punta: uvicorn real + MySQL real.

Google y Mercado Pago se reemplazan por servidores HTTP locales (GOOGLE_API_BASE_URL y
MP_API_BASE_URL). Se omite salvo que SEC_DB_PORT apunte a una BD local descartable cargada
con BD_Amicana.sql (+ migraciones) y SEC_DB_DISPOSABLE=1. Crea y borra datos
`*@amicana-sesion-e2e.com`. uvicorn corre con SESSION_COOKIE_SECURE=0 (http plano).

    SEC_DB_PORT=3357 SEC_DB_DISPOSABLE=1 SEC_DB_PASSWORD=... python -m pytest tests/test_sesion_cookie_e2e.py -v

Escenarios:
  - login (JSON y form legacy) setea amicana_session (HttpOnly, SameSite=Lax) y amicana_csrf
    (legible por JS) y mantiene access_token en el body;
  - con solo la cookie: GET /auth/me anda; un POST sin X-CSRF-Token o con uno ajeno da 403 sin tocar
    la BD; con el token correcto se persiste;
  - Origin ajeno da 403 (también en el login); el propio y los de CORS_ORIGINS pasan; "*" se ignora;
  - Bearer y X-Chatbot-Key no necesitan CSRF (y X-Chatbot-Key gana a una cookie presente);
  - crear un rol staff con la cookie de admin también exige CSRF;
  - el CSRF se deriva (HMAC) de la sesión: un par cookie/header plantado falla; una sesión inválida da 401;
  - logout siempre cierra (aunque falte el CSRF), borra las cookies y repetirlo es idempotente;
  - callback de Google: sin token ni rol en la URL, deja la sesión; state inválido no la deja;
  - el webhook de Mercado Pago sigue andando sin cookie ni CSRF.
"""
import hashlib
import hmac
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import bcrypt
import mysql.connector
import pytest
import requests

SEC_PORT = os.environ.get("SEC_DB_PORT")
SEC_DISPOSABLE = os.environ.get("SEC_DB_DISPOSABLE") == "1"
SEC_HOST = os.environ.get("SEC_DB_HOST", "127.0.0.1")



def _omitir_si_no_hay_bd_descartable():
    if not (SEC_PORT and SEC_DISPOSABLE):
        pytest.skip("SEC_DB_PORT y SEC_DB_DISPOSABLE=1 no definidos: test E2E de sesión omitido")
    if SEC_HOST not in ("127.0.0.1", "localhost"):
        pytest.skip("test E2E de sesión solo contra una BD local descartable")


# Secretos generados en cada corrida: no hay ninguno fijo en el repo.
ADMIN_PASSWORD = secrets.token_hex(8) + "a1"
ALUMNO_PASSWORD = secrets.token_hex(8) + "b2"
CHATBOT_KEY = secrets.token_urlsafe(24)
WEBHOOK_SECRET = secrets.token_hex(16)
DOMINIO = "@amicana-sesion-e2e.com"
MONTO_CUOTA = 15000.00
ORIGEN_AJENO = "https://evil.example"
ORIGEN_CORS = "http://localhost:5173"


def _db():
    return mysql.connector.connect(
        host=SEC_HOST, port=int(SEC_PORT or 0),
        user=os.environ.get("SEC_DB_USER", "root"),
        password=os.environ.get("SEC_DB_PASSWORD", ""),
        database=os.environ.get("SEC_DB_NAME", "gestion_facturas_amicana"),
    )


def _limpiar():
    conn = _db()
    cur = conn.cursor()
    cur.execute("DELETE FROM pagos_mp WHERE concepto LIKE 'e2e-sesion%'")
    cur.execute("DELETE FROM chat_sessions WHERE session_id LIKE 'sesion-e2e-%'")
    cur.execute(f"DELETE FROM usuarios WHERE email LIKE '%{DOMINIO}'")  # cascada a cuotas
    conn.commit()
    conn.close()


def _puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _ServidorFalso:
    """Hace de Google (POST /token, GET /userinfo) y de Mercado Pago (GET /v1/payments/<id>)."""

    def __init__(self, google_user):
        self.google_user = google_user
        self.pagos = {}
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                if urlparse(self.path).path == "/token":
                    self.rfile.read(int(self.headers.get("Content-Length", 0)))
                    return self._responder(200, {"access_token": "token-falso-de-google"})
                return self._responder(404, {})

            def do_GET(self):
                path = urlparse(self.path).path
                if path == "/userinfo":
                    return self._responder(200, fake.google_user)
                if path.startswith("/v1/payments/"):
                    pago = fake.pagos.get(path.rsplit("/", 1)[1])
                    return self._responder(200, pago) if pago else self._responder(404, {})
                return self._responder(404, {})

            def _responder(self, codigo, cuerpo):
                datos = json.dumps(cuerpo).encode()
                self.send_response(codigo)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(datos)))
                self.end_headers()
                self.wfile.write(datos)

            def log_message(self, *args):
                pass

        self.port = _puerto_libre()
        self.httpd = HTTPServer(("127.0.0.1", self.port), Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def cerrar(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def externos():
    _omitir_si_no_hay_bd_descartable()
    falso = _ServidorFalso({
        "id": "g-" + secrets.token_hex(6),
        "email": f"google{secrets.token_hex(4)}{DOMINIO}",
        "name": "Gabi Google",
    })
    yield falso
    falso.cerrar()


@pytest.fixture
def server(externos):
    _limpiar()
    conn = _db()
    cur = conn.cursor()
    hashed = bcrypt.hashpw(ADMIN_PASSWORD.encode(), bcrypt.gensalt()).decode()
    cur.execute("SELECT id FROM usuarios WHERE email = 'admin@amicana.com'")
    if cur.fetchone():
        cur.execute("UPDATE usuarios SET password = %s WHERE email = 'admin@amicana.com'", (hashed,))
    else:
        cur.execute("INSERT INTO usuarios (nombre, email, password, rol) "
                    "VALUES ('Administrador', 'admin@amicana.com', %s, 'admin')", (hashed,))
    conn.commit()
    conn.close()

    port = _puerto_libre()
    base = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "DB_HOST": SEC_HOST, "DB_PORT": str(SEC_PORT),
        "DB_USER": os.environ.get("SEC_DB_USER", "root"),
        "DB_PASSWORD": os.environ.get("SEC_DB_PASSWORD", ""),
        "DB_NAME": os.environ.get("SEC_DB_NAME", "gestion_facturas_amicana"),
        "SECRET_KEY": secrets.token_urlsafe(32),
        "CHATBOT_INTERNAL_KEY": CHATBOT_KEY,
        "MP_ACCESS_TOKEN": secrets.token_urlsafe(24),
        "MP_WEBHOOK_SECRET": WEBHOOK_SECRET,
        "MP_API_BASE_URL": f"http://127.0.0.1:{externos.port}",
        "GOOGLE_API_BASE_URL": f"http://127.0.0.1:{externos.port}",
        "GOOGLE_CLIENT_ID": "cliente-e2e",
        "GOOGLE_CLIENT_SECRET": secrets.token_urlsafe(16),
        "GOOGLE_REDIRECT_URI": f"{base}/auth/google/callback",
        "GOOGLE_POST_LOGIN_REDIRECT": f"{base}/app/index.html",
        "SESSION_COOKIE_SECURE": "0",
        "AUTH_RATE_LIMIT": "1000",
        # El "*" tiene que ignorarse: con credenciales no puede ser un origen válido.
        "CORS_ORIGINS": "*,HTTP://LocalHost:5173/",
    }
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=backend_dir, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        try:
            if requests.get(base + "/Prueba", timeout=1).status_code == 200:
                break
        except requests.ConnectionError:
            time.sleep(0.5)
    else:
        proc.kill()
        pytest.fail("uvicorn no arrancó")
    yield base
    proc.terminate()
    proc.wait(timeout=10)
    _limpiar()


# ── helpers ────────────────────────────────────────────────────────────────

def _alumno():
    conn = _db()
    cur = conn.cursor()
    email = f"alumno{secrets.token_hex(4)}{DOMINIO}"
    hashed = bcrypt.hashpw(ALUMNO_PASSWORD.encode(), bcrypt.gensalt()).decode()
    cur.execute("INSERT INTO usuarios (nombre, apellido, email, password, rol) "
                "VALUES ('Ana', 'Sesion', %s, %s, 'alumno')", (email, hashed))
    alumno_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": alumno_id, "email": email}


def _cuota(alumno_id):
    conn = _db()
    cur = conn.cursor()
    cur.execute("INSERT INTO cuotas (alumno_id, concepto, monto, fecha_vencimiento, estado) "
                "VALUES (%s, 'e2e-sesion cuota', %s, '2099-01-10', 'pendiente')", (alumno_id, MONTO_CUOTA))
    cuota_id = cur.lastrowid
    conn.commit()
    conn.close()
    return cuota_id


def _estado_cuota(cuota_id):
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT estado FROM cuotas WHERE id = %s", (cuota_id,))
    estado = cur.fetchone()[0]
    conn.close()
    return estado


def _cookies_seteadas(resp):
    """Set-Cookie de la respuesta -> {nombre: {"valor": ..., "attrs": {atributo_en_minusculas: valor}}}."""
    resultado = {}
    for linea in resp.raw.headers.getlist("Set-Cookie"):
        partes = [p.strip() for p in linea.split(";")]
        nombre, _, valor = partes[0].partition("=")
        attrs = {}
        for p in partes[1:]:
            k, _, v = p.partition("=")
            attrs[k.lower()] = v
        resultado[nombre] = {"valor": valor, "attrs": attrs}
    return resultado


def _login(base, email, password, **kw):
    """Sesión de `requests` que, como un navegador, guarda las cookies del login."""
    s = requests.Session()
    r = s.post(base + "/auth/login", json={"email": email, "password": password}, **kw)
    return s, r


def _login_alumno(base):
    alumno = _alumno()
    s, r = _login(base, alumno["email"], ALUMNO_PASSWORD)
    assert r.status_code == 200, r.text
    return s, alumno, r


def _confirmar(s, base, alumno_id, cuota_id, headers=None):
    return s.post(base + "/pagos/confirmar-manual", headers=headers or {},
                  json={"alumno_id": alumno_id, "cuota_id": cuota_id, "comprobante": "comprobante e2e"})


# ── 1. login ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ruta", ["/auth/login", "/login"])
def test_login_setea_las_cookies_con_sus_flags(server, ruta):
    alumno = _alumno()
    if ruta == "/auth/login":
        r = requests.post(server + ruta, json={"email": alumno["email"], "password": ALUMNO_PASSWORD})
    else:
        r = requests.post(server + ruta, data={"username": alumno["email"], "password": ALUMNO_PASSWORD})
    assert r.status_code == 200, r.text
    # El body no cambia: los clientes de API siguen recibiendo el token.
    assert r.json()["access_token"]

    cookies = _cookies_seteadas(r)
    sesion, csrf = cookies["amicana_session"], cookies["amicana_csrf"]
    assert "httponly" in sesion["attrs"]
    assert sesion["attrs"]["samesite"].lower() == "lax"
    assert sesion["attrs"]["path"] == "/"
    assert 3590 <= int(sesion["attrs"]["max-age"]) <= 3600
    assert "secure" not in sesion["attrs"]  # SESSION_COOKIE_SECURE=0 en este servidor
    assert sesion["valor"] == r.json()["access_token"]

    assert "httponly" not in csrf["attrs"]  # tiene que poder leerla el JS
    assert csrf["attrs"]["samesite"].lower() == "lax"
    assert csrf["attrs"]["path"] == "/"
    assert int(csrf["attrs"]["max-age"]) == int(sesion["attrs"]["max-age"])
    assert len(csrf["valor"]) >= 32 and csrf["valor"] != sesion["valor"]


def test_login_fallido_no_setea_cookies(server):
    alumno = _alumno()
    r = requests.post(server + "/auth/login", json={"email": alumno["email"], "password": "incorrecta1"})
    assert r.status_code == 400
    assert _cookies_seteadas(r) == {}


# ── 2. cookie + CSRF ───────────────────────────────────────────────────────

def test_con_la_cookie_me_funciona_y_el_post_exige_csrf(server):
    s, alumno, login = _login_alumno(server)

    me = s.get(server + "/auth/me")
    assert me.status_code == 200, me.text
    cuerpo = me.json()
    assert (cuerpo["id"], cuerpo["email"], cuerpo["nombre"], cuerpo["rol"]) == \
        (alumno["id"], alumno["email"], "Ana", "alumno")

    csrf = s.cookies["amicana_csrf"]
    cuota = _cuota(alumno["id"])

    # Sin header: 403 y la cuota no cambia.
    r = _confirmar(s, server, alumno["id"], cuota)
    assert r.status_code == 403, r.text
    assert _estado_cuota(cuota) == "pendiente"

    # Header que no es el de la cookie: 403 y la cuota no cambia.
    r = _confirmar(s, server, alumno["id"], cuota, {"X-CSRF-Token": csrf[::-1]})
    assert r.status_code == 403, r.text
    r = _confirmar(s, server, alumno["id"], cuota, {"X-CSRF-Token": csrf + "x"})
    assert r.status_code == 403, r.text
    assert _estado_cuota(cuota) == "pendiente"

    # Con el token correcto el cambio se persiste.
    r = _confirmar(s, server, alumno["id"], cuota, {"X-CSRF-Token": csrf})
    assert r.status_code == 200, r.text
    assert _estado_cuota(cuota) == "pendiente_verificacion"


def test_csrf_de_otra_sesion_no_sirve(server):
    # Token válido de la sesión de otro usuario, mandado como header con la cookie propia.
    s1, alumno1, _ = _login_alumno(server)
    s2, _, _ = _login_alumno(server)
    cuota = _cuota(alumno1["id"])
    r = _confirmar(s1, server, alumno1["id"], cuota, {"X-CSRF-Token": s2.cookies["amicana_csrf"]})
    assert r.status_code == 403, r.text
    assert _estado_cuota(cuota) == "pendiente"


def test_csrf_plantado_por_el_atacante_no_sirve(server):
    # Par cookie/header elegido por el atacante: el token válido se deriva de la sesión,
    # no de lo que diga la cookie amicana_csrf.
    s, alumno, _ = _login_alumno(server)
    cuota = _cuota(alumno["id"])
    s.cookies.set("amicana_csrf", "attacker", path="/")
    r = _confirmar(s, server, alumno["id"], cuota, {"X-CSRF-Token": "attacker"})
    assert r.status_code == 403, r.text
    assert _estado_cuota(cuota) == "pendiente"


def test_sesion_invalida_en_un_post_da_401_y_no_403(server):
    s, alumno, _ = _login_alumno(server)
    cuota = _cuota(alumno["id"])
    s.cookies.set("amicana_session", "no.es.un-jwt-de-este-servidor", path="/")
    r = _confirmar(s, server, alumno["id"], cuota)
    assert r.status_code == 401, r.text
    assert _estado_cuota(cuota) == "pendiente"


def test_las_lecturas_con_cookie_no_piden_csrf(server):
    s, _, _ = _login_alumno(server)
    assert s.get(server + "/perfil").status_code == 200


# ── 3. Origin ──────────────────────────────────────────────────────────────

def test_origin_ajeno_da_403_aunque_el_csrf_sea_valido(server):
    s, alumno, _ = _login_alumno(server)
    csrf = s.cookies["amicana_csrf"]
    cuota = _cuota(alumno["id"])

    r = _confirmar(s, server, alumno["id"], cuota, {"X-CSRF-Token": csrf, "Origin": ORIGEN_AJENO})
    assert r.status_code == 403, r.text
    assert _estado_cuota(cuota) == "pendiente"

    # "null" (iframe sandbox, file://) tampoco es un origen conocido.
    r = _confirmar(s, server, alumno["id"], cuota, {"X-CSRF-Token": csrf, "Origin": "null"})
    assert r.status_code == 403, r.text
    assert _estado_cuota(cuota) == "pendiente"

    # El propio origen y uno de CORS_ORIGINS pasan.
    r = _confirmar(s, server, alumno["id"], cuota, {"X-CSRF-Token": csrf, "Origin": server})
    assert r.status_code == 200, r.text
    assert _estado_cuota(cuota) == "pendiente_verificacion"
    for origen in (ORIGEN_CORS, "HTTP://LOCALHOST:5173"):
        cuota2 = _cuota(alumno["id"])
        r = _confirmar(s, server, alumno["id"], cuota2, {"X-CSRF-Token": csrf, "Origin": origen})
        assert r.status_code == 200, (origen, r.text)
        assert _estado_cuota(cuota2) == "pendiente_verificacion"


def test_login_con_origin_ajeno_no_deja_sesion(server):
    alumno = _alumno()
    s, r = _login(server, alumno["email"], ALUMNO_PASSWORD, headers={"Origin": ORIGEN_AJENO})
    assert r.status_code == 403, r.text
    assert _cookies_seteadas(r) == {}
    assert s.get(server + "/auth/me").status_code == 401

    # Mismo login desde un origen permitido.
    s, r = _login(server, alumno["email"], ALUMNO_PASSWORD, headers={"Origin": server})
    assert r.status_code == 200, r.text
    assert s.get(server + "/auth/me").status_code == 200


def test_cors_ignora_el_asterisco_y_permite_la_lista(server):
    pre = lambda origen: requests.options(
        server + "/auth/me",
        headers={"Origin": origen, "Access-Control-Request-Method": "GET"})
    ajeno = pre(ORIGEN_AJENO)
    assert ajeno.headers.get("access-control-allow-origin") is None
    propio = pre(ORIGEN_CORS)
    assert propio.headers.get("access-control-allow-origin") == ORIGEN_CORS
    assert propio.headers.get("access-control-allow-credentials") == "true"


# ── 4. Bearer y chatbot ────────────────────────────────────────────────────

def test_bearer_no_necesita_csrf(server):
    alumno = _alumno()
    r = requests.post(server + "/auth/login", json={"email": alumno["email"], "password": ALUMNO_PASSWORD})
    bearer = {"Authorization": f"Bearer {r.json()['access_token']}"}
    cuota = _cuota(alumno["id"])
    r = _confirmar(requests, server, alumno["id"], cuota, bearer)
    assert r.status_code == 200, r.text
    assert _estado_cuota(cuota) == "pendiente_verificacion"


def test_bearer_invalido_no_cae_a_la_cookie(server):
    s, alumno, _ = _login_alumno(server)
    r = s.get(server + "/auth/me", headers={"Authorization": "Bearer basura"})
    assert r.status_code == 401


def test_chatbot_key_no_necesita_csrf_y_gana_a_la_cookie(server):
    body = {"session_id": f"sesion-e2e-{secrets.token_hex(4)}", "estado": "sin_autenticar"}
    r = requests.post(server + "/chatbot/session", json=body, headers={"X-Chatbot-Key": CHATBOT_KEY})
    assert r.status_code == 200 and r.json() == {"ok": True}, r.text

    # Con una cookie de alumno presente y sin CSRF: manda la clave del chatbot, no la cookie.
    s, _, _ = _login_alumno(server)
    body["session_id"] = f"sesion-e2e-{secrets.token_hex(4)}"
    r = s.post(server + "/chatbot/session", json=body, headers={"X-Chatbot-Key": CHATBOT_KEY})
    assert r.status_code == 200 and r.json() == {"ok": True}, r.text

    # Clave equivocada y sin cookie: no autenticado.
    r = requests.post(server + "/chatbot/session", json=body, headers={"X-Chatbot-Key": "otra"})
    assert r.status_code == 401


def test_crear_staff_con_la_cookie_de_admin_exige_csrf(server):
    s, r = _login(server, "admin@amicana.com", ADMIN_PASSWORD)
    assert r.status_code == 200, r.text
    csrf = s.cookies["amicana_csrf"]
    nuevo = lambda: {"nombre": "Staff Sesion", "email": f"staff{secrets.token_hex(4)}{DOMINIO}",
                     "password": secrets.token_hex(6) + "c3", "rol": "administrativo"}

    sin_sesion = requests.post(server + "/auth/register", json=nuevo())
    assert sin_sesion.status_code == 403, sin_sesion.text

    datos = nuevo()
    r = s.post(server + "/auth/register", json=datos)
    assert r.status_code == 403, r.text
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM usuarios WHERE email = %s", (datos["email"],))
    assert cur.fetchone()[0] == 0
    conn.close()

    r = s.post(server + "/auth/register", json=datos, headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200, r.text
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT rol FROM usuarios WHERE email = %s", (datos["email"],))
    assert cur.fetchone()[0] == "administrativo"
    conn.close()

    # El registro público de un alumno no depende de ninguna cookie.
    publico = {**nuevo(), "rol": "alumno"}
    assert requests.post(server + "/auth/register", json=publico).status_code == 200


# ── 6. logout ──────────────────────────────────────────────────────────────

def test_logout_siempre_cierra_la_sesion_y_es_idempotente(server):
    s, _, _ = _login_alumno(server)

    # Sin CSRF (cookie borrada del cliente y sin header): igual cierra, un logout forzado es inofensivo.
    del s.cookies["amicana_csrf"]
    r = s.post(server + "/auth/logout")
    assert r.status_code in (200, 204), r.text
    cookies = _cookies_seteadas(r)
    for nombre in ("amicana_session", "amicana_csrf"):
        assert cookies[nombre]["valor"] in ("", '""')
        assert cookies[nombre]["attrs"]["max-age"] == "0"
        assert cookies[nombre]["attrs"]["path"] == "/"
    assert "amicana_session" not in s.cookies
    assert s.get(server + "/auth/me").status_code == 401

    # Sin sesión también responde bien y limpia.
    r = s.post(server + "/auth/logout")
    assert r.status_code in (200, 204), r.text
    assert cookies.keys() == _cookies_seteadas(r).keys()


def test_logout_con_csrf_incorrecto_cierra_igual_pero_no_con_origin_ajeno(server):
    s, _, _ = _login_alumno(server)
    r = s.post(server + "/auth/logout", headers={"X-CSRF-Token": "equivocado", "Origin": ORIGEN_AJENO})
    assert r.status_code == 403, r.text
    assert s.get(server + "/auth/me").status_code == 200  # el Origin ajeno sí lo frena el middleware

    r = s.post(server + "/auth/logout", headers={"X-CSRF-Token": "equivocado"})
    assert r.status_code in (200, 204), r.text
    assert s.get(server + "/auth/me").status_code == 401


# ── 7. Google ──────────────────────────────────────────────────────────────

def test_callback_de_google_deja_la_sesion_sin_token_en_la_url(server, externos):
    s = requests.Session()
    r = s.get(server + "/auth/google/login", allow_redirects=False)
    assert r.status_code == 302
    state = s.cookies["amicana_google_state"]
    estado = _cookies_seteadas(r)["amicana_google_state"]["attrs"]
    assert "httponly" in estado and estado["samesite"].lower() == "lax" and estado["path"] == "/"
    assert "secure" not in estado  # SESSION_COOKIE_SECURE=0 en este servidor

    r = s.get(server + "/auth/google/callback", params={"code": "codigo-falso", "state": state},
              allow_redirects=False)
    assert r.status_code in (302, 307), r.text
    destino = urlparse(r.headers["Location"])
    assert f"{destino.scheme}://{destino.netloc}{destino.path}" == f"{server}/app/index.html"
    assert parse_qs(destino.query) == {}
    assert destino.fragment == ""

    cookies = _cookies_seteadas(r)
    sesion = cookies["amicana_session"]
    assert "httponly" in sesion["attrs"] and sesion["attrs"]["samesite"].lower() == "lax"
    assert sesion["valor"] not in r.headers["Location"]
    assert "amicana_csrf" in cookies and "httponly" not in cookies["amicana_csrf"]["attrs"]

    me = s.get(server + "/auth/me")
    assert me.status_code == 200, me.text
    assert me.json()["email"] == externos.google_user["email"]
    assert me.json()["rol"] == "alumno"
    assert me.json()["auth_provider"] == "google"


def test_callback_de_google_con_state_invalido_no_deja_sesion(server):
    s = requests.Session()
    s.get(server + "/auth/google/login", allow_redirects=False)
    r = s.get(server + "/auth/google/callback", params={"code": "codigo-falso", "state": "otro"},
              allow_redirects=False)
    assert r.status_code == 400, r.text
    assert "amicana_session" not in _cookies_seteadas(r)
    assert s.get(server + "/auth/me").status_code == 401


# ── 8. webhook de Mercado Pago ─────────────────────────────────────────────

def test_webhook_de_mp_sigue_andando_sin_cookie_ni_csrf(server, externos):
    alumno = _alumno()
    cuota = _cuota(alumno["id"])
    conn = _db()
    cur = conn.cursor()
    cur.execute("INSERT INTO pagos_mp (preference_id, concepto, monto, estado, external_reference) "
                "VALUES (%s, 'e2e-sesion cuota', %s, 'pendiente', %s)",
                (f"pref-{secrets.token_hex(4)}", MONTO_CUOTA, f"CUOTA_{cuota}"))
    conn.commit()
    conn.close()

    payment_id = str(secrets.randbelow(10**9) + 10**9)
    externos.pagos[payment_id] = {
        "id": int(payment_id), "status": "approved", "transaction_amount": MONTO_CUOTA,
        "currency_id": "ARS", "external_reference": f"CUOTA_{cuota}",
        "payment_method_id": "visa", "payer": {"email": f"pagador{DOMINIO}"},
    }
    request_id = secrets.token_hex(8)
    ts = str(int(time.time() * 1000))
    plantilla = f"id:{payment_id};request-id:{request_id};ts:{ts};"
    v1 = hmac.new(WEBHOOK_SECRET.encode(), plantilla.encode(), hashlib.sha256).hexdigest()
    r = requests.post(server + "/pagos/webhook", params={"type": "payment", "data.id": payment_id},
                      headers={"x-signature": f"ts={ts},v1={v1}", "x-request-id": request_id})
    assert r.status_code == 200 and r.json().get("ok") is True, r.text
    assert _estado_cuota(cuota) == "pagada"


# ── cookie Secure por defecto (sin servidor) ───────────────────────────────

def test_la_cookie_es_secure_salvo_que_se_desactive_a_proposito(monkeypatch):
    from starlette.responses import Response

    from app.utils import sesion

    def set_cookie_de(secure_env):
        if secure_env is None:
            monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
        else:
            monkeypatch.setenv("SESSION_COOKIE_SECURE", secure_env)
        resp = Response()
        sesion.set_session_cookies(resp, "jwt-de-prueba")
        return [v.decode().lower() for k, v in resp.raw_headers if k == b"set-cookie"]

    for valor in (None, "1", "", "true"):
        lineas = set_cookie_de(valor)
        assert len(lineas) == 2 and all("secure" in linea.split("; ") for linea in lineas), (valor, lineas)
    assert not any("secure" in linea.split("; ") for linea in set_cookie_de("0"))

