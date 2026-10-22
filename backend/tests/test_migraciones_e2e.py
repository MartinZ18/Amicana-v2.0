"""Migraciones incrementales contra un servidor MySQL/MariaDB real.

Se omite salvo que MIG_DB_PORT apunte a un servidor local descartable y
MIG_DB_DISPOSABLE=1: el test borra y recrea la BD gestion_facturas_amicana.
Variables: MIG_DB_HOST (default 127.0.0.1), MIG_DB_PORT, MIG_DB_USER (default
root), MIG_DB_PASSWORD.

    MIG_DB_PORT=3327 MIG_DB_DISPOSABLE=1 MIG_DB_PASSWORD=... python -m pytest tests/test_migraciones_e2e.py -v

Escenario: una instalación vieja (schema canónico sin las columnas que agregan
las migraciones, `niveles` y `progreso_alumno` en un formato anterior, con datos
cargados) se actualiza aplicando todas las migraciones en orden, tal como están
en disco. Las tablas en formato anterior se reemplazan por las actuales. Después
se carga progreso de un alumno y se aplican otra vez: deben ser idempotentes,
dejar el mismo schema y no tocar los datos existentes, progreso incluido.
"""
import os
import secrets

import mysql.connector
import pytest

MIG_PORT = os.environ.get("MIG_DB_PORT")
MIG_DISPOSABLE = os.environ.get("MIG_DB_DISPOSABLE") == "1"
MIG_HOST = os.environ.get("MIG_DB_HOST", "127.0.0.1")
DB_NAME = "gestion_facturas_amicana"

pytestmark = [
    pytest.mark.skipif(
        not (MIG_PORT and MIG_DISPOSABLE),
        reason="MIG_DB_PORT y MIG_DB_DISPOSABLE=1 no definidos: test E2E de migraciones omitido",
    ),
    pytest.mark.skipif(
        MIG_HOST not in ("127.0.0.1", "localhost"),
        reason="el test borra la BD: solo corre contra un servidor local",
    ),
]

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCHEMA = os.path.join(ROOT, "database", "BD_Amicana.sql")
MIGRATIONS_DIR = os.path.join(ROOT, "database", "migrations")

# Columnas que agregan las migraciones; una instalación vieja no las tiene.
COLUMNAS_NUEVAS = {
    "pagos": ["comprobante_manual", "confirmado_por_alumno", "fecha_confirmacion_manual"],
    "usuarios": ["dni", "telefono", "curso_id", "apellido", "google_id", "auth_provider", "modalidad"],
    "cursos": ["modalidad", "categoria"],
    "cuotas": ["comprobante_manual", "confirmado_por_alumno", "pdf_url"],
    "chat_sessions": ["history"],
}


def _connect():
    return mysql.connector.connect(
        host=MIG_HOST,
        port=int(MIG_PORT),
        user=os.environ.get("MIG_DB_USER", "root"),
        password=os.environ.get("MIG_DB_PASSWORD", ""),
        autocommit=True,
    )


def _statements(path):
    """Parte un .sql en sentencias como lo haría el cliente mysql (sin DELIMITER).

    El archivo se lee tal cual: un BOM al principio llega al servidor y falla,
    igual que con `mysql < archivo`.
    """
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    buf = []
    for line in lines:
        stripped = line.strip()
        if not buf and (not stripped or stripped.startswith("--")):
            continue
        if stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.endswith(";"):
            yield "\n".join(buf)
            buf = []
    if "".join(buf).strip():
        yield "\n".join(buf)


def _run_file(conn, path):
    cur = conn.cursor()
    for stmt in _statements(path):
        try:
            cur.execute(stmt)
            if cur.with_rows:
                cur.fetchall()
        except mysql.connector.Error as exc:
            pytest.fail(f"{os.path.basename(path)} falló en:\n{stmt}\n-> {exc}")
    cur.close()


def _migrations():
    return sorted(
        os.path.join(MIGRATIONS_DIR, name)
        for name in os.listdir(MIGRATIONS_DIR)
        if name.endswith(".sql")
    )


def _query(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return rows


def _schema_snapshot(conn):
    columnas = _query(conn, """
        SELECT table_name, column_name, column_type, is_nullable, column_default
          FROM information_schema.columns WHERE table_schema = %s
         ORDER BY table_name, ordinal_position""", (DB_NAME,))
    indices = _query(conn, """
        SELECT table_name, index_name, non_unique, column_name
          FROM information_schema.statistics WHERE table_schema = %s
         ORDER BY table_name, index_name, seq_in_index""", (DB_NAME,))
    fks = _query(conn, """
        SELECT table_name, constraint_name, referenced_table_name, delete_rule
          FROM information_schema.referential_constraints WHERE constraint_schema = %s
         ORDER BY table_name, constraint_name""", (DB_NAME,))
    return columnas, indices, fks


def _columnas(conn, tabla):
    return {
        row[0]: row[1:]
        for row in _query(conn, """
            SELECT column_name, column_type, is_nullable, column_default
              FROM information_schema.columns
             WHERE table_schema = %s AND table_name = %s""", (DB_NAME, tabla))
    }


def _instalacion_vieja(conn):
    """Schema canónico sin las columnas nuevas y con password NOT NULL, como antes de 006."""
    hay_usuarios = _query(conn, """
        SELECT COUNT(*) FROM information_schema.tables
         WHERE table_schema = %s AND table_name = 'usuarios'""", (DB_NAME,))[0][0]
    if hay_usuarios:
        ajenos = _query(
            conn, f"SELECT COUNT(*) FROM {DB_NAME}.usuarios WHERE email NOT LIKE %s",
            ("%@amicana-mig-e2e.com",))[0][0]
        if ajenos:
            pytest.fail(f"{DB_NAME} tiene {ajenos} usuarios que no creó este test: no la borro")
    cur = conn.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
    cur.close()
    _run_file(conn, SCHEMA)
    cur = conn.cursor()
    cur.execute(f"USE {DB_NAME}")
    for tabla, columnas in COLUMNAS_NUEVAS.items():
        existentes = _columnas(conn, tabla)
        faltan = [c for c in columnas if c not in existentes]
        assert not faltan, f"BD_Amicana.sql ya no tiene {tabla}.{faltan}: actualizar el test"
    cur.execute("ALTER TABLE usuarios DROP FOREIGN KEY fk_usuarios_curso")
    for tabla, columnas in COLUMNAS_NUEVAS.items():
        cur.execute(f"ALTER TABLE {tabla} " + ", ".join(f"DROP COLUMN {c}" for c in columnas))
    email = f"vieja-{secrets.token_hex(4)}@amicana-mig-e2e.com"
    cur.execute(
        "INSERT INTO usuarios (nombre, email, password, rol) VALUES (%s, %s, %s, 'alumno')",
        ("Alumna Vieja", email, "hash-existente"),
    )
    alumno_id = cur.lastrowid
    cur.execute("ALTER TABLE usuarios MODIFY COLUMN password VARCHAR(255) NOT NULL")
    # Formato anterior de niveles/progreso (sin codigo/orden ni modulos_completados).
    cur.execute("DROP TABLE progreso_alumno")
    cur.execute("DROP TABLE niveles")
    cur.execute("CREATE TABLE niveles (id INT AUTO_INCREMENT PRIMARY KEY, nombre VARCHAR(50) NOT NULL)")
    cur.execute("""CREATE TABLE progreso_alumno (
        id INT AUTO_INCREMENT PRIMARY KEY, alumno_id INT NOT NULL, nivel_id INT NULL,
        FOREIGN KEY (alumno_id) REFERENCES usuarios(id),
        FOREIGN KEY (nivel_id) REFERENCES niveles(id))""")
    cur.execute("INSERT INTO niveles (nombre) VALUES ('Inicial')")
    cur.execute("INSERT INTO progreso_alumno (alumno_id, nivel_id) VALUES (%s, %s)",
                (alumno_id, cur.lastrowid))
    cur.close()
    return alumno_id, email


def test_upgrade_de_instalacion_vieja_es_completo_e_idempotente():
    conn = _connect()
    try:
        alumno_id, email = _instalacion_vieja(conn)
        usuario_antes = _query(
            conn, f"SELECT id, nombre, email, password, rol FROM {DB_NAME}.usuarios WHERE id = %s",
            (alumno_id,))

        for path in _migrations():
            _run_file(conn, path)
        primera = _schema_snapshot(conn)

        for tabla, columnas in COLUMNAS_NUEVAS.items():
            existentes = _columnas(conn, tabla)
            faltan = [c for c in columnas if c not in existentes]
            assert not faltan, f"después de migrar faltan {tabla}.{faltan}"

        usuarios = _columnas(conn, "usuarios")
        assert usuarios["password"][1] == "YES", "006 debe permitir password NULL"
        # MariaDB informa el default entre comillas ('local'); MySQL, sin ellas.
        assert usuarios["auth_provider"][2].strip("'") == "local"
        unicos = {
            row[0] for row in _query(conn, """
                SELECT column_name FROM information_schema.statistics
                 WHERE table_schema = %s AND table_name = 'usuarios' AND non_unique = 0""",
                (DB_NAME,))
        }
        assert {"dni", "google_id"} <= unicos, f"dni y google_id deben ser únicos: {unicos}"
        fk = _query(conn, """
            SELECT referenced_table_name, delete_rule FROM information_schema.referential_constraints
             WHERE constraint_schema = %s AND constraint_name = 'fk_usuarios_curso'""", (DB_NAME,))
        assert fk == [("cursos", "SET NULL")], f"fk_usuarios_curso: {fk}"
        indice = _query(conn, """
            SELECT column_name FROM information_schema.statistics
             WHERE table_schema = %s AND table_name = 'cursos'
               AND index_name = 'idx_cursos_categoria_modalidad' ORDER BY seq_in_index""", (DB_NAME,))
        assert indice == [("categoria",), ("modalidad",)], f"idx_cursos_categoria_modalidad: {indice}"

        assert {"codigo", "orden"} <= set(_columnas(conn, "niveles")), "niveles quedó en formato anterior"
        assert {"modulos_completados", "fecha_proximo_examen"} <= set(_columnas(conn, "progreso_alumno")), \
            "progreso_alumno quedó en formato anterior"
        niveles = _query(conn, f"SELECT codigo FROM {DB_NAME}.niveles ORDER BY orden")
        assert niveles == [("A1",), ("A2",), ("B1",), ("B2",), ("C1",), ("C2",)], f"niveles: {niveles}"

        cur = conn.cursor()
        cur.execute(f"""INSERT INTO {DB_NAME}.progreso_alumno (alumno_id, nivel_id, modulos_completados)
                        SELECT %s, id, 3 FROM {DB_NAME}.niveles WHERE codigo = 'B1'""", (alumno_id,))
        cur.close()
        progreso_antes = _query(conn, f"""
            SELECT p.alumno_id, n.codigo, p.modulos_completados
              FROM {DB_NAME}.progreso_alumno p JOIN {DB_NAME}.niveles n ON n.id = p.nivel_id""")
        assert progreso_antes == [(alumno_id, "B1", 3)]

        for path in _migrations():
            _run_file(conn, path)
        assert _schema_snapshot(conn) == primera, "la segunda pasada cambió el schema"

        progreso_despues = _query(conn, f"""
            SELECT p.alumno_id, n.codigo, p.modulos_completados
              FROM {DB_NAME}.progreso_alumno p JOIN {DB_NAME}.niveles n ON n.id = p.nivel_id""")
        assert progreso_despues == progreso_antes, "la segunda pasada borró el progreso de los alumnos"
        assert _query(conn, f"SELECT COUNT(*) FROM {DB_NAME}.niveles")[0][0] == 6

        usuario_despues = _query(
            conn, f"SELECT id, nombre, email, password, rol FROM {DB_NAME}.usuarios WHERE id = %s",
            (alumno_id,))
        assert usuario_despues == usuario_antes, "las migraciones modificaron un usuario existente"
        proveedor = _query(
            conn, f"SELECT auth_provider FROM {DB_NAME}.usuarios WHERE email = %s", (email,))
        assert proveedor == [("local",)]
    finally:
        conn.close()
