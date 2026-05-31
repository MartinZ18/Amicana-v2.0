from typing import Optional, List, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from ..auth import get_chatbot_or_current_user, is_chatbot, require_role
from ..models.chat_session import ChatSessionRepository
from ..utils.responses import error, ok

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

_repo = ChatSessionRepository()


class SessionUpsertRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    alumno_id: Optional[int] = None
    estado: str = "sin_autenticar"
    intentos_auth: int = 0
    history: List[Any] = []


@router.get("/session/{session_id}")
def get_session(session_id: str, user: dict = Depends(get_chatbot_or_current_user)):
    """Lee la sesión persistida del chatbot. Solo el chatbot (X-Chatbot-Key)."""
    if not is_chatbot(user):
        raise error("Solo el chatbot puede leer sesiones", 403)
    sess = _repo.get_by_session_id(session_id)
    if not sess:
        return {"ok": True, "session": None}
    return {"ok": True, "session": sess.model_dump(mode="json")}


@router.post("/session")
def upsert_session(data: SessionUpsertRequest, user: dict = Depends(get_chatbot_or_current_user)):
    """Persiste/actualiza la sesión del chatbot."""
    if not is_chatbot(user):
        raise error("Solo el chatbot puede actualizar sesiones", 403)
    _repo.upsert(data.session_id, data.alumno_id, data.estado, data.intentos_auth, data.history)
    return {"ok": True}


@router.delete("/sessions/stale")
def limpiar_sesiones_stale(days: int = 30,
                           user: dict = Depends(require_role("admin"))):
    """Elimina sesiones sin actividad hace más de `days` días (solo admin).

    Puede ser llamado desde un Cron trigger en n8n o manualmente.
    """
    eliminadas = _repo.cleanup_stale(days=days)
    return ok(data={"eliminadas": eliminadas},
              mensaje=f"Se eliminaron {eliminadas} sesiones inactivas.")
