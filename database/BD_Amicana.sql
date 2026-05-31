-- ============================================================
--  AMICANA 2.0 — Schema canónico (instalación desde cero)
--
--  Consolida todas las migraciones (001..012).
--  Este es el ÚNICO archivo que necesitás para una instalación nueva:
--
--      mysql -u root -p < database/BD_Amicana.sql
--
--  ⚠️  Si ya tenés una BD con datos, NO uses este archivo.
--      Aplicá solo las migraciones que te falten en orden:
--      database/migrations/001_*.sql ... 012_*.sql
--
--  Idempotente: usa CREATE TABLE IF NOT EXISTS y INSERT IGNORE.
--
--  Tablas: 15
--  Última revisión: corregidas columnas faltantes en `pagos`
--  (comprobante_manual, confirmado_por_alumno, fecha_confirmacion_manual)
--  y `pagos_mp` (external_reference), ausentes en versiones anteriores.
-- ============================================================

CREATE DATABASE IF NOT EXISTS gestion_facturas_amicana
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE gestion_facturas_amicana;


-- ============================================================
--  1. CURSOS (parent — los referencian usuarios, calendario, comunicados, unidades)
-- ============================================================

CREATE TABLE IF NOT EXISTS cursos (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    nombre      VARCHAR(100) NOT NULL UNIQUE,
    descripcion VARCHAR(255) NULL,
    monto_cuota DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    modalidad   ENUM('presencial','virtual','hibrido')
                    NOT NULL DEFAULT 'presencial',
    categoria   ENUM('regular','acelerado','especial','intensivo')
                    NOT NULL DEFAULT 'regular',
    activo      BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en   DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_cursos_categoria_modalidad (categoria, modalidad)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================================
--  2. USUARIOS
--  - `password` es NULL para cuentas Google OAuth y para alumnos
--    dados de alta por el admin que aún no se registraron.
--  - `auth_provider` distingue local (bcrypt) de federado (Google).
--  - `modalidad` puede heredarse del curso (backfill al alta).
-- ============================================================

CREATE TABLE IF NOT EXISTS usuarios (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    nombre        VARCHAR(100) NOT NULL,
    apellido      VARCHAR(100) NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    google_id     VARCHAR(100) NULL UNIQUE,
    auth_provider ENUM('local','google') NOT NULL DEFAULT 'local',
    password      VARCHAR(255) NULL,
    rol           ENUM('admin','administrativo','alumno') NOT NULL DEFAULT 'alumno',
    dni           VARCHAR(10)  NULL UNIQUE,
    telefono      VARCHAR(20)  NULL,
    curso_id      INT          NULL,
    modalidad     ENUM('presencial','virtual','hibrido') NULL,
    creado_en     DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_usuarios_curso FOREIGN KEY (curso_id) REFERENCES cursos(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================================
--  3. NIVELES + PROGRESO ACADÉMICO (CEFR)
--  Soporte para "Mi Progreso" y aptitud de exámenes internacionales.
-- ============================================================

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


-- ============================================================
--  4. CUOTAS
-- ============================================================

CREATE TABLE IF NOT EXISTS cuotas (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    alumno_id             INT NOT NULL,
    concepto              VARCHAR(200) NOT NULL,
    monto                 DECIMAL(10,2) NOT NULL,
    fecha_vencimiento     DATE NOT NULL,
    estado                ENUM('pendiente','vencida','pagada','pendiente_verificacion')
                              NOT NULL DEFAULT 'pendiente',
    preference_id         VARCHAR(100) NULL,
    comprobante_manual    VARCHAR(100) NULL,
    confirmado_por_alumno BOOLEAN NOT NULL DEFAULT FALSE,
    pdf_url               VARCHAR(255) NULL,
    fecha_creacion        DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_cuotas_alumno FOREIGN KEY (alumno_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================================
--  5. PAGOS (legacy) + PAGOS MERCADOPAGO
-- ============================================================

CREATE TABLE IF NOT EXISTS pagos (
    id                         INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id                 INT NULL,
    monto                      DECIMAL(10,2) NOT NULL,
    fecha                      DATETIME DEFAULT CURRENT_TIMESTAMP,
    estado                     VARCHAR(50) DEFAULT 'pendiente',
    metodo_pago                VARCHAR(50) NULL,
    referencia_qr              VARCHAR(100) NULL,
    comprobante_manual         VARCHAR(100) NULL,
    confirmado_por_alumno      BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_confirmacion_manual  DATETIME NULL,
    CONSTRAINT fk_pagos_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS pagos_mp (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    preference_id      VARCHAR(100) NOT NULL,
    concepto           VARCHAR(200) NOT NULL,
    monto              DECIMAL(10,2) NOT NULL,
    cantidad           INT NOT NULL DEFAULT 1,
    estado             VARCHAR(50) NOT NULL DEFAULT 'pendiente',
    payment_id         VARCHAR(100) NULL,
    email_pagador      VARCHAR(150) NULL,
    metodo_pago        VARCHAR(50)  NULL,
    creado_por         VARCHAR(150) NULL,
    external_reference VARCHAR(100) NULL,
    fecha_pago         DATETIME NULL,
    fecha_creacion     DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_pagos_mp_external (external_reference)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================================
--  6. CHATBOT — sesiones persistidas (Ianna)
-- ============================================================

CREATE TABLE IF NOT EXISTS chat_sessions (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    session_id     VARCHAR(100) NOT NULL UNIQUE,
    alumno_id      INT NULL,
    estado         ENUM('activo','cerrado','timeout','sin_autenticar') NOT NULL DEFAULT 'activo',
    intentos_auth  INT NOT NULL DEFAULT 0,
    history        JSON NULL,
    creado_en      DATETIME DEFAULT CURRENT_TIMESTAMP,
    actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_chat_alumno FOREIGN KEY (alumno_id) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================================
--  7. AVISOS INSTITUCIONALES (visibles al alumno)
-- ============================================================

CREATE TABLE IF NOT EXISTS avisos (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    titulo             VARCHAR(150) NOT NULL,
    contenido          TEXT NOT NULL,
    importante         BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_publicacion  DATETIME DEFAULT CURRENT_TIMESTAMP,
    creado_por         INT NOT NULL,
    activo             BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_avisos_creador FOREIGN KEY (creado_por)
        REFERENCES usuarios(id) ON DELETE CASCADE,
    INDEX idx_avisos_activo_fecha (activo, fecha_publicacion DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================================
--  8. CALENDARIO DE CLASES (por curso)
-- ============================================================

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


-- ============================================================
--  9. COMUNICADOS INTERNOS (staff-only, NO visibles al alumno)
-- ============================================================

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


-- ============================================================
--  10. EVENTOS INSTITUCIONALES (feriados, conmemorativos, intercambios)
--  Diferenciado de calendario_clases (que es por curso).
-- ============================================================

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


-- ============================================================
--  11. UNIDADES POR CURSO (catálogo del programa)
-- ============================================================

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


-- ============================================================
--  12. NOTAS DEL ALUMNO POR UNIDAD Y SECCIÓN
--  Una fila por (alumno, unidad, sección). Escala 0-10.
-- ============================================================

CREATE TABLE IF NOT EXISTS notas_alumno (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    alumno_id       INT NOT NULL,
    unidad_id       INT NOT NULL,
    seccion         ENUM('grammar','vocabulary','speaking','listening','writing','reading')
                        NOT NULL,
    nota            DECIMAL(4,2) NOT NULL,
    pain_points     TEXT NULL,
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


-- ============================================================
--  13. PREFERENCIAS DEL SISTEMA (clave/valor)
--  Configuración editable desde el panel admin.
-- ============================================================

CREATE TABLE IF NOT EXISTS preferencias_sistema (
    clave           VARCHAR(80) PRIMARY KEY,
    valor           TEXT NOT NULL,
    descripcion     VARCHAR(255) NULL,
    actualizado_en  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================================
--  SEEDS — datos iniciales
-- ============================================================

-- Niveles CEFR (usados por progreso_alumno y aptitud-examen del chatbot)
INSERT IGNORE INTO niveles (codigo, descripcion, orden) VALUES
    ('A1', 'Principiante',           1),
    ('A2', 'Básico',                  2),
    ('B1', 'Intermedio',              3),
    ('B2', 'Intermedio Alto',         4),
    ('C1', 'Avanzado',                5),
    ('C2', 'Dominio',                 6);

-- Cursos por defecto (catálogo inicial — el admin puede editarlo después)
INSERT IGNORE INTO cursos (nombre, descripcion, monto_cuota, modalidad, categoria, activo) VALUES
    ('English A1 - Beginners',     'Nivel inicial, 2 clases por semana',         8500.00, 'presencial', 'regular',   TRUE),
    ('English B1 - Intermediate',  'Nivel intermedio, comunicación avanzada',   10500.00, 'presencial', 'regular',   TRUE),
    ('English C1 - Advanced',      'Nivel superior, certificaciones',           12500.00, 'presencial', 'regular',   TRUE),
    ('Conversation Class',         'Práctica oral intensiva, grupos reducidos',  7000.00, 'hibrido',    'especial',  TRUE);

-- Preferencias del sistema (el admin las edita en panel Configuración)
INSERT IGNORE INTO preferencias_sistema (clave, valor, descripcion) VALUES
    ('instituto_nombre',          'AMICANA',                    'Nombre institucional mostrado en UI y PDFs'),
    ('instituto_direccion',       '',                           'Dirección física del instituto'),
    ('instituto_telefono',        '',                           'Teléfono de contacto'),
    ('instituto_email',           'contacto@amicana.com',       'Email institucional'),
    ('cuotas_dia_vencimiento',    '10',                         'Día del mes en que vencen las cuotas (1-28)'),
    ('cuotas_recargo_porcentaje', '0',                          'Recargo aplicado a cuotas vencidas (%)'),
    ('chatbot_habilitado',        'true',                       'Si el widget del chatbot está activo'),
    ('avisos_dias_visibles',      '30',                         'Días que un aviso permanece visible para alumnos');


-- ============================================================
--  Verificación rápida (ejecutar tras el import):
--
--    SELECT table_name FROM information_schema.tables
--      WHERE table_schema = 'gestion_facturas_amicana'
--      ORDER BY table_name;
--
--  Debe listar exactamente 15 tablas:
--    avisos, calendario_clases, chat_sessions, comunicados,
--    cursos, eventos_institucionales, niveles, notas_alumno,
--    pagos, pagos_mp, preferencias_sistema, progreso_alumno,
--    unidades, usuarios, cuotas
-- ============================================================
