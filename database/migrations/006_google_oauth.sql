-- Migration 006: Google OAuth 2.0
-- Agrega google_id (sub de Google) y auth_provider para distinguir
-- usuarios locales (password bcrypt) de usuarios federados (Google).
-- Los usuarios Google tienen password = NULL.

USE gestion_facturas_amicana;

ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS google_id VARCHAR(100) NULL UNIQUE AFTER email,
    ADD COLUMN IF NOT EXISTS auth_provider ENUM('local','google') NOT NULL DEFAULT 'local' AFTER google_id;

-- Permitir password NULL para cuentas OAuth (en BD original era NOT NULL)
ALTER TABLE usuarios MODIFY COLUMN password VARCHAR(255) NULL;
