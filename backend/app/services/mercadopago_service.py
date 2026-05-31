"""Service de Mercado Pago.

Wrapper sobre el orquestador legacy `app.mercadopago_qr` (que a su vez
usa `services/mercadopago_client.py` para el HTTP). Esta capa agrega
auditoría centralizada de errores.

NO se modifica la lógica histórica para evitar regresiones; se delega y
se loguea.
"""
from typing import Optional

from ..mercadopago_qr import crear_pago as _crear_pago
from ..mercadopago_qr import listar_pagos as _listar_pagos
from ..mercadopago_qr import verificar_pago as _verificar_pago
from . import auditoria_service


def crear_pago(titulo: str, monto: float, cantidad: int = 1,
               email_pagador: str = "", creado_por: str = "",
               external_reference: str = "") -> dict:
    """Crea preference en MP. Devuelve `{ok, preference_id, init_point, ...}`."""
    resultado = _crear_pago(titulo, monto, cantidad, email_pagador, creado_por, external_reference)
    if not resultado.get("ok"):
        auditoria_service.registrar(
            creado_por or None,
            "error_api_externa",
            f"MP crear_pago falló: {resultado.get('error', 'desconocido')}",
        )
    return resultado


def verificar_pago(preference_id: str, usuario_email: Optional[str] = None) -> dict:
    """Consulta estado del pago en MP."""
    resultado = _verificar_pago(preference_id)
    if not resultado.get("ok"):
        auditoria_service.registrar(
            usuario_email,
            "error_api_externa",
            f"MP verificar_pago falló: {resultado.get('error', 'desconocido')}",
        )
    return resultado


def listar_pagos() -> dict:
    return _listar_pagos()


def generar_qr(cuota_id: int, monto: float, alumno_email: str = "",
               concepto: str = "") -> dict:
    """Atajo: crea preferencia para una cuota y devuelve la URL del QR.

    Lo usa el chatbot (vía n8n). Mantiene shape común con el orquestador
    legacy: `{ok, preference_id, init_point, qr_url, monto, cuota_id}`.
    """
    titulo = concepto or f"Cuota AMICANA #{cuota_id}"
    resultado = crear_pago(
        titulo=titulo, monto=monto, cantidad=1,
        email_pagador=alumno_email, creado_por="chatbot@amicana.com",
        external_reference=f"CUOTA_{cuota_id}"
    )
    if not resultado.get("ok"):
        return resultado

    return {
        "ok": True,
        "preference_id": resultado.get("preference_id"),
        "qr_url": resultado.get("init_point"),
        "init_point": resultado.get("init_point"),
        "sandbox_init_point": resultado.get("sandbox_init_point"),
        "monto": monto,
        "cuota_id": cuota_id,
    }
