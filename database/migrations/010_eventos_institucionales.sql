-- Migration 010: eventos institucionales
-- Calendario de feriados, conmemoraciones, intercambios y eventos varios.
-- Diferenciado de calendario_clases (que es por curso).

USE gestion_facturas_amicana;

CREATE TABLE IF NOT EXISTS eventos_institucionales (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    titulo           VARCHAR(150) NOT NULL,
    descripcion      TEXT NULL,
    tipo             ENUM('feriado','conmemorativo','intercambio','evento','otro')
                         NOT NULL DEFAULT 'evento',
    fecha_inicio     DATE NOT NULL,
    fecha_fin        DATE NULL,
    hora_inicio      TIME NULL,
    hora_fin         TIME NULL,
    todo_el_dia      BOOLEAN NOT NULL DEFAULT FALSE,
    visible_alumno   BOOLEAN NOT NULL DEFAULT TRUE,
    creado_por       INT NULL,
    creado_en        DATETIME DEFAULT CURRENT_TIMESTAMP,
    actualizado_en   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_evento_creador FOREIGN KEY (creado_por)
        REFERENCES usuarios(id) ON DELETE SET NULL,
    INDEX idx_evento_fecha (fecha_inicio),
    INDEX idx_evento_tipo  (tipo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
