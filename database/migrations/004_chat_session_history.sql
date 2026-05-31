-- Migration 004: agregar columna history JSON a chat_sessions
-- Target DB : gestion_facturas_amicana
-- Run once  : mysql -u root -P 3307 gestion_facturas_amicana < database/migrations/004_chat_session_history.sql

ALTER TABLE chat_sessions
  ADD COLUMN IF NOT EXISTS history JSON NULL;
