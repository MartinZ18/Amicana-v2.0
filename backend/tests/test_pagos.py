from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.auth import create_access_token

_STUB_PASS = "pytest-stub-pw1"  # valor sin semántica de credencial real (con dígito para pasar validación)

client = TestClient(app)

def _header(rol="alumno", uid=2, email="alumno@test.com"):
    t = create_access_token({"sub": email, "rol": rol, "id": uid})
    return {"Authorization": f"Bearer {t}"}

def _admin_header():
    return _header(rol="admin", uid=1, email="admin@amicana.com")

def _cur(one=None, rowcount=1):
    c = MagicMock(); c.fetchone.return_value = one; c.rowcount = rowcount; return c

def _conn(cur):
    conn = MagicMock(); conn.cursor.return_value = cur; return conn


class TestConfirmarManual:

    def test_confirmar_cuota_pendiente(self):
        cuota = {"id": 1, "alumno_id": 2, "estado": "pendiente", "comprobante_manual": None}
        cur = _cur(one=cuota)
        with patch("app.routers.pagos.get_connection", return_value=_conn(cur)):
            r = client.post("/pagos/confirmar-manual",
                            json={"alumno_id": 2, "cuota_id": 1, "comprobante": "MP-123456"},
                            headers=_header())
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert "administrador" in r.json()["mensaje"].lower()

    def test_confirmar_cuota_ya_pagada(self):
        cuota = {"id": 1, "alumno_id": 2, "estado": "pagada", "comprobante_manual": None}
        cur = _cur(one=cuota)
        with patch("app.routers.pagos.get_connection", return_value=_conn(cur)):
            r = client.post("/pagos/confirmar-manual",
                            json={"alumno_id": 2, "cuota_id": 1, "comprobante": "MP-123456"},
                            headers=_header())
        assert r.status_code == 400
        assert "pagada" in r.json()["mensaje"].lower()

    def test_confirmar_cuota_inexistente(self):
        cur = _cur(one=None)
        with patch("app.routers.pagos.get_connection", return_value=_conn(cur)):
            r = client.post("/pagos/confirmar-manual",
                            json={"alumno_id": 2, "cuota_id": 999, "comprobante": "X"},
                            headers=_header())
        assert r.status_code == 404

    def test_sin_token_401(self):
        r = client.post("/pagos/confirmar-manual",
                        json={"alumno_id": 2, "cuota_id": 1, "comprobante": "X"})
        assert r.status_code == 401

    def test_alumno_no_puede_confirmar_cuota_ajena(self):
        """IDOR: alumno con id=99 no puede confirmar cuota de alumno_id=2."""
        token_ajeno = create_access_token({"sub": "otro@test.com", "rol": "alumno", "id": 99})
        header_ajeno = {"Authorization": f"Bearer {token_ajeno}"}
        r = client.post("/pagos/confirmar-manual",
                        json={"alumno_id": 2, "cuota_id": 1, "comprobante": "HACK"},
                        headers=header_ajeno)
        assert r.status_code == 403
        assert "propia" in r.json()["mensaje"].lower()

    def test_admin_puede_confirmar_cualquier_cuota(self):
        """Admin puede confirmar cuota de cualquier alumno."""
        cuota = {"id": 1, "alumno_id": 2, "estado": "pendiente", "comprobante_manual": None}
        cur = _cur(one=cuota)
        with patch("app.routers.pagos.get_connection", return_value=_conn(cur)):
            r = client.post("/pagos/confirmar-manual",
                            json={"alumno_id": 2, "cuota_id": 1, "comprobante": "ADMIN-OK"},
                            headers=_admin_header())
        assert r.status_code == 200

    def test_comprobante_vacio_rechazado(self):
        """comprobante vacío debe ser rechazado por validación Pydantic."""
        r = client.post("/pagos/confirmar-manual",
                        json={"alumno_id": 2, "cuota_id": 1, "comprobante": ""},
                        headers=_header())
        assert r.status_code == 422


class TestGenerarFacturaPdf:

    def test_alumno_puede_generar_su_pdf(self):
        cuota_row = {
            "id": 1, "concepto": "Cuota Mayo 2026", "monto": 45000,
            "fecha_vencimiento": "2026-05-31", "alumno_id": 2,
            "nombre": "Juan Pérez", "email": "juan@mail.com",
            "dni": "35000001", "curso": "Inglés B1"
        }
        cur = _cur(one=cuota_row)
        with patch("app.routers.pagos.get_connection", return_value=_conn(cur)):
            r = client.post("/pagos/generar-factura-pdf",
                            json={"cuota_id": 1},
                            headers=_header(uid=2))
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["pdf_url"].startswith("/static/facturas/")
        assert data["pdf_url"].endswith(".pdf")

    def test_alumno_no_puede_generar_pdf_ajeno(self):
        cuota_row = {
            "id": 1, "concepto": "Cuota Mayo 2026", "monto": 45000,
            "fecha_vencimiento": "2026-05-31", "alumno_id": 2,
            "nombre": "Juan Pérez", "email": "juan@mail.com",
            "dni": "35000001", "curso": "Inglés B1"
        }
        cur = _cur(one=cuota_row)
        with patch("app.routers.pagos.get_connection", return_value=_conn(cur)):
            r = client.post("/pagos/generar-factura-pdf",
                            json={"cuota_id": 1},
                            headers=_header(uid=99))  # uid distinto al alumno_id=2
        assert r.status_code == 403

    def test_admin_puede_generar_pdf_de_cualquier_alumno(self):
        cuota_row = {
            "id": 1, "concepto": "Cuota Mayo 2026", "monto": 45000,
            "fecha_vencimiento": "2026-05-31", "alumno_id": 2,
            "nombre": "Juan Pérez", "email": "juan@mail.com",
            "dni": None, "curso": None
        }
        cur = _cur(one=cuota_row)
        with patch("app.routers.pagos.get_connection", return_value=_conn(cur)):
            r = client.post("/pagos/generar-factura-pdf",
                            json={"cuota_id": 1},
                            headers=_admin_header())
        assert r.status_code == 200

    def test_cuota_inexistente_404(self):
        cur = _cur(one=None)
        with patch("app.routers.pagos.get_connection", return_value=_conn(cur)):
            r = client.post("/pagos/generar-factura-pdf",
                            json={"cuota_id": 999},
                            headers=_header())
        assert r.status_code == 404

    def test_sin_token_401(self):
        r = client.post("/pagos/generar-factura-pdf", json={"cuota_id": 1})
        assert r.status_code == 401


class TestPdfDeduplication:
    """FIX-C3: si la cuota ya tiene pdf_url y existe en disco, se reutiliza."""

    def _cuota_con_pdf(self, pdf_url):
        return {
            "id": 1, "concepto": "Cuota Mayo 2026", "monto": 45000,
            "fecha_vencimiento": "2026-05-31", "alumno_id": 2, "pdf_url": pdf_url,
            "nombre": "Juan Pérez", "email": "juan@mail.com",
            "dni": "35000001", "curso": "Inglés B1",
        }

    def test_pdf_se_reusa_si_archivo_existe(self):
        cur = _cur(one=self._cuota_con_pdf("/static/facturas/cached.pdf"))
        with patch("app.routers.pagos.get_connection", return_value=_conn(cur)), \
             patch("os.path.isfile", return_value=True), \
             patch("app.routers.pagos.generar_factura_pdf") as gen:
            r = client.post("/pagos/generar-factura-pdf",
                            json={"cuota_id": 1}, headers=_header(uid=2))
        assert r.status_code == 200
        body = r.json()
        assert body["pdf_url"] == "/static/facturas/cached.pdf"
        assert body["reused"] is True
        gen.assert_not_called()

    def test_pdf_se_regenera_si_archivo_borrado(self):
        cur = _cur(one=self._cuota_con_pdf("/static/facturas/missing.pdf"))
        with patch("app.routers.pagos.get_connection", return_value=_conn(cur)), \
             patch("os.path.isfile", return_value=False):
            r = client.post("/pagos/generar-factura-pdf",
                            json={"cuota_id": 1}, headers=_header(uid=2))
        assert r.status_code == 200
        body = r.json()
        assert body["reused"] is False
        assert body["pdf_url"].startswith("/static/facturas/")

    def test_pdf_se_genera_si_pdf_url_null(self):
        """Cuota sin pdf_url previo → genera y guarda."""
        cuota = self._cuota_con_pdf(None)
        cur = _cur(one=cuota)
        with patch("app.routers.pagos.get_connection", return_value=_conn(cur)):
            r = client.post("/pagos/generar-factura-pdf",
                            json={"cuota_id": 1}, headers=_header(uid=2))
        assert r.status_code == 200
        assert r.json()["reused"] is False


class TestPagarCuota:
    """FIX-A1: /pagar-cuota/{id} acepta JWT alumno o X-Chatbot-Key."""

    CHATBOT_HEADERS = {"X-Chatbot-Key": "amicana-internal"}

    def _cuota_row(self, alumno_id=2, estado="pendiente"):
        return {
            "id": 1, "concepto": "Cuota Mayo 2026", "monto": 45000,
            "estado": estado, "alumno_id": alumno_id,
            "alumno_email": "alumno@test.com",
        }

    def test_chatbot_puede_pagar_cuota_de_alumno_correcto(self):
        cur = _cur(one=self._cuota_row(alumno_id=2))
        with patch("app.routers.pagos.get_connection", return_value=_conn(cur)), \
             patch("app.services.mercadopago_service.crear_pago",
                   return_value={"ok": True, "preference_id": "PREF-1",
                                 "init_point": "x", "sandbox_init_point": "x",
                                 "titulo": "t", "monto": 45000, "cantidad": 1}):
            r = client.post("/pagar-cuota/1",
                            json={"alumno_id": 2},
                            headers=self.CHATBOT_HEADERS)
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_chatbot_no_puede_pagar_cuota_de_alumno_ajeno(self):
        cur = _cur(one=self._cuota_row(alumno_id=2))
        with patch("app.routers.pagos.get_connection", return_value=_conn(cur)):
            r = client.post("/pagar-cuota/1",
                            json={"alumno_id": 99},
                            headers=self.CHATBOT_HEADERS)
        assert r.status_code == 403

    def test_chatbot_sin_alumno_id_es_403(self):
        cur = _cur(one=self._cuota_row(alumno_id=2))
        with patch("app.routers.pagos.get_connection", return_value=_conn(cur)):
            r = client.post("/pagar-cuota/1", headers=self.CHATBOT_HEADERS)
        assert r.status_code == 403

    def test_alumno_jwt_sigue_funcionando_en_pagar_cuota(self):
        cur = _cur(one=self._cuota_row(alumno_id=2))
        with patch("app.routers.pagos.get_connection", return_value=_conn(cur)), \
             patch("app.services.mercadopago_service.crear_pago",
                   return_value={"ok": True, "preference_id": "PREF-2",
                                 "init_point": "x", "sandbox_init_point": "x",
                                 "titulo": "t", "monto": 45000, "cantidad": 1}):
            r = client.post("/pagar-cuota/1", headers=_header(uid=2))
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_pagar_cuota_pagada_retorna_400(self):
        cur = _cur(one=self._cuota_row(alumno_id=2, estado="pagada"))
        with patch("app.routers.pagos.get_connection", return_value=_conn(cur)):
            r = client.post("/pagar-cuota/1", headers=_header(uid=2))
        assert r.status_code == 400

    def test_pagar_cuota_inexistente_retorna_404(self):
        cur = _cur(one=None)
        with patch("app.routers.pagos.get_connection", return_value=_conn(cur)):
            r = client.post("/pagar-cuota/999", headers=_header(uid=2))
        assert r.status_code == 404

    def test_sin_auth_retorna_401(self):
        r = client.post("/pagar-cuota/1")
        assert r.status_code == 401


class TestCrearUsuario:

    def test_registro_alumno_sin_token(self):
        """Auto-registro público: rol alumno sin token."""
        with patch("app.services.auth_service.get_connection", return_value=_conn(_cur())):
            r = client.post("/usuarios",
                            json={"nombre": "Test", "email": "t@t.com",
                                  "password": _STUB_PASS, "rol": "alumno"})
        assert r.status_code == 200

    def test_crear_admin_sin_token_rechazado(self):
        """Sin token no se puede crear un usuario admin."""
        r = client.post("/usuarios",
                        json={"nombre": "Hack", "email": "h@h.com",
                              "password": _STUB_PASS, "rol": "admin"})
        assert r.status_code == 403

    def test_crear_admin_con_token_admin(self):
        """Con token admin sí se puede crear otro admin."""
        with patch("app.services.auth_service.get_connection", return_value=_conn(_cur())):
            r = client.post("/usuarios",
                            json={"nombre": "Nuevo Admin", "email": "na@a.com",
                                  "password": _STUB_PASS, "rol": "admin"},
                            headers=_admin_header())
        assert r.status_code == 200

    def test_alumno_no_puede_crear_admin(self):
        """Un alumno autenticado no puede crear otro admin."""
        r = client.post("/usuarios",
                        json={"nombre": "Hack", "email": "h@h.com",
                              "password": _STUB_PASS, "rol": "admin"},
                        headers=_header(rol="alumno"))
        assert r.status_code == 403
