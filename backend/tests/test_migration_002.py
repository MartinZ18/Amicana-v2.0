"""
Tests for database/migrations/002_cursos_y_alumno_datos.sql.
Validates SQL content and ordering without requiring a live database.
"""
import os

MIGRATION = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "database", "migrations", "002_cursos_y_alumno_datos.sql")
)


def _sql():
    with open(MIGRATION, encoding="utf-8") as f:
        return f.read().lower()


class TestMigration002:

    def test_file_exists(self):
        assert os.path.isfile(MIGRATION)

    def test_creates_table_cursos(self):
        sql = _sql()
        assert "create table" in sql and "cursos" in sql

    def test_cursos_columns_present(self):
        sql = _sql()
        for col in ["nombre", "descripcion", "monto_cuota", "activo"]:
            assert col in sql, f"columna '{col}' falta en cursos"

    def test_usuarios_altered(self):
        assert "alter table usuarios" in _sql()

    def test_usuarios_gets_dni(self):
        assert "dni" in _sql()

    def test_usuarios_gets_telefono(self):
        assert "telefono" in _sql()

    def test_usuarios_gets_curso_id(self):
        assert "curso_id" in _sql()

    def test_usuarios_has_foreign_key_to_cursos(self):
        sql = _sql()
        assert "foreign key" in sql and "cursos" in sql

    def test_cuotas_altered(self):
        assert "alter table cuotas" in _sql()

    def test_cuotas_gets_comprobante_manual(self):
        assert "comprobante_manual" in _sql()

    def test_cuotas_gets_confirmado_por_alumno(self):
        assert "confirmado_por_alumno" in _sql()

    def test_cursos_created_before_usuarios_fk(self):
        sql = _sql()
        assert sql.index("create table") < sql.index("alter table usuarios"), \
            "cursos debe crearse antes de agregar el FK en usuarios"
