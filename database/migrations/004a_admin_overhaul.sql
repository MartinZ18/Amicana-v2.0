-- Migration 004: rediseño del panel administrativo
-- Target DB : gestion_facturas_amicana
-- Run once  : mysql -u root -p gestion_facturas_amicana < database/migrations/004a_admin_overhaul.sql
--
-- Cambios:
--   - DROP de módulos eliminados (facturas IA, auditoría, análisis CUIT).
--   - DROP de niveles y progreso_alumno solo si están en el formato anterior
--     (la 008 los vuelve a crear); si ya tienen el formato actual, se conservan con sus datos.
--   - ALTER usuarios: agrega columna `apellido` separada del `nombre`.
--   - CREATE calendario_clases (clases del calendario por curso).
--   - CREATE comunicados (comunicaciones internas del staff, no visibles al alumno).

USE gestion_facturas_amicana;


-- ── DROP de módulos eliminados ───────────────────────────────────────────────

DROP TABLE IF EXISTS analisis_pagos;
DROP TABLE IF EXISTS facturas_ia;
DROP TABLE IF EXISTS facturas;
DROP TABLE IF EXISTS auditoria;


-- ── niveles / progreso_alumno: solo el formato anterior ─────────────────────
-- Formato actual (el que crea la 008): niveles con `codigo` y `orden`;
-- progreso_alumno con `modulos_completados` y `fecha_proximo_examen`.
-- Una tabla que existe sin esas columnas es del formato anterior y se borra.
-- progreso_alumno también se borra si niveles es del formato anterior, porque
-- su FK apunta a niveles y sus nivel_id dejan de tener sentido.

SET @niveles_anterior := (
    SELECT COUNT(*) FROM information_schema.tables
     WHERE table_schema = DATABASE() AND table_name = 'niveles') = 1
  AND (
    SELECT COUNT(*) FROM information_schema.columns
     WHERE table_schema = DATABASE() AND table_name = 'niveles'
       AND column_name IN ('codigo', 'orden')) < 2;

SET @progreso_anterior := (
    SELECT COUNT(*) FROM information_schema.tables
     WHERE table_schema = DATABASE() AND table_name = 'progreso_alumno') = 1
  AND (
    SELECT COUNT(*) FROM information_schema.columns
     WHERE table_schema = DATABASE() AND table_name = 'progreso_alumno'
       AND column_name IN ('modulos_completados', 'fecha_proximo_examen')) < 2;

SET @sql := IF(@progreso_anterior OR @niveles_anterior,
    'DROP TABLE IF EXISTS progreso_alumno',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(@niveles_anterior, 'DROP TABLE niveles', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;


-- ── usuarios: separar apellido ──────────────────────────────────────────────
-- Si la columna ya existe (re-ejecución), no la duplica.

SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'usuarios'
        AND column_name = 'apellido') = 0,
    'ALTER TABLE usuarios ADD COLUMN apellido VARCHAR(100) NULL AFTER nombre',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;


-- ── calendario_clases: clases programadas por curso ─────────────────────────

CREATE TABLE IF NOT EXISTS calendario_clases (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    curso_id      INT NOT NULL,
    titulo        VARCHAR(150) NOT NULL,
    fecha         DATE NOT NULL,
    hora_inicio   TIME NOT NULL,
    hora_fin      TIME NOT NULL,
    descripcion   TEXT NULL,
    creado_por    INT NULL,
    creado_en     DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_clase_curso   FOREIGN KEY (curso_id)  REFERENCES cursos(id)   ON DELETE CASCADE,
    CONSTRAINT fk_clase_creador FOREIGN KEY (creado_por) REFERENCES usuarios(id) ON DELETE SET NULL,
    INDEX idx_clase_curso_fecha (curso_id, fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ── comunicados internos (staff-only, NO visibles al alumno) ────────────────

CREATE TABLE IF NOT EXISTS comunicados (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    asunto          VARCHAR(200) NOT NULL,
    cuerpo          TEXT NOT NULL,
    destinatarios   ENUM('todos', 'curso') NOT NULL DEFAULT 'todos',
    curso_id        INT NULL,
    creado_por      INT NOT NULL,
    fecha           DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_comunicado_curso  FOREIGN KEY (curso_id)   REFERENCES cursos(id)   ON DELETE SET NULL,
    CONSTRAINT fk_comunicado_autor  FOREIGN KEY (creado_por) REFERENCES usuarios(id) ON DELETE CASCADE,
    INDEX idx_comunicado_fecha (fecha DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
