from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.auth import create_access_token

client = TestClient(app)

def _admin_header():
    token = create_access_token({"sub": "admin@amicana.com", "rol": "admin", "id": 1})
    return {"Authorization": f"Bearer {token}"}

def _alumno_header():
    token = create_access_token({"sub": "alumno@test.com", "rol": "alumno", "id": 2})
    return {"Authorization": f"Bearer {token}"}

def _mock_cursor(fetchone_val=None, fetchall_val=None, lastrowid=1, rowcount=1):
    c = MagicMock()
    c.fetchone.return_value = fetchone_val
    c.fetchall.return_value = fetchall_val or []
    c.lastrowid = lastrowid
    c.rowcount = rowcount
    return c

def _mock_conn(cursor):
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


class TestCursosCRUD:

    def test_listar_cursos(self):
        cursos = [{"id": 1, "nombre": "Inglés B1", "descripcion": None, "monto_cuota": 45000, "activo": True}]
        cursor = _mock_cursor(fetchall_val=cursos)
        with patch("app.routers.cursos.get_connection", return_value=_mock_conn(cursor)):
            r = client.get("/cursos", headers=_admin_header())
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert len(r.json()["cursos"]) == 1

    def test_crear_curso(self):
        cursor = _mock_cursor(lastrowid=5)
        with patch("app.routers.cursos.get_connection", return_value=_mock_conn(cursor)):
            r = client.post("/cursos", json={"nombre": "Inglés B1", "monto_cuota": 45000}, headers=_admin_header())
        assert r.status_code == 200
        assert r.json()["id"] == 5

    def test_crear_curso_requiere_admin(self):
        r = client.post("/cursos", json={"nombre": "X", "monto_cuota": 1000}, headers=_alumno_header())
        assert r.status_code == 403

    def test_editar_curso(self):
        existing = {"id": 1, "nombre": "Inglés B1", "descripcion": None, "monto_cuota": 45000,
                    "modalidad": "presencial", "categoria": "regular", "activo": True}
        cursor = _mock_cursor(fetchone_val=existing)
        with patch("app.routers.cursos.get_connection", return_value=_mock_conn(cursor)):
            r = client.put("/cursos/1", json={"monto_cuota": 50000}, headers=_admin_header())
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_editar_curso_inexistente(self):
        cursor = _mock_cursor(fetchone_val=None)
        with patch("app.routers.cursos.get_connection", return_value=_mock_conn(cursor)):
            r = client.put("/cursos/999", json={"nombre": "XY"}, headers=_admin_header())
        assert r.status_code == 404

    def test_eliminar_curso(self):
        cursor = _mock_cursor(rowcount=1)
        with patch("app.routers.cursos.get_connection", return_value=_mock_conn(cursor)):
            r = client.delete("/cursos/1", headers=_admin_header())
        assert r.status_code == 200

    def test_eliminar_curso_inexistente(self):
        cursor = _mock_cursor(rowcount=0)
        with patch("app.routers.cursos.get_connection", return_value=_mock_conn(cursor)):
            r = client.delete("/cursos/999", headers=_admin_header())
        assert r.status_code == 404
