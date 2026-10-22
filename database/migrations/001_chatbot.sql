-- Migration 001: chatbot support
-- Target DB : gestion_facturas_amicana
-- How to run: mysql -u root -P 3307 gestion_facturas_amicana < database/migrations/001_chatbot.sql
-- Idempotente y compatible con MySQL 8 y MariaDB (no usa ADD COLUMN IF NOT EXISTS,
-- que es solo MariaDB): consulta information_schema antes de cada cambio.

-- Extend pagos table with manual-confirmation columns
SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'pagos'
        AND column_name = 'comprobante_manual') = 0,
    'ALTER TABLE pagos ADD COLUMN comprobante_manual VARCHAR(100) NULL',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'pagos'
        AND column_name = 'confirmado_por_alumno') = 0,
    'ALTER TABLE pagos ADD COLUMN confirmado_por_alumno BOOLEAN DEFAULT FALSE',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'pagos'
        AND column_name = 'fecha_confirmacion_manual') = 0,
    'ALTER TABLE pagos ADD COLUMN fecha_confirmacion_manual DATETIME NULL',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- New table for chatbot conversation sessions
CREATE TABLE IF NOT EXISTS chat_sessions (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  session_id     VARCHAR(100) UNIQUE NOT NULL,
  alumno_id      INT          NULL,
  estado         ENUM('sin_autenticar', 'autenticado', 'cerrado') DEFAULT 'sin_autenticar',
  intentos_auth  INT          DEFAULT 0,
  creado_en      DATETIME     DEFAULT NOW(),
  actualizado_en DATETIME     DEFAULT NOW() ON UPDATE NOW(),
  FOREIGN KEY (alumno_id) REFERENCES usuarios(id)
);
