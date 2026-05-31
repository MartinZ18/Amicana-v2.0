-- Migration 008: niveles e idioma + progreso del alumno
-- Soporte para certificados y dashboard "Mi progreso".

USE gestion_facturas_amicana;

CREATE TABLE IF NOT EXISTS niveles (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    codigo       VARCHAR(10) NOT NULL UNIQUE,
    descripcion  VARCHAR(100) NOT NULL,
    orden        INT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS progreso_alumno (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    alumno_id             INT NOT NULL UNIQUE,
    nivel_id              INT NULL,
    modulos_completados   INT NOT NULL DEFAULT 0,
    fecha_inicio          DATE NULL,
    fecha_proximo_examen  DATE NULL,
    actualizado_en        DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_progreso_alumno FOREIGN KEY (alumno_id)
        REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_progreso_nivel FOREIGN KEY (nivel_id)
        REFERENCES niveles(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT IGNORE INTO niveles (codigo, descripcion, orden) VALUES
    ('A1', 'Principiante',           1),
    ('A2', 'Básico',                  2),
    ('B1', 'Intermedio',              3),
    ('B2', 'Intermedio Alto',         4),
    ('C1', 'Avanzado',                5),
    ('C2', 'Dominio',                 6);
