"""Orquestador de pagos: usa el cliente MP puro y persiste en BD.

El cliente HTTP vive en `services/mercadopago_client.py` (sin BD). Acá se
hace el side-effect de guardar/actualizar la fila en `pagos_mp`. Los tests
pueden mockear `crear_preference` o `buscar_pago_por_preference` sin tocar
la BD.

Mantiene `requests` como atributo del módulo para que tests existentes que
hacen `patch("app.mercadopago_qr.requests.post"/"get")` sigan funcionando.
"""
import uuid
from datetime import datetime

import requests  # re-exportado para retro-compat de mocks  # noqa: F401

from .database import get_connection
from .services import mercadopago_client


def crear_pago(titulo: str, monto: float, cantidad: int = 1,
               email_pagador: str = "", creado_por: str = "",
               external_reference: str = "") -> dict:
    """Crea preference en MP y guarda fila en `pagos_mp`."""
    
    if not external_reference:
        external_reference = f"AMICANA-{uuid.uuid4().hex[:12]}"
        
    resultado = mercadopago_client.crear_preference(
        titulo=titulo, monto=monto, cantidad=cantidad,
        email_pagador=email_pagador, external_reference=external_reference
    )
    if not resultado.get("ok"):
        return resultado

    preference_id = resultado.get("preference_id")
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO pagos_mp
               (preference_id, concepto, monto, cantidad, estado, creado_por, external_reference)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (preference_id, titulo, monto, cantidad, "pendiente", creado_por, external_reference),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        # No revertimos la preference creada en MP; solo logueamos.
        print(f"Error guardando en BD: {e}")

    return resultado


_ESTADOS_MP = {
    "approved": "aprobado",
    "pending": "pendiente",
    "in_process": "en proceso",
    "rejected": "rechazado",
    "refunded": "reembolsado",
    "cancelled": "cancelado",
}


def verificar_pago(preference_id: str) -> dict:
    """Consulta MP por preference_id y persiste el último estado en BD."""
    resp = mercadopago_client.buscar_pago_por_preference(preference_id)
    if not resp.get("ok"):
        return resp

    results = resp["results"]
    if not results:
        return {
            "ok": True,
            "estado": "pendiente",
            "mensaje": "Todavía no se registró ningún pago para este link",
            "preference_id": preference_id,
        }

    pago = results[0]
    estado_mp = pago.get("status", "unknown")
    estado_es = _ESTADOS_MP.get(estado_mp, estado_mp)
    payment_id = str(pago.get("id", ""))
    email = pago.get("payer", {}).get("email", "")
    metodo = pago.get("payment_method_id", "")
    monto = pago.get("transaction_amount", 0)

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE pagos_mp
               SET estado = %s, payment_id = %s, email_pagador = %s,
                   metodo_pago = %s, fecha_pago = %s
               WHERE preference_id = %s""",
            (estado_es, payment_id, email, metodo, datetime.now(), preference_id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error actualizando BD: {e}")

    return {
        "ok": True,
        "estado": estado_es,
        "payment_id": payment_id,
        "monto": monto,
        "email_pagador": email,
        "metodo_pago": metodo,
        "preference_id": preference_id,
    }


def listar_pagos() -> dict:
    """Lista los pagos guardados en BD."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM pagos_mp ORDER BY fecha_creacion DESC")
        pagos = cursor.fetchall()
        conn.close()

        for p in pagos:
            for key in p:
                if isinstance(p[key], datetime):
                    p[key] = p[key].strftime("%Y-%m-%d %H:%M:%S")
                elif hasattr(p[key], "__str__") and not isinstance(p[key], str):
                    p[key] = str(p[key])

        return {"ok": True, "pagos": pagos, "total": len(pagos)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
