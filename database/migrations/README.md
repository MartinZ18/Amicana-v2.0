# Migraciones incrementales

> **Si arrancás de cero, NO uses esta carpeta** — corré `database/BD_Amicana.sql` y listo.
>
> Estas migraciones son solo para upgrades de instalaciones que ya tienen datos viejos.

## Orden de aplicación

Aplicarlas en orden numérico. Las migraciones son idempotentes y corren en MySQL 8 y MariaDB: `CREATE TABLE IF NOT EXISTS`, `INSERT IGNORE` y, para columnas, índices y claves foráneas, una consulta a `information_schema` antes de cada cambio.

`004a` borra `niveles` y `progreso_alumno` solo si están en el formato anterior (sin `codigo`/`orden` o sin `modulos_completados`/`fecha_proximo_examen`), y `008` las crea en el formato actual. Si ya tienen el formato actual se conservan con sus datos, así que volver a correr todas las migraciones no borra el progreso de los alumnos.

| # | Archivo | Qué hace |
|---|---------|----------|
| 001 | `001_chatbot.sql` | Crea `chat_sessions`, columnas `comprobante_manual`/`confirmado_por_alumno` en `pagos`. |
| 002 | `002_cursos_y_alumno_datos.sql` | Crea `cursos`. Agrega `dni`/`telefono`/`curso_id` a `usuarios`. |
| 003 | `003_cuotas_estado_verificacion.sql` | Agrega `pendiente_verificacion` al ENUM `cuotas.estado`. |
| 004a | `004a_admin_overhaul.sql` | Drop de módulos legacy (`auditoria`, `facturas`, `analisis`) y de `niveles`/`progreso_alumno` en formato anterior. Crea `calendario_clases`, `comunicados`. Agrega `apellido` a `usuarios`. |
| 004b | `004b_chat_session_history.sql` | Agrega columna `history JSON` a `chat_sessions`. |
| 005a | `005a_cuota_pdf_url.sql` | Agrega `pdf_url` a `cuotas`. |
| 005b | `005b_curso_nombres_ingles.sql` | Renombra cursos del seed inicial al inglés. |
| 006 | `006_google_oauth.sql` | Agrega `google_id`/`auth_provider` a `usuarios`. Permite `password NULL`. |
| 007 | `007_create_avisos.sql` | Crea tabla `avisos`. |
| 008 | `008_niveles_progreso.sql` | Crea `niveles` (CEFR A1–C2) y `progreso_alumno`. |
| 009 | `009_modalidad_y_categoria.sql` | Agrega `modalidad`+`categoria` a `cursos`, `modalidad` a `usuarios` con backfill. |
| 010 | `010_eventos_institucionales.sql` | Crea tabla `eventos_institucionales`. |
| 011 | `011_preferencias_sistema.sql` | Crea `preferencias_sistema` + 8 seeds (datos del instituto, cuotas, flags). |
| 012 | `012_notas_unidades.sql` | Crea `unidades` y `notas_alumno` (notas por sección con pain points). |
| 013 | `013_indices_cuotas.sql` | Índices `cuotas(estado, fecha_vencimiento)` y `cuotas(preference_id)`. Idempotente (chequea `information_schema`). |

## Migraciones 004 y 005

Las migraciones 004 y 005 tienen dos partes cada una (`a` y `b`) porque fueron cambios paralelos. El orden alfabético de los archivos ya es el orden de aplicación: primero `a`, después `b`.
