-- Migration 002: cursos y datos adicionales de alumno
-- Este archivo solo es necesario si ya tenes la BD anterior sin estos cambios.
-- Si usas BD_Amicana.sql desde cero, NO corras este archivo.

USE gestion_facturas_amicana;

CREATE TABLE IF NOT EXISTS cursos (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    nombre      VARCHAR(100) NOT NULL UNIQUE,
    descripcion VARCHAR(255) NULL,
    monto_cuota DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    activo      BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en   DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS dni      VARCHAR(10) NULL UNIQUE,
    ADD COLUMN IF NOT EXISTS telefono VARCHAR(20) NULL,
    ADD COLUMN IF NOT EXISTS curso_id INT NULL,
    ADD CONSTRAINT IF NOT EXISTS fk_usuarios_curso
        FOREIGN KEY (curso_id) REFERENCES cursos(id) ON DELETE SET NULL;

ALTER TABLE cuotas
    ADD COLUMN IF NOT EXISTS comprobante_manual    VARCHAR(100) NULL,
    ADD COLUMN IF NOT EXISTS confirmado_por_alumno BOOLEAN NOT NULL DEFAULT FALSE;
