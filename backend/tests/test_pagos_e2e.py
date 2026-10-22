"""Monto y moneda de los pagos de Mercado Pago, de punta a punta: uvicorn real + MySQL real.

Mercado Pago se reemplaza por un servidor HTTP local (MP_API_BASE_URL) que
responde con el pago que cada caso necesita. Se omite salvo que SEC_DB_PORT
apunte a una BD local descartable cargada con BD_Amicana.sql (+ migraciones) y
SEC_DB_DISPOSABLE=1. El test crea y borra datos `*@amicana-pagos-e2e.com`.

    SEC_DB_PORT=3337 SEC_DB_DISPOSABLE=1 SEC_DB_PASSWORD=... python -m pytest tests/test_pagos_e2e.py -v

Escenarios:
  - webhook con pago aprobado por menos que la cuota: no se marca pagada,
    queda pendiente_verificacion; con el monto exacto (o de más) se marca pagada;
  - reintentos del webhook: no duplican filas ni degradan una cuota ya pagada;
  - moneda distinta a la de la preferencia: no se marca pagada;
  - verificar-pago (por preference_id) aplica la misma regla.
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

pytestmark = [
    pytest.mark.skipif(
        not (SEC_PORT and SEC_DISPOSABLE),
        reason="SEC_DB_PORT y SEC_DB_DISPOSABLE=1 no definidos: test E2E de pagos omitido",
    ),
    pytest.mark.skipif(
        SEC_HOST not in ("127.0.0.1", "localhost"),
        reason="test E2E de pagos solo contra una BD local descartable",
    ),
]

# Secretos generados en cada corrida: no hay ninguno fijo en el repo.
WEBHOOK_SECRET = secrets.token_hex(16)
ADMIN_PASSWORD = secrets.token_hex(8) + "a1"
DOMINIO = "@amicana-pagos-e2e.com"
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
    cur.execute("DELETE FROM pagos_mp WHERE external_reference LIKE 'CUOTA_%' AND concepto LIKE 'e2e-pagos%'")
    cur.execute(f"DELETE FROM usuarios WHERE email LIKE '%{DOMINIO}'")  # cascada a cuotas
    conn.commit()
    conn.close()


def _puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _MercadoPagoFalso:
    """Sirve GET /v1/payments/<id> y /v1/payments/search?preference_id=<id>."""

    def __init__(self):
        self.pagos = {}  # payment_id (str) -> JSON del pago
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                url = urlparse(self.path)
                if url.path == "/v1/payments/search":
                    pref = parse_qs(url.query).get("preference_id", [""])[0]
                    cuerpo = {"results": [p for p in fake.pagos.values() if p.get("_preference_id") == pref]}
                    return self._responder(200, cuerpo)
                if url.path.startswith("/v1/payments/"):
                    pago = fake.pagos.get(url.path.rsplit("/", 1)[1])
                    return self._responder(200, pago) if pago else self._responder(404, {"message": "not found"})
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

    def pago(self, payment_id, cuota_id, monto, moneda="ARS", status="approved", preference_id=""):
        self.pagos[str(payment_id)] = {
            "id": int(payment_id), "status": status, "transaction_amount": monto,
            "currency_id": moneda, "external_reference": f"CUOTA_{cuota_id}",
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
        "CHATBOT_INTERNAL_KEY": secrets.token_urlsafe(24),
        "MP_ACCESS_TOKEN": secrets.token_urlsafe(24),
        "MP_WEBHOOK_SECRET": WEBHOOK_SECRET,
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


def _nueva_cuota(preference_id=None):
    """Alumno + cuota pendiente + fila de pagos_mp como las deja /pagar-cuota."""
    conn = _db()
    cur = conn.cursor()
    sufijo = secrets.token_hex(4)
    cur.execute("INSERT INTO usuarios (nombre, apellido, email, rol) VALUES ('Ana', 'Pago', %s, 'alumno')",
                (f"ana{sufijo}{DOMINIO}",))
    alumno_id = cur.lastrowid
    pref = preference_id or f"pref-{sufijo}"
    cur.execute("INSERT INTO cuotas (alumno_id, concepto, monto, fecha_vencimiento, estado, preference_id) "
                "VALUES (%s, 'e2e-pagos cuota', %s, '2099-01-10', 'pendiente', %s)",
                (alumno_id, MONTO_CUOTA, pref))
    cuota_id = cur.lastrowid
    cur.execute("INSERT INTO pagos_mp (preference_id, concepto, monto, estado, external_reference) "
                "VALUES (%s, 'e2e-pagos cuota', %s, 'pendiente', %s)", (pref, MONTO_CUOTA, f"CUOTA_{cuota_id}"))
    conn.commit()
    conn.close()
    return cuota_id, pref


def _estado_cuota(cuota_id):
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT estado FROM cuotas WHERE id = %s", (cuota_id,))
    estado = cur.fetchone()[0]
    conn.close()
    return estado


def _filas_pagos_mp(cuota_id):
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT payment_id, estado FROM pagos_mp WHERE external_reference = %s", (f"CUOTA_{cuota_id}",))
    filas = cur.fetchall()
    conn.close()
    return filas


def _webhook(base, payment_id):
    """POST firmado con el esquema de MP: HMAC-SHA256 de id/request-id/ts."""
    request_id = secrets.token_hex(8)
    ts = str(int(time.time() * 1000))
    plantilla = f"id:{payment_id};request-id:{request_id};ts:{ts};"
    v1 = hmac.new(WEBHOOK_SECRET.encode(), plantilla.encode(), hashlib.sha256).hexdigest()
    return requests.post(
        base + "/pagos/webhook", params={"type": "payment", "data.id": str(payment_id)},
        headers={"x-signature": f"ts={ts},v1={v1}", "x-request-id": request_id},
    )


def _id_pago():
    return secrets.randbelow(10**9) + 10**9


def test_webhook_pago_incompleto_no_marca_pagada_y_el_exacto_si(server, mp):
    cuota_id, _ = _nueva_cuota()
    p_corto, p_justo = _id_pago(), _id_pago()
    mp.pago(p_corto, cuota_id, MONTO_CUOTA - 5000)
    mp.pago(p_justo, cuota_id, MONTO_CUOTA)

    r = _webhook(server, p_corto)
    assert r.status_code == 200 and r.json().get("ok") is True, r.text
    assert _estado_cuota(cuota_id) == "pendiente_verificacion"
    assert _filas_pagos_mp(cuota_id) == [(str(p_corto), "aprobado")]

    # Un reintento del mismo pago incompleto no cambia nada.
    assert _webhook(server, p_corto).status_code == 200
    assert _estado_cuota(cuota_id) == "pendiente_verificacion"
    assert len(_filas_pagos_mp(cuota_id)) == 1

    # El pago correcto posterior sí marca la cuota.
    r = _webhook(server, p_justo)
    assert r.status_code == 200 and r.json().get("ok") is True, r.text
    assert _estado_cuota(cuota_id) == "pagada"
    assert _filas_pagos_mp(cuota_id) == [(str(p_justo), "aprobado")]

    # Reintento del correcto: sin duplicados, sigue pagada.
    r = _webhook(server, p_justo)
    assert r.status_code == 200, r.text
    assert _estado_cuota(cuota_id) == "pagada"
    assert _filas_pagos_mp(cuota_id) == [(str(p_justo), "aprobado")]

    # Reenviar el pago incompleto con la cuota ya pagada no la degrada.
    assert _webhook(server, p_corto).status_code == 200
    assert _estado_cuota(cuota_id) == "pagada"
    assert len(_filas_pagos_mp(cuota_id)) == 1


def test_webhook_sobrepago_marca_pagada(server, mp):
    cuota_id, _ = _nueva_cuota()
    p = _id_pago()
    mp.pago(p, cuota_id, MONTO_CUOTA + 500.50)
    assert _webhook(server, p).status_code == 200
    assert _estado_cuota(cuota_id) == "pagada"
    assert _filas_pagos_mp(cuota_id) == [(str(p), "aprobado")]


def test_webhook_moneda_distinta_no_marca_pagada(server, mp):
    cuota_id, _ = _nueva_cuota()
    p = _id_pago()
    mp.pago(p, cuota_id, MONTO_CUOTA, moneda="USD")
    r = _webhook(server, p)
    assert r.status_code == 200 and r.json().get("ok") is True, r.text
    assert _estado_cuota(cuota_id) == "pendiente_verificacion"
    assert _filas_pagos_mp(cuota_id) == [(str(p), "aprobado")]


def test_webhook_pago_no_aprobado_no_toca_la_cuota(server, mp):
    cuota_id, _ = _nueva_cuota()
    p = _id_pago()
    mp.pago(p, cuota_id, MONTO_CUOTA, status="rejected")
    assert _webhook(server, p).status_code == 200
    assert _estado_cuota(cuota_id) == "pendiente"
    assert _filas_pagos_mp(cuota_id) == [(str(p), "rechazado")]


def test_verificar_pago_por_preference_aplica_la_misma_regla(server, mp):
    cuota_id, pref = _nueva_cuota()
    admin = requests.post(server + "/auth/login", json={"email": "admin@amicana.com", "password": ADMIN_PASSWORD})
    assert admin.status_code == 200, admin.text
    headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}

    p_corto, p_justo = _id_pago(), _id_pago()
    mp.pago(p_corto, cuota_id, MONTO_CUOTA - 1, preference_id=pref)
    r = requests.get(f"{server}/verificar-pago/{pref}", headers=headers)
    assert r.status_code == 200, r.text
    assert _estado_cuota(cuota_id) == "pendiente_verificacion"

    # Con el pago completo la cuota queda pagada; el reintento no la degrada.
    del mp.pagos[str(p_corto)]
    mp.pago(p_justo, cuota_id, MONTO_CUOTA, preference_id=pref)
    for _ in range(2):
        r = requests.get(f"{server}/verificar-pago/{pref}", headers=headers)
        assert r.status_code == 200, r.text
        assert _estado_cuota(cuota_id) == "pagada"

    mp.pago(p_corto, cuota_id, MONTO_CUOTA - 1, preference_id=pref)
    del mp.pagos[str(p_justo)]
    assert requests.get(f"{server}/verificar-pago/{pref}", headers=headers).status_code == 200
    assert _estado_cuota(cuota_id) == "pagada"

    # Moneda distinta con monto correcto, en otra cuota.
    cuota2, pref2 = _nueva_cuota()
    mp.pago(_id_pago(), cuota2, MONTO_CUOTA, moneda="USD", preference_id=pref2)
    assert requests.get(f"{server}/verificar-pago/{pref2}", headers=headers).status_code == 200
    assert _estado_cuota(cuota2) == "pendiente_verificacion"


def test_verificar_pago_con_un_intento_rechazado_y_otro_aprobado_marca_pagada(server, mp):
    # MP devuelve primero el intento rechazado: igual vale el aprobado.
    cuota_id, pref = _nueva_cuota()
    admin = requests.post(server + "/auth/login", json={"email": "admin@amicana.com", "password": ADMIN_PASSWORD})
    headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}
    mp.pago(_id_pago(), cuota_id, MONTO_CUOTA, status="rejected", preference_id=pref)
    mp.pago(_id_pago(), cuota_id, MONTO_CUOTA, preference_id=pref)
    r = requests.get(f"{server}/verificar-pago/{pref}", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "aprobado"
    assert _estado_cuota(cuota_id) == "pagada"


def test_listado_de_pagos_mp_solo_para_staff(server, mp):
    clave = secrets.token_hex(8) + secrets.choice("ABCDEFGH") + str(secrets.randbelow(10))
    email = "alumno" + DOMINIO
    r = requests.post(server + "/auth/register", json={"nombre": "Alumno", "email": email, "password": clave})
    assert r.status_code == 200, r.text
    alumno = requests.post(server + "/auth/login", json={"email": email, "password": clave})
    assert alumno.status_code == 200, alumno.text
    r = requests.get(server + "/pagos", headers={"Authorization": f"Bearer {alumno.json()['access_token']}"})
    assert r.status_code == 403, r.text

    admin = requests.post(server + "/auth/login", json={"email": "admin@amicana.com", "password": ADMIN_PASSWORD})
    r = requests.get(server + "/pagos", headers={"Authorization": f"Bearer {admin.json()['access_token']}"})
    assert r.status_code == 200, r.text
