-- Migration 001: chatbot support
-- Target DB : gestion_facturas_amicana
-- How to run: mysql -u root -P 3307 gestion_facturas_amicana < database/migrations/001_chatbot.sql

-- Extend pagos table with manual-confirmation columns
ALTER TABLE pagos
  ADD COLUMN IF NOT EXISTS comprobante_manual       VARCHAR(100) NULL,
  ADD COLUMN IF NOT EXISTS confirmado_por_alumno    BOOLEAN      DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS fecha_confirmacion_manual DATETIME    NULL;

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
