-- Migration 006: Google OAuth 2.0
-- Agrega google_id (sub de Google) y auth_provider para distinguir
-- usuarios locales (password bcrypt) de usuarios federados (Google).
-- Los usuarios Google tienen password = NULL.
-- Idempotente y compatible con MySQL 8 y MariaDB (no usa ADD COLUMN IF NOT EXISTS,
-- que es solo MariaDB): consulta information_schema antes de cada cambio.

USE gestion_facturas_amicana;

SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'usuarios'
        AND column_name = 'google_id') = 0,
    'ALTER TABLE usuarios ADD COLUMN google_id VARCHAR(100) NULL UNIQUE AFTER email',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'usuarios'
        AND column_name = 'auth_provider') = 0,
    'ALTER TABLE usuarios ADD COLUMN auth_provider ENUM(''local'',''google'') NOT NULL DEFAULT ''local'' AFTER google_id',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Permitir password NULL para cuentas OAuth (en BD original era NOT NULL)
ALTER TABLE usuarios MODIFY COLUMN password VARCHAR(255) NULL;
