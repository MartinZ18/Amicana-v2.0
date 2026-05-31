"""Tests de validación de datos (Tarea 2)."""
import os
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_pytest_only")

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.auth import create_access_token

client = TestClient(app)


def _alumno_header(uid=5, email="alumno@test.com"):
    t = create_access_token({"sub": email, "rol": "alumno", "id": uid})
    return {"Authorization": f"Bearer {t}"}


def _mock_cursor(one=None, rowcount=1):
    c = MagicMock()
    c.fetchone.return_value = one
    c.rowcount = rowcount
    return c


def _mock_conn(cur):
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


class TestPasswordValidacion:

    def test_password_sin_numero_devuelve_422(self):
        """Password 'abcdefgh' (sin número) → 422."""
        r = client.post("/auth/register", json={
            "nombre": "Test",
            "email": "test@mail.com",
            "password": "abcdefgh",
        })
        assert r.status_code == 422
        body = r.json()
        assert body["ok"] is False

    def test_password_sin_letra_devuelve_422(self):
        """Password '12345678' (sin letra) → 422."""
        r = client.post("/auth/register", json={
            "nombre": "Test",
            "email": "test@mail.com",
            "password": "12345678",
        })
        assert r.status_code == 422
        body = r.json()
        assert body["ok"] is False

    def test_password_corto_devuelve_422(self):
        """Password de 7 caracteres → 422."""
        r = client.post("/auth/register", json={
            "nombre": "Test",
            "email": "test@mail.com",
            "password": "abc123x",
        })
        assert r.status_code == 422
        body = r.json()
        assert body["ok"] is False

    def test_password_valido_no_falla_en_schema(self):
        """Password válido no lanza 422 por schema (puede fallar por BD, no por validación)."""
        with patch("app.services.auth_service.registrar_usuario", side_effect=ValueError("dup")):
            r = client.post("/auth/register", json={
                "nombre": "Test",
                "email": "test@mail.com",
                "password": "abc12345",
            })
        assert r.status_code != 422


class TestEmailValidacion:

    def test_email_sin_arroba_devuelve_422(self):
        """Email sin @ → 422."""
        r = client.post("/auth/register", json={
            "nombre": "Test",
            "email": "noesvalido",
            "password": "abc12345",
        })
        assert r.status_code == 422
        body = r.json()
        assert body["ok"] is False


class TestDNIValidacion:

    def test_dni_corto_en_completar_perfil_devuelve_422(self):
        """DNI '123' (muy corto) → 422 en /perfil/completar."""
        r = client.put(
            "/perfil/completar",
            json={"dni": "123"},
            headers=_alumno_header(),
        )
        assert r.status_code == 422
        body = r.json()
        assert body["ok"] is False

    def test_dni_valido_en_completar_perfil_pasa_schema(self):
        """DNI '12345678' (8 dígitos) → supera schema y llega a BD (200 con mock)."""
        usuario_row = {
            "id": 5,
            "dni": None,
            "telefono": None,
            "password": None,
        }
        cur = _mock_cursor(one=usuario_row, rowcount=1)
        with patch("app.routers.perfil.get_connection", return_value=_mock_conn(cur)), \
             patch("app.services.auditoria_service.registrar"):
            r = client.put(
                "/perfil/completar",
                json={"dni": "12345678"},
                headers=_alumno_header(),
            )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True

    def test_dni_siete_digitos_valido(self):
        """DNI de 7 dígitos también es válido."""
        usuario_row = {
            "id": 5,
            "dni": None,
            "telefono": None,
            "password": None,
        }
        cur = _mock_cursor(one=usuario_row, rowcount=1)
        with patch("app.routers.perfil.get_connection", return_value=_mock_conn(cur)), \
             patch("app.services.auditoria_service.registrar"):
            r = client.put(
                "/perfil/completar",
                json={"dni": "1234567"},
                headers=_alumno_header(),
            )
        assert r.status_code == 200


class TestPasswordEnCompletarPerfil:

    def test_password_sin_numero_en_completar_perfil_devuelve_422(self):
        """Password 'abcdefgh' en /perfil/completar → 422."""
        r = client.put(
            "/perfil/completar",
            json={"password": "abcdefgh"},
            headers=_alumno_header(),
        )
        assert r.status_code == 422

    def test_password_sin_letra_en_completar_perfil_devuelve_422(self):
        """Password '12345678' en /perfil/completar → 422."""
        r = client.put(
            "/perfil/completar",
            json={"password": "12345678"},
            headers=_alumno_header(),
        )
        assert r.status_code == 422
