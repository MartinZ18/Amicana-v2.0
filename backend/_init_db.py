"""Script auxiliar: aplica BD_Amicana.sql contra la base configurada en .env.

Uso:
    cd backend
    python _init_db.py
"""
import os
import sys

from dotenv import load_dotenv
import mysql.connector

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

host     = os.environ.get("DB_HOST", "localhost")
port     = int(os.environ.get("DB_PORT", 3306))
user     = os.environ.get("DB_USER", "root")
password = os.environ.get("DB_PASSWORD", "")

sql_path = os.path.join(os.path.dirname(__file__), "..", "database", "BD_Amicana.sql")
if not os.path.exists(sql_path):
    print("ERROR: no se encontró database/BD_Amicana.sql")
    sys.exit(1)

with open(sql_path, encoding="utf-8") as f:
    sql = f.read()

statements = []
current = []
for line in sql.split("\n"):
    stripped = line.strip()
    if stripped.startswith("--") or stripped == "":
        continue
    current.append(line)
    if stripped.endswith(";"):
        statements.append("\n".join(current))
        current = []

try:
    conn = mysql.connector.connect(host=host, port=port, user=user, password=password)
except mysql.connector.Error as e:
    print(f"ERROR de conexión MySQL: {e}")
    sys.exit(1)

cursor = conn.cursor()
for stmt in statements:
    try:
        cursor.execute(stmt)
        try:
            cursor.fetchall()
        except Exception:
            pass
    except Exception as e:
        if "1065" not in str(e):
            print(f"WARN: {str(e)[:80]}")

conn.commit()
conn.close()

conn2 = mysql.connector.connect(
    host=host, port=port, user=user, password=password,
    database="gestion_facturas_amicana",
)
cur2 = conn2.cursor()
cur2.execute(
    "SELECT COUNT(*) FROM information_schema.tables "
    "WHERE table_schema = 'gestion_facturas_amicana'"
)
count = cur2.fetchone()[0]
conn2.close()
print(f"BD lista — {count} tablas creadas")
