-- Migration 004: rediseño del panel administrativo
-- Target DB : gestion_facturas_amicana
-- Run once  : mysql -u root -p gestion_facturas_amicana < database/migrations/004_admin_overhaul.sql
--
-- Cambios:
--   - DROP de módulos eliminados (facturas IA, auditoría, análisis CUIT, progreso académico, niveles).
--   - ALTER usuarios: agrega columna `apellido` separada del `nombre`.
--   - CREATE calendario_clases (clases del calendario por curso).
--   - CREATE comunicados (comunicaciones internas del staff, no visibles al alumno).

USE gestion_facturas_amicana;


-- ── DROP de módulos eliminados ───────────────────────────────────────────────

DROP TABLE IF EXISTS analisis_pagos;
DROP TABLE IF EXISTS facturas_ia;
DROP TABLE IF EXISTS facturas;
DROP TABLE IF EXISTS auditoria;
DROP TABLE IF EXISTS progreso_alumno;
DROP TABLE IF EXISTS niveles;


-- ── usuarios: separar apellido ──────────────────────────────────────────────
-- Por compatibilidad, si la columna ya existe (re-ejecución), no la duplica.

ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS apellido VARCHAR(100) NULL AFTER nombre;


-- ── calendario_clases: clases programadas por curso ─────────────────────────

CREATE TABLE IF NOT EXISTS calendario_clases (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    curso_id      INT NOT NULL,
    titulo        VARCHAR(150) NOT NULL,
    fecha         DATE NOT NULL,
    hora_inicio   TIME NOT NULL,
    hora_fin      TIME NOT NULL,
    descripcion   TEXT NULL,
    creado_por    INT NULL,
    creado_en     DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_clase_curso   FOREIGN KEY (curso_id)  REFERENCES cursos(id)   ON DELETE CASCADE,
    CONSTRAINT fk_clase_creador FOREIGN KEY (creado_por) REFERENCES usuarios(id) ON DELETE SET NULL,
    INDEX idx_clase_curso_fecha (curso_id, fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ── comunicados internos (staff-only, NO visibles al alumno) ────────────────

CREATE TABLE IF NOT EXISTS comunicados (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    asunto          VARCHAR(200) NOT NULL,
    cuerpo          TEXT NOT NULL,
    destinatarios   ENUM('todos', 'curso') NOT NULL DEFAULT 'todos',
    curso_id        INT NULL,
    creado_por      INT NOT NULL,
    fecha           DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_comunicado_curso  FOREIGN KEY (curso_id)   REFERENCES cursos(id)   ON DELETE SET NULL,
    CONSTRAINT fk_comunicado_autor  FOREIGN KEY (creado_por) REFERENCES usuarios(id) ON DELETE CASCADE,
    INDEX idx_comunicado_fecha (fecha DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
