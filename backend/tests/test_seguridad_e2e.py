"""Seguridad de acceso, de punta a punta: uvicorn real + MySQL real.

Se omite salvo que SEC_DB_PORT apunte a una BD local descartable cargada con
BD_Amicana.sql (+ migraciones) y SEC_DB_DISPOSABLE=1. El test crea y borra los
usuarios `*@amicana-sec-e2e.com`. Variables: SEC_DB_HOST (default 127.0.0.1), SEC_DB_PORT,
SEC_DB_USER (default root), SEC_DB_PASSWORD, SEC_DB_NAME
(default gestion_facturas_amicana).

    SEC_DB_PORT=3317 SEC_DB_DISPOSABLE=1 SEC_DB_PASSWORD=... python -m pytest tests/test_seguridad_e2e.py -v

Escenarios:
  - un alumno recién registrado (registro público) no puede leer los datos
    personales de otro alumno por /alumnos/buscar; el chatbot y el staff sí;
  - el límite de mensajes del chatbot no se esquiva cambiando el session_id;
  - login y registro cortan los intentos repetidos desde la misma IP.
"""
import os
import secrets
import socket
import string
import subprocess
import sys
import time
import uuid

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
        reason="SEC_DB_PORT y SEC_DB_DISPOSABLE=1 no definidos: test E2E de seguridad omitido",
    ),
    pytest.mark.skipif(
        SEC_HOST not in ("127.0.0.1", "localhost"),
        reason="test E2E de seguridad solo contra una BD local descartable",
    ),
]

# Credenciales generadas en cada corrida: no hay ninguna fija en el repo.
def _clave_aleatoria() -> str:
    # El registro exige al menos una letra y un número.
    return "".join([secrets.token_hex(8), secrets.choice(string.ascii_letters), str(secrets.randbelow(10))])


CHATBOT_KEY = secrets.token_urlsafe(24)
ADMIN_PASSWORD = _clave_aleatoria()
ALUMNO_PASSWORD = _clave_aleatoria()
CHATBOT_LIMIT = 4
AUTH_LIMIT = 5
VICTIMA = {"nombre": "Valeria", "apellido": "Victima", "email": "valeria@amicana-sec-e2e.com",
           "dni": "40111222", "telefono": "3515550001"}


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
    cur.execute("DELETE FROM usuarios WHERE email LIKE '%@amicana-sec-e2e.com'")
    conn.commit()
    conn.close()


def _puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# Un servidor por test: cada uno arranca con los contadores de rate limit en cero.
@pytest.fixture
def server():
    _limpiar()
    conn = _db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (nombre, apellido, email, dni, telefono, rol) "
        "VALUES (%s, %s, %s, %s, %s, 'alumno')",
        (VICTIMA["nombre"], VICTIMA["apellido"], VICTIMA["email"], VICTIMA["dni"], VICTIMA["telefono"]),
    )
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
    env = {
        **os.environ,
        "DB_HOST": SEC_HOST, "DB_PORT": str(SEC_PORT),
        "DB_USER": os.environ.get("SEC_DB_USER", "root"),
        "DB_PASSWORD": os.environ.get("SEC_DB_PASSWORD", ""),
        "DB_NAME": os.environ.get("SEC_DB_NAME", "gestion_facturas_amicana"),
        "SECRET_KEY": secrets.token_urlsafe(32),
        "CHATBOT_INTERNAL_KEY": CHATBOT_KEY,
        "CHATBOT_RATE_LIMIT": str(CHATBOT_LIMIT),
        "AUTH_RATE_LIMIT": str(AUTH_LIMIT),
        # n8n apuntando a un puerto cerrado: el proxy responde con su fallback
        # sin gastar nada, y el límite se evalúa antes de reenviar.
        "N8N_WEBHOOK_URL": f"http://127.0.0.1:{_puerto_libre()}/webhook",
        "N8N_TIMEOUT_SECONDS": "2",
        "TRUST_PROXY_XFF": "1",
    }
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.Popen(
        # Misma configuración de proxy que el Dockerfile (detrás del proxy de Railway).
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port),
         "--no-proxy-headers"],
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


def _login(base, email, password):
    r = requests.post(base + "/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_alumno_registrado_no_lee_datos_de_otro_alumno(server):
    r = requests.post(server + "/auth/register", json={
        "nombre": "Mallory", "email": "mallory@amicana-sec-e2e.com", "password": ALUMNO_PASSWORD})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["rol"] == "alumno"
    atacante = _login(server, "mallory@amicana-sec-e2e.com", ALUMNO_PASSWORD)

    por_dni = requests.get(server + "/alumnos/buscar", params={"dni": VICTIMA["dni"]}, headers=atacante)
    por_email = requests.get(server + "/alumnos/buscar", params={"email": VICTIMA["email"]}, headers=atacante)
    for r in (por_dni, por_email):
        assert r.status_code == 403, r.text
        assert VICTIMA["telefono"] not in r.text and VICTIMA["dni"] not in r.text

    # El chatbot (n8n) y el staff siguen pudiendo buscar.
    chatbot = requests.get(server + "/alumnos/buscar", params={"dni": VICTIMA["dni"]},
                           headers={"X-Chatbot-Key": CHATBOT_KEY})
    assert chatbot.status_code == 200, chatbot.text
    assert chatbot.json()["alumno"]["email"] == VICTIMA["email"]

    admin = _login(server, "admin@amicana.com", ADMIN_PASSWORD)
    staff = requests.get(server + "/alumnos/buscar", params={"email": VICTIMA["email"]}, headers=admin)
    assert staff.status_code == 200, staff.text
    assert staff.json()["alumno"]["dni"] == VICTIMA["dni"]

    sin_sesion = requests.get(server + "/alumnos/buscar", params={"dni": VICTIMA["dni"]})
    assert sin_sesion.status_code == 401


def test_rotar_session_id_no_esquiva_el_limite_del_chatbot(server):
    codigos = []
    for _ in range(CHATBOT_LIMIT + 2):
        r = requests.post(server + "/chatbot", json={
            "session_id": f"sess-{uuid.uuid4().hex}", "message": "hola"})
        codigos.append(r.status_code)
    assert codigos[:CHATBOT_LIMIT] == [200] * CHATBOT_LIMIT, codigos
    assert codigos[CHATBOT_LIMIT:] == [429, 429], codigos

    # Sin session_id tampoco se esquiva.
    assert requests.post(server + "/chatbot", json={"message": "hola"}).status_code == 429


def test_login_corta_la_fuerza_bruta_y_no_bloquea_otros_endpoints(server):
    codigos = []
    for i in range(AUTH_LIMIT + 2):
        r = requests.post(server + "/auth/login", json={
            "email": VICTIMA["email"], "password": f"adivinanza-{i}"})
        codigos.append(r.status_code)
    assert all(c == 400 for c in codigos[:AUTH_LIMIT]), codigos
    assert codigos[AUTH_LIMIT:] == [429, 429], codigos

    # El alias legacy comparte el mismo cupo: no es una puerta trasera.
    legacy = requests.post(server + "/login", data={"username": VICTIMA["email"], "password": "incorrecta"})
    assert legacy.status_code == 429

    # Bloqueado incluso con la contraseña correcta mientras dure la ventana.
    bloqueado = requests.post(server + "/auth/login", json={
        "email": "admin@amicana.com", "password": ADMIN_PASSWORD})
    assert bloqueado.status_code == 429

    # Endpoints que no son de auth siguen respondiendo.
    assert requests.get(server + "/Prueba").status_code == 200


def test_registro_en_masa_se_corta(server):
    codigos = []
    for i in range(AUTH_LIMIT + 1):
        r = requests.post(server + "/auth/register", json={
            "nombre": "Bot", "email": f"bot{i}@amicana-sec-e2e.com", "password": ALUMNO_PASSWORD})
        codigos.append(r.status_code)
    assert codigos == [200] * AUTH_LIMIT + [429], codigos
    legacy = requests.post(server + "/usuarios", json={
        "nombre": "Bot", "email": "bot-legacy@amicana-sec-e2e.com", "password": ALUMNO_PASSWORD})
    assert legacy.status_code == 429

    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM usuarios WHERE email LIKE 'bot%@amicana-sec-e2e.com'")
    assert cur.fetchone()[0] == AUTH_LIMIT
    conn.close()

    # El login es otro cupo: registrarse no bloquea a quien quiere entrar.
    assert requests.post(server + "/auth/login", json={
        "email": "admin@amicana.com", "password": ADMIN_PASSWORD}).status_code == 200


def test_registrarse_con_el_email_del_chatbot_no_da_permisos_de_chatbot(server):
    r = requests.post(server + "/auth/register", json={
        "nombre": "Impostor", "email": "chatbot@amicana.com", "password": ALUMNO_PASSWORD})
    assert r.status_code in (200, 409), r.text
    if r.status_code == 200:
        try:
            impostor = _login(server, "chatbot@amicana.com", ALUMNO_PASSWORD)
            buscar = requests.get(server + "/alumnos/buscar", params={"dni": VICTIMA["dni"]}, headers=impostor)
            assert buscar.status_code == 403, buscar.text
            identificar = requests.post(server + "/chatbot/identificar-alumno",
                                        json={"dni": VICTIMA["dni"]}, headers=impostor)
            assert identificar.status_code == 403, identificar.text
            sesion = requests.post(server + "/chatbot/session", headers=impostor, json={
                "session_id": "sess-secuestrada", "alumno_id": 1, "estado": "autenticado"})
            assert sesion.status_code == 403, sesion.text
        finally:
            conn = _db()
            cur = conn.cursor()
            cur.execute("DELETE FROM usuarios WHERE email = 'chatbot@amicana.com'")
            conn.commit()
            conn.close()


def test_un_x_forwarded_for_inventado_no_esquiva_el_limite(server):
    # Detrás de Railway, el proxy agrega la IP real al final del header; lo que
    # el cliente manda queda a la izquierda. Se simula esa cadena.
    codigos = []
    for i in range(AUTH_LIMIT + 1):
        r = requests.post(server + "/auth/login",
                          json={"email": VICTIMA["email"], "password": f"x-{i}"},
                          headers={"X-Forwarded-For": f"203.0.113.{i}, 198.51.100.7"})
        codigos.append(r.status_code)
    assert codigos[AUTH_LIMIT:] == [429], codigos

    # Otro cliente real (otra IP agregada por el proxy) tiene su propio cupo.
    otro = requests.post(server + "/auth/login",
                         json={"email": "admin@amicana.com", "password": ADMIN_PASSWORD},
                         headers={"X-Forwarded-For": "198.51.100.8"})
    assert otro.status_code == 200, otro.text
