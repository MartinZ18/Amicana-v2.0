"""
Generador de QR para pagos con alias propio.
No usa MercadoPago - genera QR localmente sin comisiones.
"""

import qrcode
import io
import base64


# Alias de pago configurado
ALIAS_PAGO = "franco.prolongo"


def generar_qr_pago(monto: float, descripcion: str, alias: str = None) -> dict:
    """
    Genera un código QR con datos de transferencia.
    El QR contiene la info necesaria para que el usuario haga la transferencia.
    """
    alias_usar = alias or ALIAS_PAGO

    # Construir contenido del QR
    # Formato: datos de transferencia legibles al escanear
    contenido_qr = (
        f"Transferencia bancaria\n"
        f"Alias: {alias_usar}\n"
        f"Monto: ${monto:.2f}\n"
        f"Concepto: {descripcion}"
    )

    # Generar imagen QR
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(contenido_qr)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#2f3640", back_color="white")

    # Convertir a base64 para enviar al frontend
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return {
        "qr_base64": img_base64,
        "alias": alias_usar,
        "monto": monto,
        "descripcion": descripcion,
        "contenido": contenido_qr
    }
