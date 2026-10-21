-- Migration 013: índices de rendimiento sobre `cuotas`.
--   * idx_cuotas_estado_venc  (estado, fecha_vencimiento): lo usa el barrido
--     UPDATE ... SET estado='vencida' WHERE estado='pendiente' AND fecha_vencimiento < CURDATE()
--     que corre al inicio de varios endpoints de lectura (antes: full scan).
--   * idx_cuotas_preference   (preference_id): lo usa pagos.py al confirmar un
--     pago aprobado de MercadoPago (WHERE preference_id = %s).
--
-- Idempotente y compatible con MySQL 8 y MariaDB (no usa CREATE INDEX IF NOT EXISTS,
-- que es solo MariaDB): consulta information_schema antes de crear cada índice.
-- No modifica datos.

USE gestion_facturas_amicana;

SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.statistics
      WHERE table_schema = DATABASE() AND table_name = 'cuotas'
        AND index_name = 'idx_cuotas_estado_venc') = 0,
    'CREATE INDEX idx_cuotas_estado_venc ON cuotas (estado, fecha_vencimiento)',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.statistics
      WHERE table_schema = DATABASE() AND table_name = 'cuotas'
        AND index_name = 'idx_cuotas_preference') = 0,
    'CREATE INDEX idx_cuotas_preference ON cuotas (preference_id)',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
