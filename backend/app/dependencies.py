"""Dependencias FastAPI reutilizables.

Reexporta las funciones históricas de `app.auth` para cumplir la spec del
prompt (`dependencies.py` separado) sin romper imports existentes.

Uso típico:

    from app.dependencies import get_current_user, require_rol

    @router.get("/admin-only")
    def f(user: dict = Depends(require_rol("admin"))):
        ...
"""
from .auth import (  # noqa: F401  (reexport)
    get_current_user,
    get_chatbot_or_current_user,
    is_chatbot,
    oauth2_scheme,
    require_role,
    require_any_role,
)


def require_rol(*roles: str):
    """Factory de dependencia que exige uno o más roles.

    Equivale a `require_any_role(*roles)` pero con el nombre que pide la
    spec (`require_rol`). Mantenemos `require_role`/`require_any_role`
    por compatibilidad con el código existente.
    """
    return require_any_role(*roles)
