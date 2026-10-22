-- Migration 009: modalidad y categoría en cursos + modalidad en usuarios
-- Habilita filtros y badges en admin (presencial/virtual/híbrido y regular/acelerado/especial/intensivo).
-- La modalidad del alumno puede heredarse del curso o setearse explícitamente.
-- Idempotente y compatible con MySQL 8 y MariaDB (no usa ADD COLUMN IF NOT EXISTS,
-- que es solo MariaDB): consulta information_schema antes de cada cambio.

USE gestion_facturas_amicana;

SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'cursos'
        AND column_name = 'modalidad') = 0,
    'ALTER TABLE cursos ADD COLUMN modalidad ENUM(''presencial'',''virtual'',''hibrido'') NOT NULL DEFAULT ''presencial'' AFTER monto_cuota',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'cursos'
        AND column_name = 'categoria') = 0,
    'ALTER TABLE cursos ADD COLUMN categoria ENUM(''regular'',''acelerado'',''especial'',''intensivo'') NOT NULL DEFAULT ''regular'' AFTER modalidad',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.statistics
      WHERE table_schema = DATABASE() AND table_name = 'cursos'
        AND index_name = 'idx_cursos_categoria_modalidad') = 0,
    'CREATE INDEX idx_cursos_categoria_modalidad ON cursos (categoria, modalidad)',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'usuarios'
        AND column_name = 'modalidad') = 0,
    'ALTER TABLE usuarios ADD COLUMN modalidad ENUM(''presencial'',''virtual'',''hibrido'') NULL AFTER curso_id',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Backfill: si el alumno no tiene modalidad seteada, copiarla del curso al que pertenece.
UPDATE usuarios u
JOIN cursos c ON u.curso_id = c.id
SET u.modalidad = c.modalidad
WHERE u.modalidad IS NULL
  AND u.curso_id IS NOT NULL;
