-- Migration 005: agregar columna pdf_url a cuotas para deduplicación de PDFs
-- Target DB : gestion_facturas_amicana
-- Run once  : mysql -u root -P 3307 gestion_facturas_amicana < database/migrations/005_cuota_pdf_url.sql

ALTER TABLE cuotas
  ADD COLUMN IF NOT EXISTS pdf_url VARCHAR(255) NULL;
