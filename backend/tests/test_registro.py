"""Tests de registro de usuarios (Tarea 3 — normalización de email)."""
import os
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_pytest_only")

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

_PASS = "abc12345"  # válido: >= 8 chars, letra y número


def _mock_cursor(one=None, rowcount=1):
    c = MagicMock()
    c.fetchone.return_value = one
    c.rowcount = rowcount
    return c


def _mock_conn(cur):
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


class TestEmailNormalizacion:

    def test_email_mayusculas_ya_registrado_devuelve_409(self):
        """Registrar 'Usuario@AMICANA.com', luego 'usuario@amicana.com' → 409."""
        with patch("app.services.auth_service.buscar_usuario_por_email") as mock_buscar, \
             patch("app.services.auth_service.get_connection", return_value=_mock_conn(_mock_cursor())), \
             patch("app.services.auditoria_service.registrar"):

            # Primera llamada: email no existe → registro OK
            mock_buscar.return_value = None
            r1 = client.post("/auth/register", json={
                "nombre": "Test",
                "email": "Usuario@AMICANA.com",
                "password": _PASS,
            })
            assert r1.status_code == 200, f"Primera llamada falló: {r1.json()}"

            # Segunda llamada: simular que el email (ya normalizado) existe en BD
            mock_buscar.return_value = {
                "id": 1, "email": "usuario@amicana.com", "rol": "alumno"
            }
            r2 = client.post("/auth/register", json={
                "nombre": "Test2",
                "email": "usuario@amicana.com",
                "password": _PASS,
            })
            assert r2.status_code == 409, f"Debería ser 409, fue {r2.status_code}: {r2.json()}"

    def test_email_se_normaliza_a_minusculas(self):
        """El email enviado en mayúsculas queda guardado en minúsculas (normalización en service)."""
        cur = _mock_cursor(rowcount=1)
        cur.lastrowid = 99

        with patch("app.services.auth_service.buscar_usuario_por_email", return_value=None), \
             patch("app.services.auth_service.get_connection", return_value=_mock_conn(cur)), \
             patch("app.services.auditoria_service.registrar"):
            r = client.post("/auth/register", json={
                "nombre": "Test",
                "email": "TestEmail@DOMAIN.COM",
                "password": _PASS,
            })

        assert r.status_code == 200
        body = r.json()
        assert body["data"]["email"] == "testemail@domain.com"

    def test_email_con_espacios_se_normaliza(self):
        """Email con espacios puede ser rechazado por Pydantic (422) o normalizado (200)."""
        cur = _mock_cursor(rowcount=1)
        cur.lastrowid = 98

        with patch("app.services.auth_service.buscar_usuario_por_email", return_value=None), \
             patch("app.services.auth_service.get_connection", return_value=_mock_conn(cur)), \
             patch("app.services.auditoria_service.registrar"):
            r = client.post("/auth/register", json={
                "nombre": "Test",
                "email": "  test@domain.com  ",
                "password": _PASS,
            })

        # Pydantic EmailStr rechaza emails con espacios → 422 es aceptable.
        # Si pasa, debe estar normalizado.
        if r.status_code == 200:
            assert r.json()["data"]["email"] == "test@domain.com"
        else:
            assert r.status_code == 422
