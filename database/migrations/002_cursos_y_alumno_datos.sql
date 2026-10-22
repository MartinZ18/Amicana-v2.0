-- Migration 002: cursos y datos adicionales de alumno
-- Este archivo solo es necesario si ya tenes la BD anterior sin estos cambios.
-- Si usas BD_Amicana.sql desde cero, NO corras este archivo.
-- Idempotente y compatible con MySQL 8 y MariaDB (no usa ADD COLUMN IF NOT EXISTS,
-- que es solo MariaDB): consulta information_schema antes de cada cambio.

USE gestion_facturas_amicana;

CREATE TABLE IF NOT EXISTS cursos (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    nombre      VARCHAR(100) NOT NULL UNIQUE,
    descripcion VARCHAR(255) NULL,
    monto_cuota DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    activo      BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en   DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'usuarios'
        AND column_name = 'dni') = 0,
    'ALTER TABLE usuarios ADD COLUMN dni VARCHAR(10) NULL UNIQUE',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'usuarios'
        AND column_name = 'telefono') = 0,
    'ALTER TABLE usuarios ADD COLUMN telefono VARCHAR(20) NULL',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'usuarios'
        AND column_name = 'curso_id') = 0,
    'ALTER TABLE usuarios ADD COLUMN curso_id INT NULL',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.table_constraints
      WHERE table_schema = DATABASE() AND table_name = 'usuarios'
        AND constraint_name = 'fk_usuarios_curso' AND constraint_type = 'FOREIGN KEY') = 0,
    'ALTER TABLE usuarios ADD CONSTRAINT fk_usuarios_curso FOREIGN KEY (curso_id) REFERENCES cursos(id) ON DELETE SET NULL',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'cuotas'
        AND column_name = 'comprobante_manual') = 0,
    'ALTER TABLE cuotas ADD COLUMN comprobante_manual VARCHAR(100) NULL',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'cuotas'
        AND column_name = 'confirmado_por_alumno') = 0,
    'ALTER TABLE cuotas ADD COLUMN confirmado_por_alumno BOOLEAN NOT NULL DEFAULT FALSE',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
