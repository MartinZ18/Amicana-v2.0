-- Migration 011: preferencias del sistema (clave/valor)
-- Almacena configuración editable desde el panel admin: datos del instituto,
-- vencimiento de cuotas, recargo, flags del chatbot, etc.

USE gestion_facturas_amicana;

CREATE TABLE IF NOT EXISTS preferencias_sistema (
    clave           VARCHAR(80) PRIMARY KEY,
    valor           TEXT NOT NULL,
    descripcion     VARCHAR(255) NULL,
    actualizado_en  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT IGNORE INTO preferencias_sistema (clave, valor, descripcion) VALUES
    ('instituto_nombre',          'AMICANA',                    'Nombre institucional mostrado en UI y PDFs'),
    ('instituto_direccion',       '',                           'Dirección física del instituto'),
    ('instituto_telefono',        '',                           'Teléfono de contacto'),
    ('instituto_email',           'contacto@amicana.com',       'Email institucional'),
    ('cuotas_dia_vencimiento',    '10',                         'Día del mes en que vencen las cuotas (1-28)'),
    ('cuotas_recargo_porcentaje', '0',                          'Recargo aplicado a cuotas vencidas (%)'),
    ('chatbot_habilitado',        'true',                       'Si el widget del chatbot está activo'),
    ('avisos_dias_visibles',      '30',                         'Días que un aviso permanece visible para alumnos');
