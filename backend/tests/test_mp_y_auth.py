"""
CP-03: Login con campos vacíos → error (no 200)
CP-06: MP API devuelve error → endpoint lo propaga correctamente
GAP-5: Validaciones Pydantic en campos críticos (monto, DNI)
"""

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.auth import create_access_token

_STUB_PASS = "pytest-stub-pw"  # valor sin semántica de credencial real

client = TestClient(app)


def _alumno_header(uid=2):
    t = create_access_token({"sub": "alumno@test.com", "rol": "alumno", "id": uid})
    return {"Authorization": f"Bearer {t}"}


def _admin_header():
    t = create_access_token({"sub": "admin@amicana.com", "rol": "admin", "id": 1})
    return {"Authorization": f"Bearer {t}"}


def _conn_cuota(cuota_row):
    cur = MagicMock()
    cur.fetchone.return_value = cuota_row
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


# ── CP-03: Login con campos vacíos ───────────────────────────────────────────

class TestCP03_LoginCamposVacios:
    """CP-03: POST /login con campos vacíos o faltantes → no devuelve 200."""

    def test_login_sin_username_ni_password(self):
        """Sin campos → FastAPI devuelve 422 (validación de form)."""
        r = client.post("/login", data={})
        assert r.status_code == 422

    def test_login_username_vacio(self):
        """Username vacío → 422."""
        r = client.post("/login", data={"username": "", "password": "cualquiera"})
        assert r.status_code in (400, 422)

    def test_login_password_vacio(self):
        """Password vacío → 422."""
        r = client.post("/login", data={"username": "alguien@test.com", "password": ""})
        assert r.status_code in (400, 422)

    def test_login_solo_username(self):
        """Solo username, sin password → 422."""
        r = client.post("/login", data={"username": "test@test.com"})
        assert r.status_code == 422

    def test_login_solo_password(self):
        """Solo password, sin username → 422."""
        r = client.post("/login", data={"password": _STUB_PASS})
        assert r.status_code == 422


# ── CP-06: MP API error ───────────────────────────────────────────────────────

class TestCP06_MPApiError:
    """CP-06: POST /pagar-cuota/{id} cuando Mercado Pago devuelve error."""

    @staticmethod
    def _cuota(id_=1, alumno_id=2, estado="pendiente"):
        return {"id": id_, "concepto": "Cuota", "monto": 45000,
                "estado": estado, "alumno_id": alumno_id,
                "alumno_email": "alumno@test.com"}

    @patch("app.services.mercadopago_service.crear_pago")
    def test_mp_devuelve_ok_false_propaga_el_resultado(self, mock_mp):
        """MP devuelve {"ok": False, "error": "..."} → endpoint lo retorna tal cual."""
        mock_mp.return_value = {"ok": False, "error": "MP timeout", "status_code": 503}
        with patch("app.routers.pagos.get_connection", return_value=_conn_cuota(self._cuota(1))):
            r = client.post("/pagar-cuota/1", headers=_alumno_header())
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert "error" in body

    @patch("app.services.mercadopago_service.crear_pago")
    def test_mp_credenciales_invalidas(self, mock_mp):
        """Credenciales MP inválidas → el endpoint devuelve el error de MP."""
        mock_mp.return_value = {
            "ok": False,
            "error": "Unauthorized",
            "status_code": 401,
            "detalle": "Invalid access token"
        }
        with patch("app.routers.pagos.get_connection", return_value=_conn_cuota(self._cuota(2))):
            r = client.post("/pagar-cuota/2", headers=_alumno_header())
        body = r.json()
        assert body["ok"] is False

    @patch("app.services.mercadopago_service.crear_pago")
    def test_mp_excepcion_de_red_devuelve_error_amigable(self, mock_mp):
        """Si crear_pago lanza ConnectionError, el endpoint lo captura y devuelve ok:false."""
        mock_mp.side_effect = ConnectionError("No se puede conectar a MP")
        with patch("app.routers.pagos.get_connection", return_value=_conn_cuota(self._cuota(3))):
            r = client.post("/pagar-cuota/3", headers=_alumno_header())
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert "Mercado Pago" in body["error"]

    @patch("app.services.mercadopago_service.crear_pago")
    def test_mp_ok_true_devuelve_preference_id(self, mock_mp):
        """Control: MP exitoso sigue funcionando después de agregar los tests de error."""
        mock_mp.return_value = {
            "ok": True, "preference_id": "PREF_TEST_123",
            "init_point": "https://mp.com/pay/123",
            "sandbox_init_point": "https://sandbox.mp.com/pay/123"
        }
        with patch("app.routers.pagos.get_connection", return_value=_conn_cuota(self._cuota(4))):
            r = client.post("/pagar-cuota/4", headers=_alumno_header())
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert r.json()["preference_id"] == "PREF_TEST_123"

    def test_cuota_inexistente_404(self):
        """Cuota que no existe → 404 antes de llamar a MP."""
        with patch("app.routers.pagos.get_connection", return_value=_conn_cuota(None)):
            r = client.post("/pagar-cuota/9999", headers=_alumno_header())
        assert r.status_code == 404

    def test_cuota_ya_pagada_400(self):
        """Cuota en estado 'pagada' → 400 antes de llamar a MP."""
        with patch("app.routers.pagos.get_connection",
                   return_value=_conn_cuota(self._cuota(5, estado="pagada"))):
            r = client.post("/pagar-cuota/5", headers=_alumno_header())
        assert r.status_code == 400
        assert "pagada" in r.json()["mensaje"].lower()

    def test_sin_token_401(self):
        """Sin token → 401."""
        r = client.post("/pagar-cuota/1")
        assert r.status_code == 401


# ── GAP-5: Validaciones Pydantic ─────────────────────────────────────────────

class TestGAP5_ValidacionesPydantic:
    """Validaciones de campos críticos en los modelos."""

    def test_confirmar_manual_comprobante_vacio_422(self):
        """comprobante vacío → 422 por Field(min_length=1)."""
        r = client.post("/pagos/confirmar-manual",
                        json={"alumno_id": 2, "cuota_id": 1, "comprobante": ""},
                        headers=_alumno_header())
        assert r.status_code == 422

    def test_confirmar_manual_comprobante_valido_pasa_validacion(self):
        """comprobante con contenido válido pasa la validación Pydantic."""
        cuota = {"id": 1, "alumno_id": 2, "estado": "pendiente", "comprobante_manual": None}
        cur = MagicMock(); cur.fetchone.return_value = cuota
        conn = MagicMock(); conn.cursor.return_value = cur
        with patch("app.routers.pagos.get_connection", return_value=conn):
            r = client.post("/pagos/confirmar-manual",
                            json={"alumno_id": 2, "cuota_id": 1, "comprobante": "MP-123456"},
                            headers=_alumno_header())
        assert r.status_code == 200

    def test_crear_usuario_sin_nombre_422(self):
        """Crear usuario sin nombre → 422."""
        r = client.post("/usuarios", json={"email": "x@x.com", "password": _STUB_PASS, "rol": "alumno"})
        assert r.status_code == 422

    def test_crear_usuario_sin_email_422(self):
        """Crear usuario sin email → 422."""
        r = client.post("/usuarios", json={"nombre": "Test", "password": _STUB_PASS, "rol": "alumno"})
        assert r.status_code == 422

    def test_crear_usuario_sin_password_422(self):
        """Crear usuario sin password → 422."""
        r = client.post("/usuarios", json={"nombre": "Test", "email": "x@x.com", "rol": "alumno"})
        assert r.status_code == 422
