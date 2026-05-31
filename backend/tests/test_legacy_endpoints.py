"""Tests para endpoints históricos que vivían en main.py:
- GET /Prueba (smoke)
- GET /mis-cuotas (alumno propio)
- POST /crear-pago (validación de monto)

Migrados desde el viejo `app/test_amicana.py` que dependía de credenciales
reales contra MySQL (ahora todos usan mocks).
"""
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.auth import create_access_token

client = TestClient(app)


def _alumno_header(uid=99, email="alumno@test.com"):
    t = create_access_token({"sub": email, "rol": "alumno", "id": uid})
    return {"Authorization": f"Bearer {t}"}


def _cur(one=None, all_=None, rowcount=1):
    c = MagicMock()
    c.fetchone.return_value = one
    c.fetchall.return_value = all_ or []
    c.rowcount = rowcount
    return c


def _conn(cur):
    conn = MagicMock(); conn.cursor.return_value = cur; return conn


class TestRootSmoke:
    def test_prueba_responde_ok(self):
        r = client.get("/Prueba")
        assert r.status_code == 200
        body = r.json()
        assert "AMICANA" in body["mensaje"] or "funcionando" in body["mensaje"]


class TestMisCuotas:

    def test_estructura_respuesta(self):
        cur = _cur(one={"id": 99}, all_=[])
        with patch("app.routers.pagos.get_connection", return_value=_conn(cur)):
            r = client.get("/mis-cuotas", headers=_alumno_header())
        assert r.status_code == 200
        body = r.json()
        for k in ("ok", "cuotas", "pendientes", "vencidas", "pagadas", "deuda_total"):
            assert k in body

    def test_lista_vacia_deuda_cero(self):
        cur = _cur(one={"id": 99}, all_=[])
        with patch("app.routers.pagos.get_connection", return_value=_conn(cur)):
            r = client.get("/mis-cuotas", headers=_alumno_header())
        assert r.status_code == 200
        assert r.json()["cuotas"] == []
        assert r.json()["deuda_total"] == 0.0

    def test_cuotas_pendientes_y_pagadas_se_separan(self):
        cuotas = [
            {"id": 1, "alumno_id": 99, "concepto": "Marzo", "monto": 5000,
             "fecha_vencimiento": "2026-03-31", "estado": "pendiente",
             "preference_id": None, "fecha_creacion": None},
            {"id": 2, "alumno_id": 99, "concepto": "Febrero", "monto": 5000,
             "fecha_vencimiento": "2026-02-28", "estado": "pagada",
             "preference_id": None, "fecha_creacion": None},
        ]
        cur = _cur(one={"id": 99}, all_=cuotas)
        with patch("app.routers.pagos.get_connection", return_value=_conn(cur)):
            r = client.get("/mis-cuotas", headers=_alumno_header())
        assert r.status_code == 200
        body = r.json()
        assert body["pendientes"] == 1
        assert body["pagadas"] == 1
        assert body["deuda_total"] == 5000.0

    def test_sin_token_401(self):
        r = client.get("/mis-cuotas")
        assert r.status_code == 401


class TestCrearPagoValidacion:

    def test_monto_cero_rechazado(self):
        r = client.post("/crear-pago",
                        json={"titulo": "Test", "monto": 0, "cantidad": 1, "email": "t@t.com"},
                        headers=_alumno_header())
        # monto se valida en Pydantic (Field gt=0) → 422 con detalle por campo
        assert r.status_code == 422
        campos = [e["campo"] for e in r.json()["errores"]]
        assert "monto" in campos

    def test_monto_negativo_rechazado(self):
        r = client.post("/crear-pago",
                        json={"titulo": "Test", "monto": -100, "cantidad": 1, "email": "t@t.com"},
                        headers=_alumno_header())
        assert r.status_code == 422

    def test_sin_token_401(self):
        r = client.post("/crear-pago",
                        json={"titulo": "Test", "monto": 100, "cantidad": 1, "email": "t@t.com"})
        assert r.status_code == 401
