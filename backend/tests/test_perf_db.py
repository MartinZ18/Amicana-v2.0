"""Medición de performance de acceso a BD (E2E contra una MySQL real).

Se omite salvo que PERF_DB_PORT apunte a una BD descartable ya cargada con
BD_Amicana.sql (+ migraciones). Variables: PERF_DB_HOST (default 127.0.0.1),
PERF_DB_PORT, PERF_DB_USER (default root), PERF_DB_PASSWORD, PERF_DB_NAME
(default gestion_facturas_amicana). NUNCA apuntar a una BD con datos reales:
el test borra y recrea los alumnos `perf*@seed.test`.

    PERF_DB_PORT=3307 PERF_DB_DISPOSABLE=1 PERF_DB_PASSWORD=... python -m pytest tests/test_perf_db.py -s

Mide, por request: sentencias SQL ejecutadas (cursor.execute/executemany) y
conexiones abiertas contra el servidor (delta de Connections).
"""
import datetime as dt
import os
import random
import time

import mysql.connector
import pytest

os.environ.setdefault("SECRET_KEY", "test_secret_key_for_pytest_only")
os.environ.setdefault("CHATBOT_INTERNAL_KEY", "amicana-internal")

PERF_PORT = os.environ.get("PERF_DB_PORT")
# El test borra y siembra datos: exige una confirmación explícita y un host local,
# para que un PERF_DB_PORT olvidado no alcance a apuntarlo a una BD con datos reales.
PERF_DISPOSABLE = os.environ.get("PERF_DB_DISPOSABLE") == "1"
PERF_HOST = os.environ.get("PERF_DB_HOST", "127.0.0.1")

pytestmark = [
    pytest.mark.skipif(
        not (PERF_PORT and PERF_DISPOSABLE),
        reason="PERF_DB_PORT y PERF_DB_DISPOSABLE=1 no definidos: test de performance omitido",
    ),
    pytest.mark.skipif(
        PERF_HOST not in ("127.0.0.1", "localhost"),
        reason="test de performance solo contra una BD local descartable",
    ),
]

N_ALUMNOS = 300
CUOTAS_POR_ALUMNO = 10
SEQ_REQUESTS = 50


def _db_kwargs():
    return dict(
        host=PERF_HOST,
        port=int(PERF_PORT or 0),
        user=os.environ.get("PERF_DB_USER", "root"),
        password=os.environ.get("PERF_DB_PASSWORD", ""),
        database=os.environ.get("PERF_DB_NAME", "gestion_facturas_amicana"),
    )


def seed(n_alumnos=N_ALUMNOS, por_alumno=CUOTAS_POR_ALUMNO):
    """Recrea de forma determinista los alumnos y cuotas de prueba."""
    conn = mysql.connector.connect(**_db_kwargs())
    cur = conn.cursor()
    cur.execute("DELETE FROM usuarios WHERE email LIKE 'perf%@seed.test'")
    cur.execute("ALTER TABLE usuarios AUTO_INCREMENT = 1000")
    cur.execute("ALTER TABLE cuotas AUTO_INCREMENT = 100000")
    cur.execute("SELECT id FROM cursos ORDER BY id LIMIT 3")
    cursos = [r[0] for r in cur.fetchall()] or [None]
    rnd = random.Random(42)
    today = dt.date.today()
    alumnos = [
        (f"Nombre{i}", f"Apellido{i:03d}", f"perf{i}@seed.test",
         f"{30000000 + i}", cursos[i % len(cursos)], "2026-01-01 00:00:00")
        for i in range(n_alumnos)
    ]
    cur.executemany(
        "INSERT INTO usuarios (nombre, apellido, email, dni, rol, curso_id, creado_en) "
        "VALUES (%s, %s, %s, %s, 'alumno', %s, %s)",
        [(n, a, e, d, c, ts) for n, a, e, d, c, ts in alumnos],
    )
    cur.execute("SELECT id FROM usuarios WHERE email LIKE 'perf%@seed.test' ORDER BY id")
    ids = [r[0] for r in cur.fetchall()]
    estados = ["pagada", "pendiente", "pendiente", "vencida", "pendiente_verificacion"]
    rows = []
    for aid in ids:
        for k in range(por_alumno):
            estado = rnd.choice(estados)
            if estado == "pendiente":
                # mitad ya vencidas por fecha (deben pasar a 'vencida' en la lectura)
                delta = rnd.choice([-90, -45, -10, -1, 5, 20, 60])
            elif estado == "vencida":
                delta = rnd.choice([-60, -30, -5])
            else:
                delta = rnd.choice([-30, 10, 40])
            rows.append((aid, f"Cuota {k + 1}", 1000 + 50 * k,
                         today + dt.timedelta(days=delta), estado,
                         f"pref-{aid}-{k}" if k == 0 else None))
    cur.executemany(
        "INSERT INTO cuotas (alumno_id, concepto, monto, fecha_vencimiento, estado, preference_id) "
        "VALUES (%s, %s, %s, %s, %s, %s)", rows)
    cur.execute("UPDATE cuotas SET fecha_creacion='2026-01-01 00:00:00' "
                "WHERE alumno_id IN (SELECT id FROM usuarios WHERE email LIKE 'perf%@seed.test')")
    conn.commit()
    conn.close()
    return ids


def _server_connections():
    conn = mysql.connector.connect(**_db_kwargs())
    cur = conn.cursor()
    cur.execute("SHOW GLOBAL STATUS LIKE 'Connections'")
    n = int(cur.fetchone()[1])
    conn.close()
    return n  # incluye esta conexión de medición (+1 constante)


def _cursor_classes():
    import mysql.connector.cursor as c
    classes, stack = [], [c.MySQLCursor]
    try:
        import mysql.connector.cursor_cext as cc
        stack.append(cc.CMySQLCursor)
    except ImportError:  # extensión C no disponible: cursor puro Python
        pass
    while stack:
        k = stack.pop()
        classes.append(k)
        stack.extend(k.__subclasses__())
    return classes


class Counter:
    """Cuenta sentencias (execute/executemany) mientras está activo."""

    def __init__(self):
        self.statements = 0
        self.log = []
        self._orig = []

    def __enter__(self):
        counter = self
        for k in _cursor_classes():
            for name in ("execute", "executemany"):
                if name in k.__dict__:
                    orig = k.__dict__[name]

                    def make(orig, name):
                        def wrapper(self_, operation, *a, **kw):
                            # El conector lanza por su cuenta "SELECT @@session.sql_mode"
                            # tras abrir/resetear una conexión: no es SQL de la app.
                            if "@@session.sql_mode" not in str(operation):
                                counter.statements += 1
                                counter.log.append((name, str(operation)[:80]))
                            return orig(self_, operation, *a, **kw)
                        return wrapper
                    setattr(k, name, make(orig, name))
                    self._orig.append((k, name, orig))
        return self

    def __exit__(self, *exc):
        for k, name, orig in self._orig:
            setattr(k, name, orig)


def _staff_headers():
    from app.auth import create_access_token
    t = create_access_token({"sub": "admin@amicana.com", "rol": "admin", "id": 1})
    return {"Authorization": f"Bearer {t}"}


CHATBOT = {"X-Chatbot-Key": os.environ.get("CHATBOT_INTERNAL_KEY", "amicana-internal")}


def endpoints(alumno_id):
    staff = _staff_headers()
    return {
        "alumnos_ficha": ("GET", "/alumnos/ficha?q=Apellido00", staff, None),
        "alumnos_listado": ("GET", "/alumnos", staff, None),
        "alumno_cuotas": ("GET", f"/alumnos/{alumno_id}/cuotas", staff, None),
        "reportes_resumen": ("GET", "/reportes/resumen", staff, None),
        "reportes_deudores": ("GET", "/reportes/deudores", staff, None),
        "reportes_cuotas_vencidas": ("GET", "/reportes/cuotas-vencidas", staff, None),
        "chatbot_estado_cuotas": ("GET", f"/chatbot/alumno/{alumno_id}/estado-cuotas", CHATBOT, None),
        "chatbot_aptitud_examen": ("GET", f"/chatbot/alumno/{alumno_id}/aptitud-examen", CHATBOT, None),
        "asignar_cuotas_12": ("POST", "/asignar-cuotas", staff, {
            "alumno_id": alumno_id,
            "cuotas": [{"alumno_id": alumno_id, "concepto": f"Bulk {i}", "monto": 1500.0,
                        "fecha_vencimiento": f"2027-{(i % 12) + 1:02d}-10"} for i in range(12)],
        }),
    }


def call(client, spec):
    method, path, headers, body = spec
    return client.request(method, path, headers=headers, json=body)


def measure(client, spec, n=SEQ_REQUESTS):
    """Devuelve (sentencias en 1 request, conexiones abiertas en n requests, segundos para n)."""
    with Counter() as one:
        r = call(client, spec)
    assert r.status_code == 200, (spec[1], r.status_code, r.text[:200])
    before = _server_connections()
    t0 = time.perf_counter()
    for _ in range(n):
        call(client, spec)
    wall = time.perf_counter() - t0
    opened = _server_connections() - before - 1  # -1: la conexión de medición
    return one.statements, opened, wall


@pytest.fixture(scope="module")
def env():
    from fastapi.testclient import TestClient
    p = _db_kwargs()
    saved = {k: os.environ.get(k) for k in
             ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME")}
    os.environ.update(DB_HOST=p["host"], DB_PORT=str(p["port"]), DB_USER=p["user"],
                      DB_PASSWORD=p["password"], DB_NAME=p["database"])
    # Un pool ya creado por otro test (mocks) apuntaría a otra BD.
    import app.database as database
    if hasattr(database, "reset_pool"):
        database.reset_pool()
    ids = seed()
    from app.main import app
    yield TestClient(app), ids
    if hasattr(database, "reset_pool"):
        database.reset_pool()
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


POOL_MAX = int(os.environ.get("DB_POOL_SIZE", "5"))


@pytest.mark.parametrize("name", [
    "alumnos_ficha", "alumnos_listado", "alumno_cuotas", "reportes_resumen",
    "reportes_deudores", "reportes_cuotas_vencidas", "chatbot_estado_cuotas",
    "chatbot_aptitud_examen", "asignar_cuotas_12",
])
def test_conexiones_acotadas_por_el_pool(env, name):
    client, ids = env
    spec = endpoints(ids[0])[name]
    stmts, opened, wall = measure(client, spec)
    print(f"\n[perf] {name}: {stmts} sentencias/request, {opened} conexiones nuevas en "
          f"{SEQ_REQUESTS} requests, {wall:.3f}s")
    assert opened <= POOL_MAX, (
        f"{name}: {opened} conexiones abiertas en {SEQ_REQUESTS} requests (pool={POOL_MAX})")


def test_update_vencidas_usa_indice(env):
    client, _ = env
    conn = mysql.connector.connect(**_db_kwargs())
    cur = conn.cursor(dictionary=True)
    # EXPLAIN de UPDATE: en MySQL 8 devuelve type/key como un SELECT.
    cur.execute("EXPLAIN UPDATE cuotas SET estado='vencida' "
                "WHERE estado='pendiente' AND fecha_vencimiento < CURDATE()")
    row = cur.fetchall()[0]
    cur.execute("EXPLAIN SELECT id FROM cuotas WHERE preference_id = 'x'")
    row_pref = cur.fetchall()[0]
    conn.close()
    print(f"\n[perf] EXPLAIN vencida UPDATE: type={row['type']} key={row['key']} rows={row['rows']}"
          f" | preference_id: type={row_pref['type']} key={row_pref['key']}")
    # Sin el índice MySQL recorre PRIMARY completo (type=index): key no nulo pero full scan.
    assert row["key"] == "idx_cuotas_estado_venc"
    assert row_pref["key"] == "idx_cuotas_preference"


def test_asignar_cuotas_inserta_las_mismas_filas_en_una_sentencia(env):
    client, ids = env
    aid = ids[1]
    conn = mysql.connector.connect(**_db_kwargs())
    conn.autocommit = True  # sin snapshot REPEATABLE READ: ver lo que commitea la app
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM cuotas WHERE alumno_id=%s", (aid,))
    antes = cur.fetchone()[0]
    spec = endpoints(aid)["asignar_cuotas_12"]
    with Counter() as c:
        r = call(client, spec)
    assert r.status_code == 200
    cur.execute("SELECT concepto, monto, fecha_vencimiento FROM cuotas "
                "WHERE alumno_id=%s AND concepto LIKE 'Bulk %%' ORDER BY id", (aid,))
    filas = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM cuotas WHERE alumno_id=%s", (aid,))
    despues = cur.fetchone()[0]
    conn.close()
    assert despues - antes == 12
    assert [f[0] for f in filas][-12:] == [f"Bulk {i}" for i in range(12)]
    inserts = [x for x in c.log if x[1].lstrip().upper().startswith("INSERT")]
    print(f"\n[perf] asignar-cuotas: {len(inserts)} llamadas INSERT para 12 cuotas")
    assert len(inserts) == 1
