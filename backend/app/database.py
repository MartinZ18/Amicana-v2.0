"""Conexión MySQL.

Las credenciales se leen de variables de entorno (.env). En desarrollo
local, los defaults coinciden con la instalación típica que veníamos
usando (root/root @ localhost) — pero en producción TODAS las variables
deben estar definidas explícitamente.

Las conexiones salen de un pool (mysql.connector.pooling). El contrato para
los callers no cambia: `conn = get_connection()` ... `conn.close()`, solo que
`close()` devuelve la conexión al pool en vez de cerrar el socket. Al devolverla
se hace reset de sesión (COM_RESET_CONNECTION): revierte cualquier transacción
abierta y restaura autocommit, así que el próximo usuario recibe una conexión limpia.

Variables opcionales:
  DB_POOL_SIZE      tamaño del pool (default 5, rango 1-32)
  DB_POOL_WAIT_MS   cuánto esperar una conexión libre si el pool está agotado
                    antes de abrir una conexión directa de emergencia (default 1000)
"""
import os
import threading
import time

import mysql.connector
from mysql.connector.errors import PoolError
from mysql.connector.pooling import MySQLConnectionPool, PooledMySQLConnection
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

_pool = None
_pool_lock = threading.Lock()


def _config() -> dict:
    return dict(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", "root"),
        database=os.environ.get("DB_NAME", "gestion_facturas_amicana"),
    )


def _pool_size() -> int:
    try:
        size = int(os.environ.get("DB_POOL_SIZE", "5"))
    except ValueError:
        size = 5
    return max(1, min(size, 32))


def _pool_wait_ms() -> int:
    try:
        wait = int(os.environ.get("DB_POOL_WAIT_MS", "1000"))
    except ValueError:
        wait = 1000
    return max(0, wait)


class _PooledConnection(PooledMySQLConnection):
    """Conexión del pool que se devuelve sola si el caller nunca llega a close().

    Varios callers cierran la conexión fuera de un `finally`; sin esto, cada
    error en esos caminos filtraría una conexión hasta agotar el pool.
    """

    def close(self):
        cnx = self.__dict__.get("_cnx")
        if cnx is None:
            return  # ya devuelta: close() doble es inofensivo, como antes
        try:
            if getattr(cnx, "unread_result", False):
                cnx.consume_results()
        except mysql.connector.Error:
            pass
        try:
            super().close()
        except mysql.connector.Error:
            # Socket muerto (p. ej. MySQL reiniciado): el reset de sesión falla, pero el
            # trabajo del request ya terminó. Antes del pool, close() no fallaba acá.
            pass

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


def _get_pool() -> MySQLConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:  # si la creación falla (BD caída) no queda cacheada
                _pool = MySQLConnectionPool(
                    pool_name="amicana", pool_size=_pool_size(), **_config()
                )
    return _pool


def reset_pool() -> None:
    """Cierra el pool; el próximo get_connection() crea uno nuevo (tests/cambio de config)."""
    global _pool
    with _pool_lock:
        pool, _pool = _pool, None
    if pool is not None:
        pool._remove_connections()


def get_connection():
    """Toma una conexión del pool. El caller debe llamar close() para devolverla.

    Si el pool está agotado espera DB_POOL_WAIT_MS y, de seguir agotado, abre una
    conexión directa (no pooleada) para no tumbar el request: es el comportamiento
    previo al pool.
    """
    pool = _get_pool()
    deadline = time.monotonic() + _pool_wait_ms() / 1000
    while True:
        try:
            cnx = pool.get_connection()
            cnx.__class__ = _PooledConnection
            return cnx
        except PoolError:
            if time.monotonic() >= deadline:
                break
            time.sleep(0.01)
    print("⚠️  Pool de conexiones agotado: se abre una conexión directa")
    return mysql.connector.connect(**_config())
