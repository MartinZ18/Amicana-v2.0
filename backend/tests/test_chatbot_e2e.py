"""TASK-21: Test end-to-end del flujo del chatbot via FastAPI.
Simula exactamente las llamadas que hace n8n usando X-Chatbot-Key.
"""
import os
os.environ.setdefault("CHATBOT_INTERNAL_KEY", "amicana-internal")

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.auth import create_access_token

client = TestClient(app)
CHATBOT_HEADERS = {"X-Chatbot-Key": "amicana-internal"}


def _chatbot_headers_for(alumno_id: int, session_id: str = "sess_test"):
    """Headers que simulan al chatbot con sesión autenticada (FIX-B3).

    Para que get_chatbot_or_current_user resuelva chatbot_alumno_id, el caller
    debe envolver con `with patch('app.auth.ChatSessionRepository') as MockRepo: ...`
    y configurar `MockRepo().get_by_session_id.return_value`.
    """
    return {"X-Chatbot-Key": "amicana-internal", "X-Chatbot-Session-Id": session_id}


def _mock_chatbot_session(alumno_id: int):
    """Devuelve un context manager que mockea ChatSessionRepository para B3."""
    from app.models.chat_session import ChatSession
    fake_session = ChatSession(id=1, session_id="sess_test", alumno_id=alumno_id,
                               estado="autenticado", intentos_auth=0, history=[])
    return patch("app.models.chat_session.ChatSessionRepository.get_by_session_id",
                 return_value=fake_session)


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


class TestChatbotAuthFlow:
    """Paso 1 — n8n autentica al alumno por DNI."""

    def test_chatbot_buscar_alumno_por_dni(self):
        alumno = {
            "id": 5, "nombre": "María García", "email": "maria@mail.com",
            "dni": "35000001", "telefono": "3514000000",
            "curso": "Inglés B1", "monto_cuota": 10500,
        }
        with patch("app.routers.alumnos.get_connection", return_value=_conn(_cur(one=alumno))):
            r = client.get("/alumnos/buscar?dni=35000001", headers=CHATBOT_HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["alumno"]["nombre"] == "María García"

    def test_chatbot_buscar_alumno_por_email(self):
        alumno = {
            "id": 5, "nombre": "María García", "email": "maria@mail.com",
            "dni": "35000001", "telefono": None,
            "curso": "Inglés B1", "monto_cuota": 10500,
        }
        with patch("app.routers.alumnos.get_connection", return_value=_conn(_cur(one=alumno))):
            r = client.get("/alumnos/buscar?email=maria@mail.com", headers=CHATBOT_HEADERS)
        assert r.status_code == 200
        assert r.json()["alumno"]["email"] == "maria@mail.com"

    def test_chatbot_alumno_no_encontrado_retorna_404(self):
        with patch("app.routers.alumnos.get_connection", return_value=_conn(_cur(one=None))):
            r = client.get("/alumnos/buscar?dni=00000000", headers=CHATBOT_HEADERS)
        assert r.status_code == 404

    def test_clave_incorrecta_retorna_401(self):
        r = client.get("/alumnos/buscar?dni=35000001",
                       headers={"X-Chatbot-Key": "clave-incorrecta"})
        assert r.status_code == 401

    def test_sin_auth_retorna_401(self):
        r = client.get("/alumnos/buscar?dni=35000001")
        assert r.status_code == 401


class TestChatbotEstadoFlow:
    """Paso 2 — n8n consulta las cuotas del alumno autenticado."""

    def test_chatbot_cuotas_alumno_con_deuda(self):
        cuota = {
            "id": 1, "concepto": "Cuota Mayo 2026", "monto": 10500,
            "fecha_vencimiento": "2026-05-31", "estado": "pendiente",
        }
        with _mock_chatbot_session(alumno_id=5), \
             patch("app.routers.alumnos.get_connection", return_value=_conn(
                _cur(one={"id": 5}, all_=[cuota])
             )):
            r = client.get("/alumnos/5/cuotas", headers=_chatbot_headers_for(5))
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["resumen"]["estado"] == "Con deuda"
        assert data["resumen"]["cuotas_pendientes"] == 1
        assert data["resumen"]["deuda_total"] == 10500.0

    def test_chatbot_cuotas_alumno_al_dia(self):
        cuota = {
            "id": 2, "concepto": "Cuota Abril 2026", "monto": 10500,
            "fecha_vencimiento": "2026-04-30", "estado": "pagada",
        }
        with _mock_chatbot_session(alumno_id=5), \
             patch("app.routers.alumnos.get_connection", return_value=_conn(
                _cur(one={"id": 5}, all_=[cuota])
             )):
            r = client.get("/alumnos/5/cuotas", headers=_chatbot_headers_for(5))
        assert r.status_code == 200
        data = r.json()
        assert data["resumen"]["estado"] == "Al día"
        assert data["resumen"]["deuda_total"] == 0.0

    def test_chatbot_alumno_inexistente_retorna_404(self):
        with _mock_chatbot_session(alumno_id=999), \
             patch("app.routers.alumnos.get_connection", return_value=_conn(_cur(one=None))):
            r = client.get("/alumnos/999/cuotas", headers=_chatbot_headers_for(999))
        assert r.status_code == 404


class TestChatbotEstadoIDOR:
    """H3: /alumnos/{id}/cuotas debe validar chatbot_alumno_id == alumno_id."""

    def test_sin_session_id_es_403(self):
        r = client.get("/alumnos/5/cuotas", headers=CHATBOT_HEADERS)
        assert r.status_code == 403

    def test_session_de_otro_alumno_es_403(self):
        """sesión autenticada como alumno 7 → no puede ver cuotas del alumno 5."""
        with _mock_chatbot_session(alumno_id=7):
            r = client.get("/alumnos/5/cuotas", headers=_chatbot_headers_for(7))
        assert r.status_code == 403


class TestChatbotConfirmarFlow:
    """Paso 3 — n8n registra una confirmación manual de pago."""

    def test_chatbot_confirmar_pago_cuota_pendiente(self):
        cuota = {"id": 1, "alumno_id": 5, "estado": "pendiente", "comprobante_manual": None}
        with _mock_chatbot_session(alumno_id=5), \
             patch("app.routers.pagos.get_connection", return_value=_conn(_cur(one=cuota))):
            r = client.post(
                "/pagos/confirmar-manual",
                json={"alumno_id": 5, "cuota_id": 1, "comprobante": "MP-987654321"},
                headers=_chatbot_headers_for(5),
            )
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_chatbot_confirmar_cuota_ya_pagada_retorna_400(self):
        cuota = {"id": 1, "alumno_id": 5, "estado": "pagada", "comprobante_manual": None}
        with _mock_chatbot_session(alumno_id=5), \
             patch("app.routers.pagos.get_connection", return_value=_conn(_cur(one=cuota))):
            r = client.post(
                "/pagos/confirmar-manual",
                json={"alumno_id": 5, "cuota_id": 1, "comprobante": "MP-987654321"},
                headers=_chatbot_headers_for(5),
            )
        assert r.status_code == 400

    def test_chatbot_confirmar_cuota_inexistente_retorna_404(self):
        with _mock_chatbot_session(alumno_id=5), \
             patch("app.routers.pagos.get_connection", return_value=_conn(_cur(one=None))):
            r = client.post(
                "/pagos/confirmar-manual",
                json={"alumno_id": 5, "cuota_id": 999, "comprobante": "X"},
                headers=_chatbot_headers_for(5),
            )
        assert r.status_code == 404


class TestChatbotConfirmarSessionGuard:
    """FIX-B3: el chatbot debe demostrar que el alumno_id pasado coincide con la sesión."""

    def test_sin_session_id_es_403(self):
        cuota = {"id": 1, "alumno_id": 5, "estado": "pendiente", "comprobante_manual": None}
        with patch("app.routers.pagos.get_connection", return_value=_conn(_cur(one=cuota))):
            r = client.post(
                "/pagos/confirmar-manual",
                json={"alumno_id": 5, "cuota_id": 1, "comprobante": "X"},
                headers=CHATBOT_HEADERS,
            )
        assert r.status_code == 403

    def test_session_de_otro_alumno_es_403(self):
        """sesión autenticada como alumno 7 → no puede confirmar cuota del alumno 5."""
        cuota = {"id": 1, "alumno_id": 5, "estado": "pendiente", "comprobante_manual": None}
        with _mock_chatbot_session(alumno_id=7), \
             patch("app.routers.pagos.get_connection", return_value=_conn(_cur(one=cuota))):
            r = client.post(
                "/pagos/confirmar-manual",
                json={"alumno_id": 5, "cuota_id": 1, "comprobante": "X"},
                headers=_chatbot_headers_for(7),
            )
        assert r.status_code == 403


class TestChatbotPagarFlow:
    """Paso 4 — n8n genera PDF de comprobante."""

    def test_chatbot_generar_pdf_cuota(self):
        cuota_row = {
            "id": 1, "concepto": "Cuota Mayo 2026", "monto": 10500,
            "fecha_vencimiento": "2026-05-31", "alumno_id": 5,
            "nombre": "María García", "email": "maria@mail.com",
            "dni": "35000001", "curso": "Inglés B1",
        }
        with _mock_chatbot_session(alumno_id=5), \
             patch("app.routers.pagos.get_connection", return_value=_conn(_cur(one=cuota_row))):
            r = client.post(
                "/pagos/generar-factura-pdf",
                json={"cuota_id": 1},
                headers=_chatbot_headers_for(5),
            )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["pdf_url"].startswith("/static/facturas/")

    def test_chatbot_pdf_cuota_inexistente_retorna_404(self):
        with _mock_chatbot_session(alumno_id=5), \
             patch("app.routers.pagos.get_connection", return_value=_conn(_cur(one=None))):
            r = client.post(
                "/pagos/generar-factura-pdf",
                json={"cuota_id": 999},
                headers=_chatbot_headers_for(5),
            )
        assert r.status_code == 404


class TestChatbotPrivilegeBoundaries:
    """FIX-B2: el chatbot NO debe tener privilegios admin."""

    def test_chatbot_no_puede_ver_reportes(self):
        # La API de auditoría se removió; /reportes/resumen es admin-only y
        # sirve igual para verificar que la X-Chatbot-Key no da privilegios staff.
        r = client.get("/reportes/resumen", headers=CHATBOT_HEADERS)
        assert r.status_code in (401, 403)

    def test_chatbot_no_puede_aprobar_pago(self):
        r = client.post("/pagos/aprobar/1", headers=CHATBOT_HEADERS)
        assert r.status_code in (401, 403)

    def test_chatbot_no_puede_listar_pendientes(self):
        r = client.get("/pagos/pendiente-verificacion", headers=CHATBOT_HEADERS)
        assert r.status_code in (401, 403)


class TestChatbotVsJwtInterop:
    """Los endpoints del chatbot también siguen funcionando con JWT normal."""

    def test_jwt_sigue_funcionando_en_buscar(self):
        alumno = {
            "id": 5, "nombre": "Juan", "email": "juan@mail.com",
            "dni": "35000001", "telefono": None,
            "curso": "Inglés A1", "monto_cuota": 8500,
        }
        token = create_access_token({"sub": "admin@amicana.com", "rol": "admin", "id": 1})
        headers = {"Authorization": f"Bearer {token}"}
        with patch("app.routers.alumnos.get_connection", return_value=_conn(_cur(one=alumno))):
            r = client.get("/alumnos/buscar?dni=35000001", headers=headers)
        assert r.status_code == 200
