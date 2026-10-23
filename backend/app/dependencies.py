"""Dependencias FastAPI reutilizables.

Reexporta las funciones históricas de `app.auth` para cumplir la spec del
prompt (`dependencies.py` separado) sin romper imports existentes.

Uso típico:

    from app.dependencies import get_current_user, require_rol

    @router.get("/admin-only")
    def f(user: dict = Depends(require_rol("admin"))):
        ...
"""
from fastapi import Depends

from .auth import (  # noqa: F401  (reexport)
    get_current_user,
    get_chatbot_or_current_user,
    is_chatbot,
    oauth2_scheme,
    require_role,
    require_any_role,
)
from .database import get_connection
from .utils.responses import error

_STAFF = ("admin", "administrativo")


def require_rol(*roles: str):
    """Factory de dependencia que exige uno o más roles.

    Equivale a `require_any_role(*roles)` pero con el nombre que pide la
    spec (`require_rol`). Mantenemos `require_role`/`require_any_role`
    por compatibilidad con el código existente.
    """
    return require_any_role(*roles)


def require_chatbot_or_rol(*roles: str):
    """Factory de dependencia: deja pasar al chatbot (X-Chatbot-Key) o a los roles indicados."""
    def checker(user: dict = Depends(get_chatbot_or_current_user)):
        if not is_chatbot(user) and user.get("rol") not in roles:
            raise error("Sin permisos", 403)
        return user
    return checker


def chatbot_de_alumno(alumno_id: int, user: dict = Depends(get_chatbot_or_current_user)):
    """Dependencia: solo el chatbot, y con una sesión autenticada del mismo `alumno_id` del path."""
    if not is_chatbot(user):
        raise error("Solo el chatbot puede consumir este endpoint", 403)
    if user.get("chatbot_alumno_id") != alumno_id:
        raise error("alumno_id no coincide con la sesión autenticada", 403)
    return user


def puede_pagar_cuota(cuota_id: int, user: dict = Depends(get_chatbot_or_current_user)):
    """Dependencia: staff paga cualquier cuota; un alumno o el chatbot (con la sesión
    del alumno) solo las propias. Ajena e inexistente responden 404."""
    if user.get("rol") in _STAFF:
        return user
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT alumno_id FROM cuotas WHERE id = %s", (cuota_id,))
        fila = cursor.fetchone()
    finally:
        conn.close()
    if not fila:
        return user
    duenio = fila["alumno_id"]
    # "No es tuya" responde igual que "no existe" (404) para no revelar qué cuotas existen.
    propia = user.get("chatbot_alumno_id") if is_chatbot(user) else user.get("id")
    if propia is None or propia != duenio:
        raise error("Cuota no encontrada", 404)
    return user


def puede_verificar_pago(preference_id: str, user: dict = Depends(get_current_user)):
    """Dependencia: staff verifica cualquier preferencia; un alumno solo las de sus cuotas.

    "No es tuya" y "no existe" responden igual (404) para no revelar preferencias ajenas.
    """
    if user.get("rol") in _STAFF:
        return user
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM cuotas WHERE preference_id = %s AND alumno_id = %s LIMIT 1",
                       (preference_id, user.get("id")))
        propia = cursor.fetchone()
    finally:
        conn.close()
    if not propia:
        raise error("Preferencia no encontrada", 404)
    return user
