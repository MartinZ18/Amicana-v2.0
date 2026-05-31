import json
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from ..database import get_connection


class ChatSession(BaseModel):
    id: Optional[int] = None
    session_id: str
    alumno_id: Optional[int] = None
    estado: str = "sin_autenticar"
    intentos_auth: int = 0
    history: Optional[List[Any]] = None
    creado_en: Optional[datetime] = None
    actualizado_en: Optional[datetime] = None


class ChatSessionRepository:
    """Repository for chat_sessions table. All methods open and close their own connection."""

    def create(self, session_id: str) -> ChatSession:
        """Insert a new unauthenticated session and return it."""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "INSERT INTO chat_sessions (session_id) VALUES (%s)",
            (session_id,)
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return ChatSession(id=new_id, session_id=session_id)

    def get_by_session_id(self, session_id: str) -> Optional[ChatSession]:
        """Return the session matching session_id, or None if not found."""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM chat_sessions WHERE session_id = %s",
            (session_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        # MySQL devuelve JSON como str (mysql-connector lo parsea solo a veces).
        h = row.get("history")
        if isinstance(h, str):
            try:
                row["history"] = json.loads(h)
            except (TypeError, ValueError):
                row["history"] = None
        return ChatSession(**row)

    def upsert(self, session_id: str, alumno_id: Optional[int],
               estado: str, intentos_auth: int,
               history: Optional[List[Any]]) -> None:
        """Insertar o actualizar la sesión. Idempotente: el caller puede llamar
        en cada turno y tanto crea como sobrescribe la fila."""
        history_json = json.dumps(history) if history is not None else None
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_sessions (session_id, alumno_id, estado, intentos_auth, history) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "alumno_id=VALUES(alumno_id), estado=VALUES(estado), "
            "intentos_auth=VALUES(intentos_auth), history=VALUES(history)",
            (session_id, alumno_id, estado, intentos_auth, history_json)
        )
        conn.commit()
        conn.close()

    def update_estado(self, session_id: str, estado: str,
                      alumno_id: Optional[int] = None) -> bool:
        """Update estado (and optionally alumno_id) for a session. Returns True if a row was updated."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE chat_sessions SET estado = %s, alumno_id = %s WHERE session_id = %s",
            (estado, alumno_id, session_id)
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    def cleanup_stale(self, days: int = 30) -> int:
        """Borra sesiones sin actividad hace más de `days` días. Devuelve filas eliminadas."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM chat_sessions WHERE actualizado_en < DATE_SUB(NOW(), INTERVAL %s DAY)",
            (days,),
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected

    def increment_intentos(self, session_id: str) -> int:
        """Increment intentos_auth by 1 and return the updated value."""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "UPDATE chat_sessions SET intentos_auth = intentos_auth + 1 WHERE session_id = %s",
            (session_id,)
        )
        conn.commit()
        cursor.execute(
            "SELECT intentos_auth FROM chat_sessions WHERE session_id = %s",
            (session_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return row["intentos_auth"] if row else 0
