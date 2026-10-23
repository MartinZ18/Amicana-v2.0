"""Permisos de datos del chatbot y de pagos, de punta a punta: uvicorn real + MySQL real.

Mercado Pago se reemplaza por un servidor HTTP local (MP_API_BASE_URL). Se omite
salvo que SEC_DB_PORT apunte a una BD local descartable cargada con
BD_Amicana.sql (+ migraciones) y SEC_DB_DISPOSABLE=1. El test crea y borra
datos `*@amicana-permisos-e2e.com`.

    SEC_DB_PORT=3347 SEC_DB_DISPOSABLE=1 SEC_DB_PASSWORD=... python -m pytest tests/test_permisos_e2e.py -v

Escenarios:
  - estado-cuotas / aptitud-examen del chatbot: solo con una sesión del mismo alumno;
  - pagar-cuota: un alumno solo paga cuotas propias; el chatbot necesita sesión del dueño;
  - verificar-pago: un alumno solo consulta preferencias de sus cuotas, sin tocar MP ni la BD;
  - /alumnos/{id}/cuotas con la sesión del alumno (el flujo de n8n) sigue andando.
"""
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

pytestmark = [
    pytest.mark.skipif(
        not (SEC_PORT and SEC_DISPOSABLE),
        reason="SEC_DB_PORT y SEC_DB_DISPOSABLE=1 no definidos: test E2E de permisos omitido",
    ),
    pytest.mark.skipif(
        SEC_HOST not in ("127.0.0.1", "localhost"),
        reason="test E2E de permisos solo contra una BD local descartable",
    ),
]

# Secretos generados en cada corrida: no hay ninguno fijo en el repo.
CHATBOT_KEY = secrets.token_urlsafe(24)
PASSWORD = secrets.token_hex(8) + "a1"
DOMINIO = "@amicana-permisos-e2e.com"
MONTO_CUOTA = 15000.00


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
    cur.execute("DELETE FROM chat_sessions WHERE session_id LIKE 'perm-e2e-%'")
    cur.execute("DELETE FROM pagos_mp WHERE concepto LIKE 'e2e-permisos%'")
    cur.execute(f"DELETE FROM usuarios WHERE email LIKE '%{DOMINIO}'")  # cascada a cuotas
    conn.commit()
    conn.close()


def _puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _MercadoPagoFalso:
    """Sirve POST /checkout/preferences y GET /v1/payments/search?preference_id=<id>."""

    def __init__(self):
        self.pagos = {}  # payment_id (str) -> JSON del pago
        self.consultas = []  # preference_id consultados por la API
        self.preferencias_creadas = 0
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                url = urlparse(self.path)
                if url.path == "/v1/payments/search":
                    pref = parse_qs(url.query).get("preference_id", [""])[0]
                    fake.consultas.append(pref)
                    cuerpo = {"results": [p for p in fake.pagos.values() if p.get("_preference_id") == pref]}
                    return self._responder(200, cuerpo)
                return self._responder(404, {})

            def do_POST(self):
                if urlparse(self.path).path == "/checkout/preferences":
                    self.rfile.read(int(self.headers.get("Content-Length", 0)))
                    fake.preferencias_creadas += 1
                    nueva = f"pref-nueva-{secrets.token_hex(4)}"
                    return self._responder(201, {"id": nueva, "init_point": f"http://127.0.0.1/{nueva}"})
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
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def pago(self, cuota_id, monto, preference_id):
        pid = secrets.randbelow(10**9) + 10**9
        self.pagos[str(pid)] = {
            "id": pid, "status": "approved", "transaction_amount": monto,
            "currency_id": "ARS", "external_reference": f"CUOTA_{cuota_id}",
            "payment_method_id": "visa", "payer": {"email": f"pagador{DOMINIO}"},
            "_preference_id": preference_id,
        }

    def cerrar(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def mp():
    falso = _MercadoPagoFalso()
    yield falso
    falso.cerrar()


@pytest.fixture
def server(mp):
    _limpiar()
    conn = _db()
    cur = conn.cursor()
    hashed = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
    cur.execute("SELECT id FROM usuarios WHERE email = 'admin@amicana.com'")
    if cur.fetchone():
        cur.execute("UPDATE usuarios SET password = %s WHERE email = 'admin@amicana.com'", (hashed,))
    else:
        cur.execute("INSERT INTO usuarios (nombre, email, password, rol) "
                    "VALUES ('Administrador', 'admin@amicana.com', %s, 'admin')", (hashed,))
    conn.commit()
    conn.close()

    port = _puerto_libre()
    env = {
        **os.environ,
        "DB_HOST": SEC_HOST, "DB_PORT": str(SEC_PORT),
        "DB_USER": os.environ.get("SEC_DB_USER", "root"),
        "DB_PASSWORD": os.environ.get("SEC_DB_PASSWORD", ""),
        "DB_NAME": os.environ.get("SEC_DB_NAME", "gestion_facturas_amicana"),
        "SECRET_KEY": secrets.token_urlsafe(32),
        "CHATBOT_INTERNAL_KEY": CHATBOT_KEY,
        "MP_ACCESS_TOKEN": secrets.token_urlsafe(24),
        "MP_WEBHOOK_SECRET": secrets.token_hex(16),
        "MP_API_BASE_URL": f"http://127.0.0.1:{mp.port}",
    }
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=backend_dir, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
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


def _alumno(nombre):
    """Alumno con login + una cuota pendiente + una sesión de chatbot propia (autenticada)."""
    conn = _db()
    cur = conn.cursor()
    sufijo = secrets.token_hex(4)
    email = f"{nombre.lower()}{sufijo}{DOMINIO}"
    hashed = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
    cur.execute("INSERT INTO usuarios (nombre, apellido, email, password, rol) "
                "VALUES (%s, 'Permisos', %s, %s, 'alumno')", (nombre, email, hashed))
    alumno_id = cur.lastrowid
    pref = f"pref-{sufijo}"
    cur.execute("INSERT INTO cuotas (alumno_id, concepto, monto, fecha_vencimiento, estado, preference_id) "
                "VALUES (%s, 'e2e-permisos cuota', %s, '2099-01-10', 'pendiente', %s)",
                (alumno_id, MONTO_CUOTA, pref))
    cuota_id = cur.lastrowid
    cur.execute("INSERT INTO pagos_mp (preference_id, concepto, monto, estado, external_reference) "
                "VALUES (%s, 'e2e-permisos cuota', %s, 'pendiente', %s)", (pref, MONTO_CUOTA, f"CUOTA_{cuota_id}"))
    session_id = f"perm-e2e-{sufijo}"
    cur.execute("INSERT INTO chat_sessions (session_id, alumno_id, estado) VALUES (%s, %s, 'activo')",
                (session_id, alumno_id))
    conn.commit()
    conn.close()
    return {"id": alumno_id, "email": email, "cuota": cuota_id, "pref": pref, "session": session_id}


def _sesion_sin_autenticar():
    conn = _db()
    cur = conn.cursor()
    session_id = f"perm-e2e-anon-{secrets.token_hex(4)}"
    cur.execute("INSERT INTO chat_sessions (session_id, estado) VALUES (%s, 'sin_autenticar')", (session_id,))
    conn.commit()
    conn.close()
    return session_id


def _jwt(server, email):
    r = requests.post(server + "/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _bot(session_id=None):
    h = {"X-Chatbot-Key": CHATBOT_KEY}
    if session_id:
        h["X-Chatbot-Session-Id"] = session_id
    return h


def _cuota(cuota_id):
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT estado, preference_id FROM cuotas WHERE id = %s", (cuota_id,))
    fila = cur.fetchone()
    conn.close()
    return fila


@pytest.mark.parametrize("ruta", ["estado-cuotas", "aptitud-examen"])
def test_datos_del_chatbot_solo_del_alumno_de_la_sesion(server, ruta):
    a, b = _alumno("Ana"), _alumno("Beto")
    anonima = _sesion_sin_autenticar()

    url = lambda alumno: f"{server}/chatbot/alumno/{alumno['id']}/{ruta}"
    # La sesión de A lee lo de A...
    r = requests.get(url(a), headers=_bot(a["session"]))
    assert r.status_code == 200, r.text
    # ...pero no lo de B, ni sin sesión, ni con una sesión sin autenticar, ni con sesión inexistente.
    assert requests.get(url(b), headers=_bot(a["session"])).status_code == 403
    assert requests.get(url(a), headers=_bot()).status_code == 403
    assert requests.get(url(a), headers=_bot(anonima)).status_code == 403
    assert requests.get(url(a), headers=_bot("perm-e2e-no-existe")).status_code == 403
    # Un JWT de alumno (sin ser el chatbot) tampoco entra.
    assert requests.get(url(a), headers=_jwt(server, a["email"])).status_code == 403


def test_pagar_cuota_ajena_no_crea_preferencia_ni_pisa_la_existente(server, mp):
    a, b = _alumno("Ana"), _alumno("Beto")
    antes = _cuota(b["cuota"])
    headers_a = _jwt(server, a["email"])

    r = requests.post(f"{server}/pagar-cuota/{b['cuota']}", headers=headers_a)
    assert r.status_code == 404, r.text
    assert mp.preferencias_creadas == 0
    assert _cuota(b["cuota"]) == antes

    # La propia sigue andando.
    r = requests.post(f"{server}/pagar-cuota/{a['cuota']}", headers=headers_a)
    assert r.status_code == 200 and r.json().get("ok") is True, r.text
    assert mp.preferencias_creadas == 1
    assert _cuota(a["cuota"])[1] == r.json()["preference_id"]

    # Staff puede pagar cualquiera.
    admin = _jwt(server, "admin@amicana.com")
    r = requests.post(f"{server}/pagar-cuota/{b['cuota']}", headers=admin)
    assert r.status_code == 200 and r.json().get("ok") is True, r.text
    assert _cuota(b["cuota"])[1] == r.json()["preference_id"]


def test_pagar_cuota_por_chatbot_exige_sesion_del_dueno(server, mp):
    a, b = _alumno("Ana"), _alumno("Beto")
    antes = _cuota(a["cuota"])

    # Sin sesión: antes pasaba por el bypass de chatbot_alumno_id=None.
    r = requests.post(f"{server}/pagar-cuota/{a['cuota']}", headers=_bot(), json={"alumno_id": a["id"]})
    assert r.status_code == 404, r.text
    # Sesión de otro alumno.
    r = requests.post(f"{server}/pagar-cuota/{a['cuota']}", headers=_bot(b["session"]), json={"alumno_id": a["id"]})
    assert r.status_code == 404, r.text
    assert mp.preferencias_creadas == 0
    assert _cuota(a["cuota"]) == antes

    # Sesión del dueño: igual que siempre.
    r = requests.post(f"{server}/pagar-cuota/{a['cuota']}", headers=_bot(a["session"]), json={"alumno_id": a["id"]})
    assert r.status_code == 200 and r.json().get("ok") is True, r.text
    assert mp.preferencias_creadas == 1
    assert _cuota(a["cuota"])[1] == r.json()["preference_id"]


def test_verificar_pago_solo_de_preferencias_propias(server, mp):
    a, b = _alumno("Ana"), _alumno("Beto")
    # MP ya tiene el pago aprobado de B: si el pedido de A llegara a MP, la cuota de B quedaría pagada.
    mp.pago(b["cuota"], MONTO_CUOTA, b["pref"])
    headers_a = _jwt(server, a["email"])

    ajena = requests.get(f"{server}/verificar-pago/{b['pref']}", headers=headers_a)
    inexistente = requests.get(f"{server}/verificar-pago/pref-no-existe-{secrets.token_hex(4)}", headers=headers_a)
    assert ajena.status_code == 404, ajena.text
    # No se filtra si la preferencia existe: misma respuesta que una inexistente.
    assert (inexistente.status_code, inexistente.json()) == (ajena.status_code, ajena.json())
    assert mp.consultas == []
    assert _cuota(b["cuota"])[0] == "pendiente"

    # Staff verifica cualquiera y aplica el pago.
    admin = _jwt(server, "admin@amicana.com")
    r = requests.get(f"{server}/verificar-pago/{b['pref']}", headers=admin)
    assert r.status_code == 200 and r.json()["estado"] == "aprobado", r.text
    assert _cuota(b["cuota"])[0] == "pagada"

    # El dueño verifica la suya.
    mp.pago(a["cuota"], MONTO_CUOTA, a["pref"])
    r = requests.get(f"{server}/verificar-pago/{a['pref']}", headers=headers_a)
    assert r.status_code == 200 and r.json()["estado"] == "aprobado", r.text
    assert _cuota(a["cuota"])[0] == "pagada"


def test_cuotas_del_alumno_con_su_sesion_de_chatbot(server):
    # El nodo "Estado — Cuotas Alumno" de n8n ahora manda X-Chatbot-Session-Id.
    a, b = _alumno("Ana"), _alumno("Beto")
    r = requests.get(f"{server}/alumnos/{a['id']}/cuotas", headers=_bot(a["session"]))
    assert r.status_code == 200, r.text
    assert requests.get(f"{server}/alumnos/{b['id']}/cuotas", headers=_bot(a["session"])).status_code == 403
    assert requests.get(f"{server}/alumnos/{a['id']}/cuotas", headers=_bot()).status_code == 403
