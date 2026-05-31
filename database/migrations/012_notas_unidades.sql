-- Migration 012: notas por unidad y sección para "Mi Progreso" del alumno.
-- Catálogo de unidades por curso + notas (con pain_points) por (alumno, unidad, sección).

USE gestion_facturas_amicana;

-- Catálogo de unidades por curso (definidas por admin/profesor).
CREATE TABLE IF NOT EXISTS unidades (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    curso_id    INT NOT NULL,
    numero      INT NOT NULL,
    titulo      VARCHAR(150) NOT NULL,
    orden       INT NOT NULL DEFAULT 0,
    activa      BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_unidad_curso FOREIGN KEY (curso_id) REFERENCES cursos(id) ON DELETE CASCADE,
    UNIQUE KEY uniq_unidad_curso_numero (curso_id, numero)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Notas del alumno: una fila por (alumno, unidad, sección).
-- Sección es enum fija: grammar, vocabulary, speaking, listening, writing, reading.
CREATE TABLE IF NOT EXISTS notas_alumno (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    alumno_id       INT NOT NULL,
    unidad_id       INT NOT NULL,
    seccion         ENUM('grammar','vocabulary','speaking','listening','writing','reading')
                        NOT NULL,
    nota            DECIMAL(4,2) NOT NULL,            -- escala 0-10 con 2 decimales
    pain_points     TEXT NULL,                         -- texto libre cargado por profesor
    fecha           DATE NULL,
    creado_en       DATETIME DEFAULT CURRENT_TIMESTAMP,
    actualizado_en  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_nota_alumno FOREIGN KEY (alumno_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_nota_unidad FOREIGN KEY (unidad_id) REFERENCES unidades(id) ON DELETE CASCADE,
    UNIQUE KEY uniq_nota_alumno_unidad_seccion (alumno_id, unidad_id, seccion),
    INDEX idx_nota_alumno (alumno_id),
    INDEX idx_nota_unidad (unidad_id),
    CONSTRAINT chk_nota_rango CHECK (nota BETWEEN 0 AND 10)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
