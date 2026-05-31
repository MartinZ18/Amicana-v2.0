"""Notas y progreso del alumno por unidad y sección.

GET    /mi-progreso              alumno autenticado, devuelve sus notas + promedios.
GET    /alumnos/{id}/notas       admin/administrativo.
POST   /notas                    admin/administrativo (upsert por uniq_alumno_unidad_seccion).
DELETE /notas/{id}               admin/administrativo.
GET    /unidades                 cualquier autenticado (filtro opcional curso_id).
POST   /unidades                 admin/administrativo.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..database import get_connection
from ..dependencies import get_current_user, require_rol
from ..schemas.progreso import NotaCreate, UnidadCreate
from ..utils.responses import error, ok

router = APIRouter(tags=["progreso"])

_STAFF = ("admin", "administrativo")
_SECCIONES = ("grammar", "vocabulary", "speaking", "listening", "writing", "reading")


def _serializar_unidad(row: dict) -> dict:
    return {
        "id":       row["id"],
        "curso_id": row["curso_id"],
        "numero":   row["numero"],
        "titulo":   row["titulo"],
        "orden":    row["orden"],
        "activa":   bool(row["activa"]),
    }


def _alumno_id_de_email(cursor, email: str) -> Optional[int]:
    cursor.execute("SELECT id FROM usuarios WHERE email=%s AND rol='alumno'", (email,))
    row = cursor.fetchone()
    return row["id"] if row else None


@router.get("/mi-progreso")
def mi_progreso(user: dict = Depends(get_current_user)):
    """Progreso del alumno autenticado: notas por unidad/sección, promedios y pain points."""
    if user.get("rol") != "alumno":
        raise error("Endpoint exclusivo para alumnos", 403)

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        alumno_id = _alumno_id_de_email(cursor, user.get("sub", ""))
        if not alumno_id:
            raise error("Alumno no encontrado", 404)

        cursor.execute("SELECT curso_id FROM usuarios WHERE id=%s", (alumno_id,))
        u = cursor.fetchone() or {}
        curso_id = u.get("curso_id")

        unidades: list[dict] = []
        if curso_id:
            cursor.execute(
                "SELECT id, curso_id, numero, titulo, orden, activa "
                "FROM unidades WHERE curso_id=%s AND activa=1 "
                "ORDER BY orden, numero",
                (curso_id,),
            )
            unidades = [_serializar_unidad(r) for r in cursor.fetchall()]

        cursor.execute(
            "SELECT n.id, n.unidad_id, n.seccion, n.nota, n.pain_points, n.fecha, "
            "       u.numero AS unidad_numero, u.titulo AS unidad_titulo "
            "FROM notas_alumno n "
            "JOIN unidades u ON u.id = n.unidad_id "
            "WHERE n.alumno_id=%s "
            "ORDER BY u.orden, u.numero, n.seccion",
            (alumno_id,),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    por_unidad: dict[int, dict] = {}
    suma_total = 0.0
    n_total = 0
    for r in rows:
        uid = r["unidad_id"]
        nota = float(r["nota"])
        suma_total += nota
        n_total += 1
        bucket = por_unidad.setdefault(uid, {
            "unidad_id":   uid,
            "numero":      r["unidad_numero"],
            "titulo":      r["unidad_titulo"],
            "secciones":   {},
            "pain_points": [],
        })
        bucket["secciones"][r["seccion"]] = {
            "nota":  nota,
            "fecha": str(r["fecha"]) if r.get("fecha") else None,
        }
        if r.get("pain_points"):
            bucket["pain_points"].append({"seccion": r["seccion"], "texto": r["pain_points"]})

    for u_data in por_unidad.values():
        notas = [s["nota"] for s in u_data["secciones"].values()]
        u_data["promedio"] = round(sum(notas) / len(notas), 2) if notas else None

    promedio_seccion: dict[str, float] = {}
    for sec in _SECCIONES:
        valores = [float(r["nota"]) for r in rows if r["seccion"] == sec]
        if valores:
            promedio_seccion[sec] = round(sum(valores) / len(valores), 2)

    promedio_general = round(suma_total / n_total, 2) if n_total else None

    return ok(data={
        "unidades_disponibles": unidades,
        "progreso_por_unidad":  list(por_unidad.values()),
        "promedio_por_seccion": promedio_seccion,
        "promedio_general":     promedio_general,
        "total_notas":          n_total,
    })


@router.get("/alumnos/{alumno_id}/notas")
def notas_de_alumno(alumno_id: int, user: dict = Depends(require_rol(*_STAFF))):
    """Listado plano de notas de un alumno (para que el staff las edite)."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT n.id, n.alumno_id, n.unidad_id, n.seccion, n.nota, n.pain_points, "
            "       n.fecha, u.numero AS unidad_numero, u.titulo AS unidad_titulo "
            "FROM notas_alumno n JOIN unidades u ON u.id=n.unidad_id "
            "WHERE n.alumno_id=%s ORDER BY u.orden, u.numero, n.seccion",
            (alumno_id,),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()
    for r in rows:
        r["nota"]  = float(r["nota"])
        r["fecha"] = str(r["fecha"]) if r.get("fecha") else None
    return ok(data={"notas": rows, "total": len(rows)})


@router.post("/notas")
def crear_nota(data: NotaCreate, user: dict = Depends(require_rol(*_STAFF))):
    """Upsert de una nota por (alumno, unidad, sección)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO notas_alumno (alumno_id, unidad_id, seccion, nota, pain_points, fecha) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE nota=VALUES(nota), "
            "pain_points=VALUES(pain_points), fecha=VALUES(fecha)",
            (data.alumno_id, data.unidad_id, data.seccion,
             data.nota, data.pain_points, data.fecha),
        )
        conn.commit()
        new_id = cursor.lastrowid
    finally:
        conn.close()
    return ok(data={"id": new_id}, mensaje="Nota guardada")


@router.delete("/notas/{nota_id}")
def eliminar_nota(nota_id: int, user: dict = Depends(require_rol(*_STAFF))):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM notas_alumno WHERE id=%s", (nota_id,))
        conn.commit()
        if not cursor.rowcount:
            raise error("Nota no encontrada", 404)
    finally:
        conn.close()
    return ok(mensaje="Nota eliminada")


@router.get("/unidades")
def listar_unidades(curso_id: Optional[int] = Query(default=None),
                    user: dict = Depends(get_current_user)):
    """Lista unidades. Si se pasa curso_id, filtra; si no, devuelve todas."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        if curso_id is not None:
            cursor.execute(
                "SELECT id, curso_id, numero, titulo, orden, activa "
                "FROM unidades WHERE curso_id=%s ORDER BY orden, numero",
                (curso_id,),
            )
        else:
            cursor.execute(
                "SELECT id, curso_id, numero, titulo, orden, activa "
                "FROM unidades ORDER BY curso_id, orden, numero"
            )
        rows = cursor.fetchall()
    finally:
        conn.close()
    return ok(data={"unidades": [_serializar_unidad(r) for r in rows]})


@router.post("/unidades")
def crear_unidad(data: UnidadCreate, user: dict = Depends(require_rol(*_STAFF))):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO unidades (curso_id, numero, titulo, orden, activa) "
            "VALUES (%s, %s, %s, %s, %s)",
            (data.curso_id, data.numero, data.titulo, data.orden, data.activa),
        )
        conn.commit()
        new_id = cursor.lastrowid
    finally:
        conn.close()
    return ok(data={"id": new_id}, mensaje="Unidad creada")
