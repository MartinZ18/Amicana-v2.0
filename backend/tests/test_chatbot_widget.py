"""Tests for TASK-18: chatbot widget static files."""

import os


STATIC_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "static"
)


def test_widget_js_exists():
    path = os.path.join(STATIC_DIR, "chatbot-widget.js")
    assert os.path.isfile(path), "chatbot-widget.js no existe en /static/"
    assert os.path.getsize(path) > 0, "chatbot-widget.js está vacío"


def test_widget_css_exists():
    path = os.path.join(STATIC_DIR, "chatbot-widget.css")
    assert os.path.isfile(path), "chatbot-widget.css no existe en /static/"
    assert os.path.getsize(path) > 0, "chatbot-widget.css está vacío"


def test_widget_js_has_required_elements():
    path = os.path.join(STATIC_DIR, "chatbot-widget.js")
    content = open(path, encoding="utf-8").read()

    assert "session_id" in content, "falta manejo de session_id"
    assert "sessionStorage" in content, "falta uso de sessionStorage"
    assert "fetch" in content, "falta llamada fetch al webhook"
    assert "data-webhook" in content, "falta soporte de data-webhook"
    assert "amicana-chat-bubble" in content, "falta el elemento burbuja"
    assert "amicana-chat-panel" in content, "falta el panel del chat"
    assert "amicana-typing" in content, "falta el indicador de escritura"
    assert "qr_url" in content, "falta renderizado de QR"
    assert "pdf_url" in content, "falta renderizado de link PDF"


def test_widget_css_has_required_selectors():
    path = os.path.join(STATIC_DIR, "chatbot-widget.css")
    content = open(path, encoding="utf-8").read()

    assert "#amicana-chat-bubble" in content
    assert "#amicana-chat-panel" in content
    assert "#amicana-chat-toggle" in content
    assert ".amicana-msg" in content
    assert "amicana-typing" in content


def test_alumno_html_includes_widget():
    frontend_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "frontend"
    )
    path = os.path.join(frontend_dir, "alumno.html")
    content = open(path, encoding="utf-8").read()

    assert "chatbot-widget.js" in content, "alumno.html no incluye el widget JS"
    assert "chatbot-widget.css" in content, "alumno.html no incluye los estilos del widget"
