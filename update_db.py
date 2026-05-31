import sys
import os

# Añadir el path del backend al PYTHONPATH
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from app.database import get_connection

def main():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Añadir columna external_reference si no existe
        print("Verificando/Añadiendo columna external_reference a pagos_mp...")
        try:
            cursor.execute("ALTER TABLE pagos_mp ADD COLUMN external_reference VARCHAR(100) NULL AFTER preference_id;")
            print("Columna añadida exitosamente.")
        except Exception as e:
            if "Duplicate column name" in str(e):
                print("La columna ya existe. Todo bien.")
            else:
                print(f"Error al añadir columna: {e}")

        # Añadir curso Inglés Básico con monto 100 ARS
        print("Creando/Actualizando curso Inglés Básico...")
        cursor.execute("SELECT id FROM cursos WHERE nombre = %s", ("Inglés Básico",))
        curso = cursor.fetchone()
        
        if curso:
            cursor.execute("UPDATE cursos SET monto_cuota = 100.00 WHERE id = %s", (curso[0],))
            print("Curso existente, monto actualizado a 100.00 ARS.")
        else:
            cursor.execute("""
                INSERT INTO cursos (nombre, descripcion, monto_cuota, modalidad, categoria, activo) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """, ("Inglés Básico", "Curso de prueba para pagos MP", 100.00, "virtual", "regular", True))
            print("Curso creado con éxito.")

        conn.commit()
        print("Operaciones de BD finalizadas correctamente.")

    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()
