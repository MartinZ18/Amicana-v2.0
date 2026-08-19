"""Tests para GET /chatbot/avisos (fuente de datos para la ingesta RAG)."""
import os
os.environ.setdefault("CHATBOT_INTERNAL_KEY", "amicana-internal")

from datetime import datetime
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
CHATBOT_HEADERS = {"X-Chatbot-Key": "amicana-internal"}


def _cur(all_=None):
    c = MagicMock()
    c.fetchall.return_value = all_ or []
    return c


def _conn(cur):
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


class TestChatbotAvisos:
    def test_lista_avisos_activos(self):
        avisos = [
            {"id": 1, "titulo": "Receso de invierno", "contenido": "No hay clases del 14 al 18/7.",
             "importante": True, "fecha_publicacion": datetime(2026, 7, 1, 10, 0, 0)},
        ]
        with patch("app.routers.chatbot_data.get_connection", return_value=_conn(_cur(all_=avisos))):
            r = client.get("/chatbot/avisos", headers=CHATBOT_HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert len(data["data"]["avisos"]) == 1
        assert data["data"]["avisos"][0]["titulo"] == "Receso de invierno"
        assert isinstance(data["data"]["avisos"][0]["fecha_publicacion"], str)

    def test_lista_vacia_cuando_no_hay_avisos(self):
        with patch("app.routers.chatbot_data.get_connection", return_value=_conn(_cur(all_=[]))):
            r = client.get("/chatbot/avisos", headers=CHATBOT_HEADERS)
        assert r.status_code == 200
        assert r.json()["data"]["avisos"] == []

    def test_sin_auth_retorna_401(self):
        r = client.get("/chatbot/avisos")
        assert r.status_code == 401

    def test_clave_incorrecta_retorna_401(self):
        r = client.get("/chatbot/avisos", headers={"X-Chatbot-Key": "clave-incorrecta"})
        assert r.status_code == 401
