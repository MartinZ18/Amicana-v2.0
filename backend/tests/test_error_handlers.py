"""Tests para los exception handlers globales (Tarea 1)."""
import os
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_pytest_only")
os.environ["ENV"] = "test"  # activa /_test_500

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, raise_server_exceptions=False)


class TestValidationErrorHandler:

    def test_campo_invalido_devuelve_ok_false_y_errores(self):
        """422 con campo inválido → ok=false y errores como lista."""
        r = client.post("/auth/register", json={"email": "no-es-email", "password": "12345678", "nombre": "X"})
        assert r.status_code == 422
        body = r.json()
        assert body["ok"] is False
        assert "errores" in body
        assert isinstance(body["errores"], list)
        assert len(body["errores"]) > 0
        assert "campo" in body["errores"][0]
        assert "detalle" in body["errores"][0]

    def test_body_faltante_devuelve_ok_false(self):
        """422 sin body → ok=false."""
        r = client.post("/auth/register", json={})
        assert r.status_code == 422
        body = r.json()
        assert body["ok"] is False
        assert isinstance(body.get("errores"), list)


class TestHTTPExceptionHandler:

    def test_ruta_inexistente_devuelve_ok_false(self):
        """404 en ruta que no existe → ok=false y mensaje legible."""
        r = client.get("/usuarios/no-existe")
        assert r.status_code == 404
        body = r.json()
        assert body["ok"] is False
        assert "mensaje" in body
        assert isinstance(body["mensaje"], str)
        assert len(body["mensaje"]) > 0

    def test_error_negocio_devuelve_ok_false(self):
        """404 generado por raise error() → ok=false y mensaje del negocio."""
        from unittest.mock import patch, MagicMock
        from app.auth import create_access_token
        token = create_access_token({"sub": "admin@amicana.com", "rol": "admin", "id": 1})
        headers = {"Authorization": f"Bearer {token}"}

        cur = MagicMock()
        cur.fetchone.return_value = None
        conn = MagicMock()
        conn.cursor.return_value = cur

        with patch("app.routers.alumnos.get_connection", return_value=conn):
            r = client.get("/alumnos/99999", headers=headers)

        assert r.status_code == 404
        body = r.json()
        assert body["ok"] is False
        assert "mensaje" in body


class TestGenericExceptionHandler:

    def test_excepcion_interna_devuelve_500_sin_traceback(self):
        """Error no capturado → 500, ok=false, sin traceback en el body."""
        r = client.get("/_test_500")
        assert r.status_code == 500
        body = r.json()
        assert body["ok"] is False
        assert body["mensaje"] == "Error interno del servidor"
        body_str = str(body)
        assert "Traceback" not in body_str
        assert "RuntimeError" not in body_str
        assert "deliberado" not in body_str
