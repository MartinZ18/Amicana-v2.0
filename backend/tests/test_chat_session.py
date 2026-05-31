from unittest.mock import patch, MagicMock
from app.models.chat_session import ChatSession, ChatSessionRepository


# ── helpers ─────────────────────────────────────────────────────────────────

def _mock_cursor(fetchone_val=None, lastrowid=1, rowcount=1):
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone_val
    cursor.lastrowid = lastrowid
    cursor.rowcount = rowcount
    return cursor


def _mock_connection(cursor):
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


# ── tests ────────────────────────────────────────────────────────────────────

class TestChatSessionRepository:

    def test_create_returns_session_with_correct_id(self):
        cursor = _mock_cursor(lastrowid=7)
        conn = _mock_connection(cursor)
        repo = ChatSessionRepository()
        with patch("app.models.chat_session.get_connection", return_value=conn):
            session = repo.create("sess_abc")
        assert isinstance(session, ChatSession)
        assert session.id == 7
        assert session.session_id == "sess_abc"
        assert session.estado == "sin_autenticar"
        assert session.intentos_auth == 0

    def test_get_by_session_id_found(self):
        row = {
            "id": 7, "session_id": "sess_abc", "alumno_id": None,
            "estado": "sin_autenticar", "intentos_auth": 0,
            "creado_en": None, "actualizado_en": None,
        }
        cursor = _mock_cursor(fetchone_val=row)
        conn = _mock_connection(cursor)
        repo = ChatSessionRepository()
        with patch("app.models.chat_session.get_connection", return_value=conn):
            session = repo.get_by_session_id("sess_abc")
        assert session is not None
        assert session.session_id == "sess_abc"
        assert session.id == 7
        assert session.alumno_id is None

    def test_get_by_session_id_not_found(self):
        cursor = _mock_cursor(fetchone_val=None)
        conn = _mock_connection(cursor)
        repo = ChatSessionRepository()
        with patch("app.models.chat_session.get_connection", return_value=conn):
            session = repo.get_by_session_id("sess_no_existe")
        assert session is None

    def test_update_estado_returns_true_when_row_updated(self):
        cursor = _mock_cursor(rowcount=1)
        conn = _mock_connection(cursor)
        repo = ChatSessionRepository()
        with patch("app.models.chat_session.get_connection", return_value=conn):
            result = repo.update_estado("sess_abc", "autenticado", alumno_id=42)
        assert result is True

    def test_update_estado_returns_false_when_session_missing(self):
        cursor = _mock_cursor(rowcount=0)
        conn = _mock_connection(cursor)
        repo = ChatSessionRepository()
        with patch("app.models.chat_session.get_connection", return_value=conn):
            result = repo.update_estado("sess_fantasma", "autenticado")
        assert result is False

    def test_increment_intentos_returns_updated_count(self):
        cursor = _mock_cursor(fetchone_val={"intentos_auth": 2})
        conn = _mock_connection(cursor)
        repo = ChatSessionRepository()
        with patch("app.models.chat_session.get_connection", return_value=conn):
            count = repo.increment_intentos("sess_abc")
        assert count == 2

    def test_increment_intentos_returns_zero_if_session_missing(self):
        cursor = _mock_cursor(fetchone_val=None)
        conn = _mock_connection(cursor)
        repo = ChatSessionRepository()
        with patch("app.models.chat_session.get_connection", return_value=conn):
            count = repo.increment_intentos("sess_fantasma")
        assert count == 0

    def test_upsert_envia_query_idempotente(self):
        """upsert(): un único INSERT ... ON DUPLICATE KEY UPDATE."""
        cursor = _mock_cursor()
        conn = _mock_connection(cursor)
        repo = ChatSessionRepository()
        with patch("app.models.chat_session.get_connection", return_value=conn):
            repo.upsert("sess_abc", 42, "autenticado", 0,
                        [{"role": "user", "parts": [{"text": "hola"}]}])
        sql_call = cursor.execute.call_args
        sql, params = sql_call.args
        assert "INSERT INTO chat_sessions" in sql
        assert "ON DUPLICATE KEY UPDATE" in sql
        assert params[0] == "sess_abc"
        assert params[1] == 42
        assert params[2] == "autenticado"
        # history serializado a JSON
        import json as _json
        assert _json.loads(params[4]) == [{"role": "user", "parts": [{"text": "hola"}]}]

    def test_upsert_history_none_se_persiste_como_null(self):
        cursor = _mock_cursor()
        conn = _mock_connection(cursor)
        repo = ChatSessionRepository()
        with patch("app.models.chat_session.get_connection", return_value=conn):
            repo.upsert("sess_x", None, "sin_autenticar", 0, None)
        params = cursor.execute.call_args.args[1]
        assert params[4] is None

    def test_get_by_session_id_parsea_history_json(self):
        """history llega como string JSON desde MySQL → repo lo deserializa."""
        row = {
            "id": 1, "session_id": "sess_abc", "alumno_id": 42,
            "estado": "autenticado", "intentos_auth": 0,
            "history": '[{"role":"user","parts":[{"text":"hola"}]}]',
            "creado_en": None, "actualizado_en": None,
        }
        cursor = _mock_cursor(fetchone_val=row)
        conn = _mock_connection(cursor)
        repo = ChatSessionRepository()
        with patch("app.models.chat_session.get_connection", return_value=conn):
            session = repo.get_by_session_id("sess_abc")
        assert session.history == [{"role": "user", "parts": [{"text": "hola"}]}]


# ── tests endpoints /chatbot/session ─────────────────────────────────────────

from fastapi.testclient import TestClient
from app.main import app

_client = TestClient(app)
CHATBOT_HEADERS = {"X-Chatbot-Key": "amicana-internal"}


class TestChatbotSessionEndpoints:

    def test_get_session_inexistente_devuelve_null(self):
        with patch("app.routers.chatbot._repo.get_by_session_id", return_value=None):
            r = _client.get("/chatbot/session/sess_x", headers=CHATBOT_HEADERS)
        assert r.status_code == 200
        assert r.json() == {"ok": True, "session": None}

    def test_get_session_existente(self):
        sess = ChatSession(id=1, session_id="sess_x", alumno_id=42,
                           estado="autenticado", intentos_auth=0,
                           history=[{"role": "user", "parts": [{"text": "hi"}]}])
        with patch("app.routers.chatbot._repo.get_by_session_id", return_value=sess):
            r = _client.get("/chatbot/session/sess_x", headers=CHATBOT_HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["session"]["alumno_id"] == 42

    def test_upsert_session(self):
        with patch("app.routers.chatbot._repo.upsert") as up:
            r = _client.post("/chatbot/session", headers=CHATBOT_HEADERS,
                             json={"session_id": "sess_x", "alumno_id": 42,
                                   "estado": "autenticado", "intentos_auth": 0,
                                   "history": []})
        assert r.status_code == 200
        up.assert_called_once()

    def test_endpoints_requieren_chatbot_key(self):
        from app.auth import create_access_token
        # Un alumno no debería poder leer/escribir sesiones internas.
        token = create_access_token({"sub": "alumno@x.com", "rol": "alumno", "id": 1})
        h = {"Authorization": f"Bearer {token}"}
        r1 = _client.get("/chatbot/session/sess_x", headers=h)
        r2 = _client.post("/chatbot/session", headers=h,
                          json={"session_id": "sess_x"})
        assert r1.status_code == 403
        assert r2.status_code == 403

    def test_sin_auth_401(self):
        r1 = _client.get("/chatbot/session/sess_x")
        r2 = _client.post("/chatbot/session", json={"session_id": "sess_x"})
        assert r1.status_code == 401
        assert r2.status_code == 401
