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
from .utils.responses import error


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
