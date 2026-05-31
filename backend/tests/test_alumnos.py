from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.auth import create_access_token

client = TestClient(app)
_STUB_PASS = "pytest-stub-pw"

def _header(rol="admin", uid=1, email="admin@amicana.com"):
    t = create_access_token({"sub": email, "rol": rol, "id": uid})
    return {"Authorization": f"Bearer {t}"}

def _cur(one=None, all_=None, lastrowid=1, rowcount=1):
    c = MagicMock()
    c.fetchone.return_value = one
    c.fetchall.return_value = all_ or []
    c.lastrowid = lastrowid
    c.rowcount = rowcount
    return c

def _conn(cur):
    conn = MagicMock(); conn.cursor.return_value = cur; return conn


class TestAlumnosCRUD:

    def test_crear_alumno(self):
        cur = _cur(lastrowid=10)
        with patch("app.routers.alumnos.get_connection", return_value=_conn(cur)):
            r = client.post("/alumnos", json={
                "nombre": "Juan", "apellido": "Pérez", "email": "j@mail.com",
                "dni": "35000001", "telefono": "3514000000", "curso_id": 1,
                "modalidad": "presencial",
            }, headers=_header())
        assert r.status_code == 200
        assert r.json()["id"] == 10

    def test_crear_alumno_sin_permisos(self):
        r = client.post("/alumnos", json={"nombre": "X", "email": "x@x.com", "password": "x"}, headers=_header(rol="alumno"))
        assert r.status_code == 403

    def test_obtener_alumno(self):
        alumno = {"id": 5, "nombre": "Juan", "email": "j@mail.com", "dni": "35000001", "telefono": None, "curso_id": 1, "curso": "Inglés B1"}
        cur = _cur(one=alumno)
        with patch("app.routers.alumnos.get_connection", return_value=_conn(cur)):
            r = client.get("/alumnos/5", headers=_header())
        assert r.status_code == 200
        assert r.json()["alumno"]["nombre"] == "Juan"

    def test_obtener_alumno_inexistente(self):
        cur = _cur(one=None)
        with patch("app.routers.alumnos.get_connection", return_value=_conn(cur)):
            r = client.get("/alumnos/999", headers=_header())
        assert r.status_code == 404

    def test_editar_alumno(self):
        existing = {"id": 5, "nombre": "Juan", "email": "juan@mail.com",
                    "dni": None, "telefono": None, "curso_id": None}
        cur = _cur(one=existing)
        with patch("app.routers.alumnos.get_connection", return_value=_conn(cur)):
            r = client.put("/alumnos/5", json={"telefono": "3514000000"}, headers=_header())
        assert r.status_code == 200

    def test_eliminar_alumno(self):
        cur = _cur(rowcount=1)
        with patch("app.routers.alumnos.get_connection", return_value=_conn(cur)):
            r = client.delete("/alumnos/5", headers=_header())
        assert r.status_code == 200

    def test_eliminar_alumno_inexistente(self):
        cur = _cur(rowcount=0)
        with patch("app.routers.alumnos.get_connection", return_value=_conn(cur)):
            r = client.delete("/alumnos/999", headers=_header())
        assert r.status_code == 404


class TestBuscarAlumno:

    def test_buscar_por_dni_encontrado(self):
        alumno = {"id": 5, "nombre": "Juan", "email": "j@mail.com", "dni": "35000001", "telefono": None, "curso": "Inglés B1", "monto_cuota": 45000}
        cur = _cur(one=alumno)
        with patch("app.routers.alumnos.get_connection", return_value=_conn(cur)):
            r = client.get("/alumnos/buscar?dni=35000001", headers=_header())
        assert r.status_code == 200
        assert r.json()["alumno"]["dni"] == "35000001"

    def test_buscar_dni_inexistente(self):
        cur = _cur(one=None)
        with patch("app.routers.alumnos.get_connection", return_value=_conn(cur)):
            r = client.get("/alumnos/buscar?dni=00000000", headers=_header())
        assert r.status_code == 404

    def test_buscar_sin_parametros(self):
        r = client.get("/alumnos/buscar", headers=_header())
        assert r.status_code == 400


class TestCuotasPorAlumno:

    def test_resumen_con_deuda(self):
        cuota = {"id": 1, "concepto": "Cuota Mayo", "monto": 45000, "fecha_vencimiento": "2026-05-31", "estado": "pendiente"}
        cur = _cur(one={"id": 5}, all_=[cuota])
        with patch("app.routers.alumnos.get_connection", return_value=_conn(cur)):
            r = client.get("/alumnos/5/cuotas", headers=_header())
        assert r.status_code == 200
        data = r.json()
        assert data["resumen"]["estado"] == "Con deuda"
        assert data["resumen"]["cuotas_pendientes"] == 1

    def test_alumno_inexistente(self):
        cur = _cur(one=None)
        with patch("app.routers.alumnos.get_connection", return_value=_conn(cur)):
            r = client.get("/alumnos/999/cuotas", headers=_header())
        assert r.status_code == 404

    def test_alumno_no_puede_ver_cuotas_ajenas(self):
        """IDOR: alumno con id=99 no puede ver cuotas de alumno_id=5."""
        token_ajeno = create_access_token({"sub": "otro@test.com", "rol": "alumno", "id": 99})
        header_ajeno = {"Authorization": f"Bearer {token_ajeno}"}
        r = client.get("/alumnos/5/cuotas", headers=header_ajeno)
        assert r.status_code == 403

    def test_alumno_puede_ver_sus_propias_cuotas(self):
        """Alumno con id=5 sí puede ver SUS propias cuotas."""
        cuota = {"id": 1, "concepto": "Cuota Mayo", "monto": 45000,
                 "fecha_vencimiento": "2026-05-31", "estado": "pendiente"}
        cur = _cur(one={"id": 5}, all_=[cuota])
        token_propio = create_access_token({"sub": "alumno5@test.com", "rol": "alumno", "id": 5})
        header_propio = {"Authorization": f"Bearer {token_propio}"}
        with patch("app.routers.alumnos.get_connection", return_value=_conn(cur)):
            r = client.get("/alumnos/5/cuotas", headers=header_propio)
        assert r.status_code == 200


class TestMiPerfil:

    def test_perfil_propio(self):
        perfil = {"id": 2, "nombre": "Juan", "email": "j@mail.com", "rol": "alumno",
                  "dni": "35000001", "telefono": None, "modalidad": None,
                  "auth_provider": "local", "tiene_password_local": 1,
                  "curso": "Inglés B1", "modalidad_curso": None}
        cur = _cur(one=perfil)
        with patch("app.routers.perfil.get_connection", return_value=_conn(cur)):
            r = client.get("/perfil", headers=_header(rol="alumno", uid=2, email="j@mail.com"))
        assert r.status_code == 200
        assert r.json()["data"]["email"] == "j@mail.com"

    def test_sin_token_401(self):
        r = client.get("/perfil")
        assert r.status_code == 401
