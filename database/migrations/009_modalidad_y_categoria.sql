-- Migration 009: modalidad y categoría en cursos + modalidad en usuarios
-- Habilita filtros y badges en admin (presencial/virtual/híbrido y regular/acelerado/especial/intensivo).
-- La modalidad del alumno puede heredarse del curso o setearse explícitamente.

USE gestion_facturas_amicana;

ALTER TABLE cursos
    ADD COLUMN modalidad ENUM('presencial','virtual','hibrido')
        NOT NULL DEFAULT 'presencial' AFTER monto_cuota,
    ADD COLUMN categoria ENUM('regular','acelerado','especial','intensivo')
        NOT NULL DEFAULT 'regular' AFTER modalidad;

CREATE INDEX idx_cursos_categoria_modalidad
    ON cursos (categoria, modalidad);

ALTER TABLE usuarios
    ADD COLUMN modalidad ENUM('presencial','virtual','hibrido') NULL AFTER curso_id;

-- Backfill: si el alumno no tiene modalidad seteada, copiarla del curso al que pertenece.
UPDATE usuarios u
JOIN cursos c ON u.curso_id = c.id
SET u.modalidad = c.modalidad
WHERE u.modalidad IS NULL
  AND u.curso_id IS NOT NULL;
