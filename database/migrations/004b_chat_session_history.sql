-- Migration 004: agregar columna history JSON a chat_sessions
-- Target DB : gestion_facturas_amicana
-- Run once  : mysql -u root -P 3307 gestion_facturas_amicana < database/migrations/004b_chat_session_history.sql
-- Idempotente y compatible con MySQL 8 y MariaDB (no usa ADD COLUMN IF NOT EXISTS,
-- que es solo MariaDB): consulta information_schema antes de cada cambio.

SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'chat_sessions'
        AND column_name = 'history') = 0,
    'ALTER TABLE chat_sessions ADD COLUMN history JSON NULL',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
