# Guía de Usuario — AMICANA 2.0

Sistema de gestión académica del Instituto Cultural Argentino Norteamericano.

---

## Acceso al sistema

Ingresá desde tu navegador a la URL del sistema (local: `http://localhost:8000/app` o la URL de producción).

Podés iniciar sesión con:
- **Email y contraseña** — completá el formulario y hacé clic en *Ingresar*
- **Cuenta de Google** — hacé clic en *Continuar con Google*

Si no tenés cuenta, hacé clic en *Registrarme*, completá el formulario y aceptá los términos.

---

## Rol: Alumno

### Mis Cuotas
Al ingresar ves la lista de tus cuotas con estado (Pendiente / Pagada / Vencida).

**Pagar una cuota:**
1. Hacé clic en *Pagar* en la cuota deseada.
2. Se abre la pasarela de MercadoPago (tarjeta, QR, efectivo).
3. Completá el pago. Al volver, el estado se actualiza automáticamente.

**Descargar recibo:** Una vez pagada, podés descargar el PDF desde el botón *Recibo*.

### Mi Progreso
Visualizá tus niveles completados y las notas por unidad en cada curso.

### Calendario
Consultá el calendario académico con fechas de clases, exámenes y feriados.

### Chatbot Ianna
Hacé clic en el ícono del chat (esquina inferior derecha). Podés consultar:
- Estado de tus cuotas
- Fechas de vencimiento
- Información sobre cursos disponibles

### Mi Perfil
Hacé clic en tu nombre (arriba a la derecha) → *Perfil*. Podés actualizar teléfono y contraseña.

---

## Rol: Administrador / Administrativo

### Alumnos
- **Listar:** la tabla muestra todos los alumnos con filtro por texto.
- **Agregar:** completá nombre, email, contraseña y rol → *Guardar*.
- **Editar / Eliminar:** iconos en cada fila.

### Cursos
- **Listar con filtros:** filtrá por modalidad (Presencial / Virtual / Híbrido) y categoría (Inglés / Conversación / Business, etc.).
- **Agregar / Editar / Eliminar:** mismo flujo que alumnos.

### Cuotas
- **Ver cuotas por alumno:** buscá por email o nombre.
- **Agregar cuota:** seleccioná alumno, monto, vencimiento → *Guardar*.
- **Marcar como pagada manualmente:** botón *Confirmar pago*.

### Pagos MercadoPago
Lista de todas las transacciones MP con estado (pendiente / aprobado / rechazado).

### Reportes
Generá el listado de alumnos deudores. Podés exportarlo a PDF.

### Eventos
Cargá y editá eventos institucionales que aparecen en el calendario de los alumnos.

### Avisos
Publicá avisos visibles para todos los alumnos al ingresar.

### Configuración
Editá el nombre del instituto, dirección, teléfono y correo de contacto.

### Auditoría (solo admin)
Historial de todas las acciones realizadas por usuarios (quién hizo qué y cuándo).

---

## Preguntas frecuentes

**¿Olvidé mi contraseña?**  
Actualmente no hay recuperación automática por email. Contactá al administrador para que restablezca tu contraseña desde el panel.

**¿Por qué no se actualizó el estado de mi cuota luego de pagar?**  
El sistema verifica el pago automáticamente. Si tardó más de 2 minutos, recargá la página. Si el problema persiste, contactá al administrativo con el número de operación de MercadoPago.

**¿El chatbot no responde?**  
El chatbot Ianna requiere que el servicio n8n esté activo. Si el ícono no aparece o no responde, es probable que el servicio esté temporalmente inactivo.

**¿Cómo descargo el recibo de una cuota pagada?**  
En la sección *Mis Cuotas*, las cuotas con estado *Pagada* muestran un botón *Recibo* (PDF).
