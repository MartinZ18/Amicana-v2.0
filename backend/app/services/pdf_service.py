import os
import uuid
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

FACTURAS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "static", "facturas")


def _ensure_dir():
    os.makedirs(FACTURAS_DIR, exist_ok=True)


def generar_factura_pdf(
    nombre: str,
    email: str,
    dni: str | None,
    curso: str | None,
    concepto: str,
    monto: float,
    vencimiento: str,
    orden_id: str | None = None,
) -> str:
    """
    Genera un PDF de factura de cuota con ReportLab y lo guarda en static/facturas/.
    Retorna la ruta relativa: /static/facturas/{uuid}.pdf
    """
    _ensure_dir()
    filename = f"{uuid.uuid4()}.pdf"
    filepath = os.path.join(FACTURAS_DIR, filename)

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    dark = colors.HexColor("#2c3e50")
    elements = []

    # Título
    title_style = ParagraphStyle("title", parent=styles["Heading1"],
                                 textColor=dark, alignment=TA_CENTER, fontSize=18)
    elements.append(Paragraph("AMICANA — Comprobante de Cuota", title_style))
    elements.append(Spacer(1, 0.5*cm))

    # Tabla de datos
    fecha_emision = datetime.now().strftime("%d/%m/%Y %H:%M")
    rows = [
        ["Campo", "Valor"],
        ["Nombre", nombre],
        ["Email", email],
    ]
    if dni:
        rows.append(["DNI", dni])
    if curso:
        rows.append(["Curso", curso])
    rows += [
        ["Concepto", concepto],
        ["Vencimiento", vencimiento],
        ["Total", f"${monto:,.2f} ARS"],
        ["Fecha de emisión", fecha_emision],
    ]
    if orden_id:
        rows.append(["Referencia MP", orden_id])

    table = Table(rows, colWidths=[5*cm, 11*cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), dark),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, 0), 11),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("FONTNAME",   (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 1), (-1, -1), 10),
        ("PADDING",    (0, 0), (-1, -1), 8),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 1*cm))

    # Pie de página
    footer_style = ParagraphStyle("footer", parent=styles["Normal"],
                                  fontSize=8, textColor=colors.grey)
    elements.append(Paragraph(
        "Documento no válido como factura fiscal. Solo para control interno de AMICANA.",
        footer_style
    ))

    doc.build(elements)
    return f"/static/facturas/{filename}"
