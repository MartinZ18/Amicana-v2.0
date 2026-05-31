"""Configuración del sistema (clave/valor en `preferencias_sistema`).

Solo `admin` puede leer/escribir. Las claves editables están en una whitelist
para evitar que se persista cualquier valor arbitrario.
"""
from fastapi import APIRouter, Body, Depends

from ..auth import require_role
from ..database import get_connection
from ..services import auditoria_service
from ..utils.responses import error, ok

router = APIRouter(tags=["configuracion"])

CLAVES_EDITABLES = {
    "instituto_nombre",
    "instituto_direccion",
    "instituto_telefono",
    "instituto_email",
    "cuotas_dia_vencimiento",
    "cuotas_recargo_porcentaje",
    "chatbot_habilitado",
    "avisos_dias_visibles",
}


_CLAVES_PUBLICAS = (
    "instituto_nombre",
    "instituto_direccion",
    "instituto_telefono",
    "instituto_email",
)


@router.get("/configuracion/publica")
def configuracion_publica():
    """Subset de preferencias visibles a cualquiera (sin autenticación).

    Usado por la pestaña "Quiénes somos > Nuestra Sede" del panel alumno
    y por usuarios no logueados que consultan datos del instituto.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        placeholders = ",".join(["%s"] * len(_CLAVES_PUBLICAS))
        cursor.execute(
            f"SELECT clave, valor FROM preferencias_sistema WHERE clave IN ({placeholders})",
            _CLAVES_PUBLICAS,
        )
        prefs = {r["clave"]: r["valor"] for r in cursor.fetchall()}
    finally:
        conn.close()
    return ok(data={"preferencias": prefs})


@router.get("/configuracion")
def leer_configuracion(user: dict = Depends(require_role("admin"))):
    """Devuelve todas las preferencias del sistema."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT clave, valor, descripcion FROM preferencias_sistema ORDER BY clave"
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    config = {r["clave"]: r["valor"] for r in rows}
    return ok(data={"configuracion": config, "items": rows})


@router.put("/configuracion")
def actualizar_configuracion(
    payload: dict = Body(...),
    user: dict = Depends(require_role("admin")),
):
    """Actualiza una o más preferencias. Solo claves de la whitelist."""
    if not isinstance(payload, dict) or not payload:
        raise error("Enviá un objeto clave/valor con al menos un campo", 400)

    invalidas = [k for k in payload.keys() if k not in CLAVES_EDITABLES]
    if invalidas:
        raise error(f"Claves no editables: {', '.join(invalidas)}", 400)

    conn = get_connection()
    cursor = conn.cursor()
    actualizadas: list[str] = []
    try:
        for clave, valor in payload.items():
            cursor.execute(
                "INSERT INTO preferencias_sistema (clave, valor) VALUES (%s, %s) "
                "ON DUPLICATE KEY UPDATE valor = VALUES(valor)",
                (clave, str(valor) if valor is not None else ""),
            )
            actualizadas.append(clave)
        conn.commit()
    finally:
        conn.close()

    auditoria_service.registrar(
        user.get("sub"), "actualizar_configuracion",
        f"claves={','.join(actualizadas)}",
    )
    return ok(mensaje=f"{len(actualizadas)} preferencia(s) actualizada(s)",
              data={"claves": actualizadas})
