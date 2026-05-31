"""TASK-23: Tests de tolerancia a fallos.
Verifica que el sistema responde con errores amigables cuando
servicios externos (MP) fallan o están caídos.
"""
from unittest.mock import patch, MagicMock
import requests
from fastapi.testclient import TestClient
from app.main import app
from app.auth import create_access_token

client = TestClient(app)


def _auth_header(rol="admin", uid=1, email="admin@amicana.com"):
    t = create_access_token({"sub": email, "rol": rol, "id": uid})
    return {"Authorization": f"Bearer {t}"}


def _cur(one=None, all_=None, rowcount=1):
    c = MagicMock()
    c.fetchone.return_value = one
    c.fetchall.return_value = all_ or []
    c.rowcount = rowcount
    return c


def _conn(cur):
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


# ── Mercado Pago fault tolerance ─────────────────────────────────────────────

class TestMercadoPagoFaultTolerance:

    @staticmethod
    def _cuota(alumno_id=2, estado="pendiente"):
        return {"id": 1, "concepto": "Cuota Mayo", "monto": 10500,
                "estado": estado, "alumno_id": alumno_id,
                "alumno_email": "alumno@test.com"}

    def test_mp_timeout_retorna_error_amigable(self):
        """Si MP no responde (timeout), el endpoint retorna ok=False sin crashear."""
        with patch("app.routers.pagos.get_connection", return_value=_conn(_cur(one=self._cuota()))):
            with patch("app.mercadopago_qr.requests.post",
                       side_effect=requests.exceptions.Timeout("MP timeout")):
                r = client.post("/pagar-cuota/1", headers=_auth_header(rol="alumno", uid=2))
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is False
        assert "error" in data

    def test_mp_connection_error_retorna_error_amigable(self):
        """Si MP no es alcanzable, el endpoint retorna ok=False sin crashear."""
        with patch("app.routers.pagos.get_connection", return_value=_conn(_cur(one=self._cuota()))):
            with patch("app.mercadopago_qr.requests.post",
                       side_effect=requests.exceptions.ConnectionError("no route")):
                r = client.post("/pagar-cuota/1", headers=_auth_header(rol="alumno", uid=2))
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is False

    def test_mp_error_500_retorna_error_amigable(self):
        """Si MP devuelve 500, el endpoint retorna ok=False con detalle."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"message": "Internal Server Error"}
        with patch("app.routers.pagos.get_connection", return_value=_conn(_cur(one=self._cuota()))):
            with patch("app.mercadopago_qr.requests.post", return_value=mock_resp):
                r = client.post("/pagar-cuota/1", headers=_auth_header(rol="alumno", uid=2))
        assert r.status_code == 200
        assert r.json()["ok"] is False

    def test_verificar_pago_mp_caido_retorna_error(self):
        """Si la verificación de pago falla, retorna error claro."""
        with patch("app.mercadopago_qr.requests.get",
                   side_effect=requests.exceptions.ConnectionError()):
            r = client.get("/verificar-pago/pref-test-123",
                           headers=_auth_header())
        assert r.status_code in (400, 500)

    def test_crear_pago_mp_caido_retorna_400(self):
        """Si crear pago libre falla, retorna 400 con error."""
        with patch("app.mercadopago_qr.requests.post",
                   side_effect=requests.exceptions.ConnectionError()):
            r = client.post("/crear-pago",
                            json={"titulo": "Test", "monto": 1000.0, "cantidad": 1},
                            headers=_auth_header())
        assert r.status_code == 400


# ── DB fault tolerance ────────────────────────────────────────────────────────

class TestDatabaseFaultTolerance:

    def test_listar_pagos_bd_caida_retorna_500(self):
        """Si la BD está caída, /pagos retorna error controlado."""
        with patch("app.mercadopago_qr.get_connection",
                   side_effect=Exception("BD no disponible")):
            r = client.get("/pagos", headers=_auth_header())
        assert r.status_code in (500, 200)
        if r.status_code == 200:
            assert r.json()["ok"] is False
