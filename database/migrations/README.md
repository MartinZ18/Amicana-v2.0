# Migraciones incrementales

> **Si arrancás de cero, NO uses esta carpeta** — corré `database/BD_Amicana.sql` y listo.
>
> Estas migraciones son solo para upgrades de instalaciones que ya tienen datos viejos.

## Orden de aplicación

Aplicarlas en orden numérico. Las migraciones son idempotentes (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `INSERT IGNORE`).

| # | Archivo | Qué hace |
|---|---------|----------|
| 001 | `001_chatbot.sql` | Crea `chat_sessions`, columnas `comprobante_manual`/`confirmado_por_alumno` en `pagos`. |
| 002 | `002_cursos_y_alumno_datos.sql` | Crea `cursos`. Agrega `dni`/`telefono`/`curso_id` a `usuarios`. |
| 003 | `003_cuotas_estado_verificacion.sql` | Agrega `pendiente_verificacion` al ENUM `cuotas.estado`. |
| 004a | `004_admin_overhaul.sql` | Drop de módulos legacy (`auditoria`, `facturas`, `analisis`). Crea `calendario_clases`, `comunicados`. Agrega `apellido` a `usuarios`. |
| 004b | `004_chat_session_history.sql` | Agrega columna `history JSON` a `chat_sessions`. |
| 005a | `005_cuota_pdf_url.sql` | Agrega `pdf_url` a `cuotas`. |
| 005b | `005_curso_nombres_ingles.sql` | Renombra cursos del seed inicial al inglés. |
| 006 | `006_google_oauth.sql` | Agrega `google_id`/`auth_provider` a `usuarios`. Permite `password NULL`. |
| 007 | `007_create_avisos.sql` | Crea tabla `avisos`. |
| 008 | `008_niveles_progreso.sql` | Crea `niveles` (CEFR A1–C2) y `progreso_alumno`. |
| 009 | `009_modalidad_y_categoria.sql` | Agrega `modalidad`+`categoria` a `cursos`, `modalidad` a `usuarios` con backfill. |
| 010 | `010_eventos_institucionales.sql` | Crea tabla `eventos_institucionales`. |
| 011 | `011_preferencias_sistema.sql` | Crea `preferencias_sistema` + 8 seeds (datos del instituto, cuotas, flags). |
| 012 | `012_notas_unidades.sql` | Crea `unidades` y `notas_alumno` (notas por sección con pain points). |

## Notas sobre numeración duplicada

Las migraciones `004_*` y `005_*` aparecen duplicadas (admin_overhaul / chat_session_history y cuota_pdf_url / curso_nombres_ingles). Son cambios paralelos hechos en el mismo punto del tiempo; aplicar primero la más estructural (admin_overhaul, cuota_pdf_url) y después la otra.
