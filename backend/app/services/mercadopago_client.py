"""Cliente HTTP puro contra la API REST de MercadoPago.

Sin acceso a BD ni efectos secundarios — solo arma payloads, hace la llamada
y normaliza la respuesta. La persistencia (registrar pago en `pagos_mp`,
actualizar estados) la hace el orquestador en `mercadopago_qr.py`.

Esto facilita los tests: mockear `requests` sin tocar la BD.
"""
import hashlib
import hmac
import os
from typing import Optional

import requests

MP_API_BASE = "https://api.mercadopago.com"


def verificar_firma_webhook(
    x_signature: str,
    x_request_id: str,
    data_id: str,
) -> bool:
    """Valida la firma HMAC-SHA256 que MP incluye en cada notificación IPN.

    Algoritmo oficial:
      1. Armar el template: "id:<data.id>;request-id:<x-request-id>;ts:<ts>;"
      2. HMAC-SHA256 con MP_WEBHOOK_SECRET como clave.
      3. Comparar con el hash v1 del header x-signature.

    Devuelve False (sin lanzar excepción) si el secret no está configurado
    o si la firma no coincide — el caller decide si rechazar o solo loguear.
    """
    secret = os.environ.get("MP_WEBHOOK_SECRET", "").strip()
    if not secret:
        return False

    ts = ""
    v1 = ""
    for part in x_signature.split(","):
        part = part.strip()
        if part.startswith("ts="):
            ts = part[3:]
        elif part.startswith("v1="):
            v1 = part[3:]

    if not ts or not v1:
        return False

    template = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
    expected = hmac.new(
        secret.encode(), template.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, v1)


def _access_token() -> str:
    """Lee el token en cada llamada (no a import time) para que `conftest.py`
    pueda inyectarlo aunque el módulo se haya importado antes."""
    token = os.environ.get("MP_ACCESS_TOKEN")
    if not token:
        raise RuntimeError(
            "MP_ACCESS_TOKEN no está definida. Definila en .env (token de sandbox de MercadoPago)."
        )
    return token


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_access_token()}",
        "Content-Type": "application/json",
    }


def crear_preference(titulo: str, monto: float, cantidad: int = 1,
                     email_pagador: str = "", external_reference: str = "", timeout: int = 15) -> dict:
    """Crea una preference en MercadoPago Checkout Pro.

    Devuelve `{ok: True, preference_id, init_point, sandbox_init_point, ...}`
    o `{ok: False, error, status_code, detalle?}` ante cualquier fallo. Nunca
    levanta excepción.
    """
    ngrok_url = os.environ.get("NGROK_URL", "http://localhost:8000").rstrip("/")
    
    body = {
        "items": [{
            "title": titulo,
            "quantity": cantidad,
            "unit_price": float(monto),
            "currency_id": "ARS",
        }],
        "back_urls": {
            "success": f"{ngrok_url}/app/alumno.html?pago=exito",
            "pending": f"{ngrok_url}/app/alumno.html?pago=pendiente",
            "failure": f"{ngrok_url}/app/alumno.html?pago=error"
        },
        "auto_return": "approved",
        "notification_url": f"{ngrok_url}/pagos/webhook"
    }
    
    if external_reference:
        body["external_reference"] = external_reference

    if email_pagador:
        body["payer"] = {"email": email_pagador}

    try:
        response = requests.post(
            f"{MP_API_BASE}/checkout/preferences",
            json=body,
            headers=_headers(),
            timeout=timeout,
        )
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": f"Error de conexión con Mercado Pago: {str(e)}"}

    if response.status_code in (200, 201):
        data = response.json()
        return {
            "ok": True,
            "preference_id": data.get("id"),
            "init_point": data.get("init_point"),
            "sandbox_init_point": data.get("sandbox_init_point"),
            "titulo": titulo,
            "monto": monto,
            "cantidad": cantidad,
        }

    detalle: Optional[dict]
    try:
        detalle = response.json()
        msg = detalle.get("message", "Error al crear el pago")
    except ValueError:
        detalle = None
        msg = f"Error HTTP {response.status_code} al crear el pago"

    return {
        "ok": False,
        "error": msg,
        "status_code": response.status_code,
        "detalle": detalle,
    }


def buscar_pago_por_preference(preference_id: str, timeout: int = 15) -> dict:
    """Consulta `/v1/payments/search?preference_id=...` y normaliza la respuesta.

    Devuelve `{ok: True, results: [...]}` o `{ok: False, error, status_code}`.
    """
    try:
        response = requests.get(
            f"{MP_API_BASE}/v1/payments/search",
            params={"preference_id": preference_id},
            headers=_headers(),
            timeout=timeout,
        )
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": f"Error de conexión con Mercado Pago: {str(e)}"}

    if response.status_code != 200:
        return {
            "ok": False,
            "error": "Error al consultar MercadoPago",
            "status_code": response.status_code,
        }

    data = response.json()
    return {"ok": True, "results": data.get("results", [])}


def buscar_pago_por_id(payment_id: str, timeout: int = 15) -> dict:
    """Consulta `/v1/payments/{payment_id}` y devuelve los datos del pago.
    
    Se utiliza para verificar notificaciones de Webhooks (IPN) de manera segura.
    Devuelve `{ok: True, pago: {...}}` o `{ok: False, error, status_code}`.
    """
    try:
        response = requests.get(
            f"{MP_API_BASE}/v1/payments/{payment_id}",
            headers=_headers(),
            timeout=timeout,
        )
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": f"Error de conexión con Mercado Pago: {str(e)}"}

    if response.status_code != 200:
        return {
            "ok": False,
            "error": "Error al consultar MercadoPago",
            "status_code": response.status_code,
        }

    return {"ok": True, "pago": response.json()}

