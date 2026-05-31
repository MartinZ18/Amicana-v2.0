"""CRUD de avisos institucionales.

- GET    /avisos          → público autenticado (alumnos también).
- POST   /avisos          → admin/administrativo.
- PUT    /avisos/{id}     → admin/administrativo.
- DELETE /avisos/{id}     → admin (soft delete).
"""
from fastapi import APIRouter, Depends

from ..database import get_connection
from ..dependencies import get_current_user, require_rol
from ..schemas.avisos import AvisoCreate, AvisoUpdate
from ..services import auditoria_service
from ..utils import serialize_row
from ..utils.responses import error, ok

router = APIRouter(tags=["avisos"])

_STAFF = ("admin", "administrativo")


@router.get("/avisos")
def listar_avisos(user: dict = Depends(get_current_user), limite: int = 20):
    """Lista avisos activos ordenados por fecha desc."""
    if limite < 1 or limite > 100:
        limite = 20
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT a.id, a.titulo, a.contenido, a.importante, "
            "a.fecha_publicacion, a.creado_por, a.activo, "
            "u.nombre AS creado_por_nombre "
            "FROM avisos a LEFT JOIN usuarios u ON a.creado_por = u.id "
            "WHERE a.activo = 1 "
            "ORDER BY a.fecha_publicacion DESC LIMIT %s",
            (limite,),
        )
        avisos = [serialize_row(row) for row in cursor.fetchall()]
    finally:
        conn.close()
    return ok(data={"avisos": avisos, "total": len(avisos)})


@router.post("/avisos")
def crear_aviso(data: AvisoCreate, user: dict = Depends(require_rol(*_STAFF))):
    """Crea un aviso. Solo admin/administrativo."""
    creado_por = user.get("id")
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO avisos (titulo, contenido, importante, creado_por) "
            "VALUES (%s, %s, %s, %s)",
            (data.titulo, data.contenido, 1 if data.importante else 0, creado_por),
        )
        conn.commit()
        new_id = cursor.lastrowid
    finally:
        conn.close()
    auditoria_service.registrar(user.get("sub", ""), "crear_aviso",
                                f"aviso_id={new_id} titulo={data.titulo[:60]}")
    return ok(data={"id": new_id}, mensaje="Aviso creado")


@router.put("/avisos/{aviso_id}")
def editar_aviso(aviso_id: int, data: AvisoUpdate,
                 user: dict = Depends(require_rol(*_STAFF))):
    """Edita campos parciales del aviso."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM avisos WHERE id=%s", (aviso_id,))
        row = cursor.fetchone()
        if not row:
            raise error("Aviso no encontrado", 404)

        titulo     = data.titulo     if data.titulo     is not None else row["titulo"]
        contenido  = data.contenido  if data.contenido  is not None else row["contenido"]
        importante = (1 if data.importante else 0) if data.importante is not None else row["importante"]
        activo     = (1 if data.activo else 0) if data.activo is not None else row["activo"]

        cursor.execute(
            "UPDATE avisos SET titulo=%s, contenido=%s, importante=%s, activo=%s "
            "WHERE id=%s",
            (titulo, contenido, importante, activo, aviso_id),
        )
        conn.commit()
    finally:
        conn.close()
    auditoria_service.registrar(user.get("sub", ""), "editar_aviso", f"aviso_id={aviso_id}")
    return ok(mensaje="Aviso actualizado")


@router.delete("/avisos/{aviso_id}")
def eliminar_aviso(aviso_id: int, user: dict = Depends(require_rol("admin"))):
    """Soft delete: marca activo=0. Solo admin."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE avisos SET activo=0 WHERE id=%s", (aviso_id,))
        conn.commit()
        if not cursor.rowcount:
            raise error("Aviso no encontrado", 404)
    finally:
        conn.close()
    auditoria_service.registrar(user.get("sub", ""), "eliminar_aviso", f"aviso_id={aviso_id}")
    return ok(mensaje="Aviso desactivado")
