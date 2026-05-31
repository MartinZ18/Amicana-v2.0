import os
from app.services.pdf_service import generar_factura_pdf, FACTURAS_DIR


class TestPdfService:

    def test_genera_archivo(self):
        path = generar_factura_pdf(
            nombre="Juan Pérez",
            email="juan@mail.com",
            dni="35000001",
            curso="Inglés B1",
            concepto="Cuota Mayo 2026",
            monto=45000.0,
            vencimiento="31/05/2026",
            orden_id="MP-001234",
        )
        assert path.startswith("/static/facturas/")
        assert path.endswith(".pdf")

    def test_archivo_existe_en_disco(self):
        path = generar_factura_pdf(
            nombre="Ana García",
            email="ana@mail.com",
            dni=None,
            curso=None,
            concepto="Cuota Junio 2026",
            monto=45000.0,
            vencimiento="30/06/2026",
        )
        filename = path.split("/")[-1]
        full_path = os.path.join(FACTURAS_DIR, filename)
        assert os.path.isfile(full_path)
        assert os.path.getsize(full_path) > 0

    def test_sin_dni_ni_curso_no_falla(self):
        path = generar_factura_pdf(
            nombre="Pedro López",
            email="pedro@mail.com",
            dni=None,
            curso=None,
            concepto="Cuota Julio 2026",
            monto=50000.0,
            vencimiento="31/07/2026",
        )
        assert path.endswith(".pdf")

    def test_cada_llamada_genera_archivo_unico(self):
        p1 = generar_factura_pdf("A", "a@a.com", None, None, "Cuota", 1000, "01/01/2026")
        p2 = generar_factura_pdf("B", "b@b.com", None, None, "Cuota", 1000, "01/01/2026")
        assert p1 != p2
