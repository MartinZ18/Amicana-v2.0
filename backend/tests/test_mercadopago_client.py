"""Tests del cliente HTTP puro de MercadoPago (services.mercadopago_client).

No tocan BD ni se acoplan a `mercadopago_qr` (que es el orquestador).
"""
from unittest.mock import MagicMock, patch

import requests as req_lib

from app.services import mercadopago_client as mp


class TestCrearPreference:

    def _resp(self, status, body):
        m = MagicMock()
        m.status_code = status
        m.json.return_value = body
        return m

    def test_201_devuelve_preference_id(self):
        resp = self._resp(201, {
            "id": "PREF-123",
            "init_point": "https://mp.com/p/123",
            "sandbox_init_point": "https://sandbox.mp.com/p/123",
        })
        with patch("app.services.mercadopago_client.requests.post", return_value=resp):
            r = mp.crear_preference(titulo="Cuota", monto=1000)
        assert r["ok"] is True
        assert r["preference_id"] == "PREF-123"
        assert r["init_point"].startswith("https://")

    def test_email_pagador_se_envia_si_no_vacio(self):
        resp = self._resp(201, {"id": "PREF-1"})
        with patch("app.services.mercadopago_client.requests.post", return_value=resp) as p:
            mp.crear_preference(titulo="x", monto=10, email_pagador="alumno@test.com")
        body_enviado = p.call_args.kwargs["json"]
        assert body_enviado["payer"]["email"] == "alumno@test.com"

    def test_email_pagador_vacio_no_agrega_payer(self):
        resp = self._resp(201, {"id": "PREF-1"})
        with patch("app.services.mercadopago_client.requests.post", return_value=resp) as p:
            mp.crear_preference(titulo="x", monto=10, email_pagador="")
        body_enviado = p.call_args.kwargs["json"]
        assert "payer" not in body_enviado

    def test_status_400_devuelve_ok_false(self):
        resp = self._resp(400, {"message": "Invalid"})
        with patch("app.services.mercadopago_client.requests.post", return_value=resp):
            r = mp.crear_preference(titulo="x", monto=10)
        assert r["ok"] is False
        assert r["status_code"] == 400
        assert "Invalid" in r["error"]

    def test_status_400_sin_json_no_crashea(self):
        m = MagicMock()
        m.status_code = 502
        m.json.side_effect = ValueError("no json")
        with patch("app.services.mercadopago_client.requests.post", return_value=m):
            r = mp.crear_preference(titulo="x", monto=10)
        assert r["ok"] is False
        assert r["status_code"] == 502
        assert r["detalle"] is None

    def test_timeout_devuelve_ok_false(self):
        with patch("app.services.mercadopago_client.requests.post",
                   side_effect=req_lib.exceptions.Timeout("timeout")):
            r = mp.crear_preference(titulo="x", monto=10)
        assert r["ok"] is False
        assert "Mercado Pago" in r["error"]

    def test_connection_error_devuelve_ok_false(self):
        with patch("app.services.mercadopago_client.requests.post",
                   side_effect=req_lib.exceptions.ConnectionError("no route")):
            r = mp.crear_preference(titulo="x", monto=10)
        assert r["ok"] is False


class TestBuscarPagoPorPreference:

    def test_results_vacio_es_ok(self):
        m = MagicMock(); m.status_code = 200; m.json.return_value = {"results": []}
        with patch("app.services.mercadopago_client.requests.get", return_value=m):
            r = mp.buscar_pago_por_preference("PREF-x")
        assert r["ok"] is True
        assert r["results"] == []

    def test_status_no_200_es_error(self):
        m = MagicMock(); m.status_code = 503
        with patch("app.services.mercadopago_client.requests.get", return_value=m):
            r = mp.buscar_pago_por_preference("PREF-x")
        assert r["ok"] is False
        assert r["status_code"] == 503

    def test_excepcion_red_devuelve_error(self):
        with patch("app.services.mercadopago_client.requests.get",
                   side_effect=req_lib.exceptions.ConnectionError()):
            r = mp.buscar_pago_por_preference("PREF-x")
        assert r["ok"] is False


class TestAccessTokenLazy:
    def test_no_token_levanta_runtime_error(self, monkeypatch):
        """Si MP_ACCESS_TOKEN está vacío al llamar (no a import time)."""
        monkeypatch.delenv("MP_ACCESS_TOKEN", raising=False)
        try:
            mp.crear_preference(titulo="x", monto=10)
            assert False, "debió haber levantado RuntimeError"
        except RuntimeError as e:
            assert "MP_ACCESS_TOKEN" in str(e)
