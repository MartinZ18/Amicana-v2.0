-- Migration 007: avisos del instituto
-- Tabla de comunicados que el alumno ve en su dashboard.
-- Soft delete via columna `activo`.

USE gestion_facturas_amicana;

CREATE TABLE IF NOT EXISTS avisos (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    titulo             VARCHAR(150) NOT NULL,
    contenido          TEXT NOT NULL,
    importante         TINYINT(1) NOT NULL DEFAULT 0,
    fecha_publicacion  DATETIME DEFAULT CURRENT_TIMESTAMP,
    creado_por         INT NOT NULL,
    activo             TINYINT(1) NOT NULL DEFAULT 1,
    CONSTRAINT fk_avisos_creador FOREIGN KEY (creado_por)
        REFERENCES usuarios(id) ON DELETE CASCADE,
    INDEX idx_avisos_activo_fecha (activo, fecha_publicacion DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
