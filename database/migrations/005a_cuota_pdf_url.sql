-- Migration 005: agregar columna pdf_url a cuotas para deduplicación de PDFs
-- Target DB : gestion_facturas_amicana
-- Run once  : mysql -u root -P 3307 gestion_facturas_amicana < database/migrations/005a_cuota_pdf_url.sql
-- Idempotente y compatible con MySQL 8 y MariaDB (no usa ADD COLUMN IF NOT EXISTS,
-- que es solo MariaDB): consulta information_schema antes de cada cambio.

SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'cuotas'
        AND column_name = 'pdf_url') = 0,
    'ALTER TABLE cuotas ADD COLUMN pdf_url VARCHAR(255) NULL',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
