"""Tests de doble acceso: contraseña propia para usuarios Google (Tarea 4)."""
import os
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_pytest_only")

from unittest.mock import patch, MagicMock, call

from fastapi.testclient import TestClient
from app.main import app
from app.auth import create_access_token, verify_password

client = TestClient(app)

_PASS_VALID = "abc12345"
_GOOGLE_EMAIL = "usuario.google@gmail.com"


def _header(email=_GOOGLE_EMAIL, rol="alumno", uid=10):
    t = create_access_token({"sub": email, "rol": rol, "id": uid})
    return {"Authorization": f"Bearer {t}"}


def _cur(one=None, rowcount=1):
    c = MagicMock()
    c.fetchone.return_value = one
    c.rowcount = rowcount
    return c


def _conn(cur):
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


class TestSetearPassword:

    def test_usuario_google_sin_password_puede_setear(self):
        """Usuario Google sin pw → POST /perfil/setear-password → 200."""
        row = {"id": 10, "password": None}
        cur = _cur(one=row)
        with patch("app.routers.perfil.get_connection", return_value=_conn(cur)), \
             patch("app.services.auditoria_service.registrar"):
            r = client.post("/perfil/setear-password",
                            json={"password": _PASS_VALID},
                            headers=_header())
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True

    def test_segundo_intento_devuelve_409(self):
        """Segundo intento de setear contraseña → 409."""
        row = {"id": 10, "password": "ya-existe-hash"}
        cur = _cur(one=row)
        with patch("app.routers.perfil.get_connection", return_value=_conn(cur)):
            r = client.post("/perfil/setear-password",
                            json={"password": _PASS_VALID},
                            headers=_header())
        assert r.status_code == 409
        body = r.json()
        assert "contraseña" in body["mensaje"].lower()

    def test_password_debil_devuelve_422(self):
        """Password sin número → 422 antes de llegar a BD."""
        r = client.post("/perfil/setear-password",
                        json={"password": "sololetras"},
                        headers=_header())
        assert r.status_code == 422
        assert r.json()["ok"] is False

    def test_sin_token_devuelve_401(self):
        """Sin JWT → 401."""
        r = client.post("/perfil/setear-password", json={"password": _PASS_VALID})
        assert r.status_code == 401

    def test_hash_guardado_es_bcrypt_valido(self):
        """El hash que se pasa a UPDATE es un hash bcrypt verificable."""
        row = {"id": 10, "password": None}
        cur = _cur(one=row)
        hashes_guardados = []

        def fake_execute(sql, params=None):
            if params and len(params) == 2 and "UPDATE" in sql:
                hashes_guardados.append(params[0])

        cur.execute = fake_execute

        with patch("app.routers.perfil.get_connection", return_value=_conn(cur)), \
             patch("app.services.auditoria_service.registrar"):
            r = client.post("/perfil/setear-password",
                            json={"password": _PASS_VALID},
                            headers=_header())

        assert r.status_code == 200
        assert len(hashes_guardados) == 1
        assert verify_password(_PASS_VALID, hashes_guardados[0])


class TestLoginDualAcceso:

    def test_usuario_google_con_password_puede_hacer_login_local(self):
        """Después de setear contraseña, el login con email+pw funciona (bug 4.8)."""
        user_row = {
            "id": 10,
            "email": _GOOGLE_EMAIL,
            "nombre": "Google User",
            "rol": "alumno",
            "auth_provider": "google",
            "password": None,  # se sobreescribe abajo
        }
        from app.auth import hash_password
        user_row["password"] = hash_password(_PASS_VALID)

        with patch("app.services.auth_service.buscar_usuario_por_email",
                   return_value=user_row), \
             patch("app.services.auditoria_service.registrar"):
            r = client.post("/auth/login", json={
                "email": _GOOGLE_EMAIL,
                "password": _PASS_VALID,
            })

        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body

    def test_usuario_google_sin_password_sigue_bloqueado(self):
        """Usuario Google sin password local → login con email+pw falla."""
        user_row = {
            "id": 10,
            "email": _GOOGLE_EMAIL,
            "nombre": "Google User",
            "rol": "alumno",
            "auth_provider": "google",
            "password": None,
        }
        with patch("app.services.auth_service.buscar_usuario_por_email",
                   return_value=user_row), \
             patch("app.services.auditoria_service.registrar"):
            r = client.post("/auth/login", json={
                "email": _GOOGLE_EMAIL,
                "password": "cualquier-cosa1",
            })

        assert r.status_code in (400, 401)  # "cuenta Google sin password" → no autorizado


class TestPerfilTienePasswordLocal:

    def test_get_perfil_incluye_tiene_password_local(self):
        """GET /perfil devuelve el campo tiene_password_local."""
        perfil_row = {
            "id": 10, "nombre": "Test", "email": _GOOGLE_EMAIL,
            "rol": "alumno", "auth_provider": "google",
            "tiene_password_local": 0,  # MySQL devuelve int
            "dni": None, "telefono": None, "modalidad": None,
            "curso": None, "modalidad_curso": None,
        }
        cur = _cur(one=perfil_row)
        with patch("app.routers.perfil.get_connection", return_value=_conn(cur)):
            r = client.get("/perfil", headers=_header())

        assert r.status_code == 200
        data = r.json()["data"]
        assert "tiene_password_local" in data
        assert data["tiene_password_local"] is False

    def test_get_perfil_tiene_password_local_true_cuando_tiene_hash(self):
        """tiene_password_local es True cuando el usuario tiene password seteado."""
        perfil_row = {
            "id": 10, "nombre": "Test", "email": _GOOGLE_EMAIL,
            "rol": "alumno", "auth_provider": "google",
            "tiene_password_local": 1,  # MySQL devuelve 1 cuando hay hash
            "dni": "12345678", "telefono": "+54 381 000", "modalidad": None,
            "curso": None, "modalidad_curso": None,
        }
        cur = _cur(one=perfil_row)
        with patch("app.routers.perfil.get_connection", return_value=_conn(cur)):
            r = client.get("/perfil", headers=_header())

        assert r.status_code == 200
        data = r.json()["data"]
        assert data["tiene_password_local"] is True
