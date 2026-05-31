"""Formato estándar de respuestas para todos los endpoints.

Todas las respuestas exitosas usan `ok(...)`. Los errores se levantan con
`raise error(...)` para que FastAPI propague el `HTTPException` con el
mismo formato `{ok: false, mensaje: ...}`.
"""
from typing import Any, Optional

from fastapi import HTTPException


def ok(data: Any = None, mensaje: Optional[str] = None) -> dict:
    """Respuesta de éxito estándar.

    - `ok(data={...})` → `{"ok": True, "data": {...}}`
    - `ok(mensaje="X")` → `{"ok": True, "mensaje": "X"}`
    - `ok(data=..., mensaje=...)` → ambos.
    """
    response: dict = {"ok": True}
    if mensaje is not None:
        response["mensaje"] = mensaje
    if data is not None:
        response["data"] = data
    return response


def error(mensaje: str, codigo: int = 400) -> HTTPException:
    """Crea (no levanta) una HTTPException con `{ok: false, mensaje}`.

    Uso: `raise error("texto", 404)`.
    """
    return HTTPException(status_code=codigo, detail={"ok": False, "mensaje": mensaje})
