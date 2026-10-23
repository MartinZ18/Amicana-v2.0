import os
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_pytest_only")
os.environ.setdefault("CHATBOT_INTERNAL_KEY", "amicana-internal")

from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _dependencias_usan_la_conexion_de_pagos():
    """Las dependencias de permisos (app.dependencies) consultan la misma BD que
    el router de pagos. Los tests mockean `app.routers.pagos.get_connection`;
    esto hace que las dependencias usen ese mismo mock en vez de una MySQL real."""
    import app.routers.pagos as pagos

    with patch("app.dependencies.get_connection", side_effect=lambda: pagos.get_connection()):
        yield
