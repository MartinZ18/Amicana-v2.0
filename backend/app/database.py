"""Conexión MySQL.

Las credenciales se leen de variables de entorno (.env). En desarrollo
local, los defaults coinciden con la instalación típica que veníamos
usando (root/root @ localhost) — pero en producción TODAS las variables
deben estar definidas explícitamente.
"""
import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))


def get_connection():
    """Abre una conexión nueva a MySQL. El caller es responsable de cerrarla."""
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", "root"),
        database=os.environ.get("DB_NAME", "gestion_facturas_amicana"),
    )
