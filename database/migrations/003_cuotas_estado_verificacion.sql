-- Migration 003: extiende cuotas.estado para soportar confirmación manual pendiente de admin
-- Target DB : gestion_facturas_amicana
-- Run once  : mysql -u root -P 3307 gestion_facturas_amicana < database/migrations/003_cuotas_estado_verificacion.sql

ALTER TABLE cuotas
  MODIFY COLUMN estado
    ENUM('pendiente', 'pagada', 'vencida', 'pendiente_verificacion')
    DEFAULT 'pendiente';
