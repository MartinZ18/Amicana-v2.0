# Receta de test manual — Chatbot Ianna (E2E)

**Prerrequisitos:**
- Servidor FastAPI corriendo: `uvicorn app.main:app --reload` (desde `/backend`)
- ngrok activo: `ngrok http --domain=chaffy-gamely-ramon.ngrok-free.dev 8000`
- n8n corriendo con el workflow `amicana-chatbot` activo
- Base de datos con al menos un alumno que tenga cuotas pendientes

---

## Paso 1 — Abrir el widget sin sesión
1. Abrí `http://localhost:8000/app/alumno.html` en el browser.
2. Hacé clic en el botón flotante del chat (esquina inferior derecha).
3. **Esperado:** se muestra el mensaje de bienvenida de Ianna (cargado desde `GET /chatbot/welcome`).
4. **Verificar:** en DevTools → Application → LocalStorage existe `amicana_session` con `{id, createdAt}`.

## Paso 2 — Identificación por DNI
1. Escribí: `Hola, quiero ver mis cuotas`.
2. El chatbot debe pedir DNI o email.
3. Ingresá el DNI de un alumno de prueba (ej: `40123456`).
4. **Esperado:** Ianna responde con el nombre del alumno y muestra sus cuotas pendientes.

## Paso 3 — Verificar pre-autenticación (si hay JWT)
1. Iniciá sesión como alumno en `index.html`.
2. Navegá a `alumno.html` y abrí el chat nuevamente.
3. **Esperado:** Ianna reconoce al alumno sin pedir DNI (el JWT se envía como `X-User-Token`).

## Paso 4 — Consultar estado de cuotas
1. (Ya identificado en el paso anterior.) Escribí: `¿Cuáles son mis cuotas pendientes?`
2. **Esperado:** listado de cuotas con concepto, monto y fecha de vencimiento.
3. **Verificar:** no aparece QR ni PDF en este mensaje (solo texto).

## Paso 5 — Pagar una cuota
1. Escribí: `Quiero pagar la cuota de mayo`.
2. **Esperado:** Ianna muestra el link de MercadoPago o un QR de pago.
3. Hacé clic en el link / escaneá el QR.
4. Completá el pago en el sandbox de MP.

## Paso 6 — Confirmar comprobante manual
1. Escribí: `Pagué por transferencia, mi comprobante es MP-123456`.
2. **Esperado:** Ianna confirma la recepción y dice que el pago quedará pendiente de verificación por el admin.
3. En el panel admin (`admin.html`) verificar que aparece el comprobante.

## Paso 7 — Descargar comprobante PDF
1. Escribí: `Quiero el comprobante PDF de mi pago`.
2. **Esperado:** Ianna responde con un link "Descargar comprobante PDF".
3. El link abre un PDF válido en nueva pestaña.

## Paso 8 — FAQ visual
1. Hacé clic en el botón **FAQ** en el header del chat.
2. **Esperado:** aparece un panel con chips de preguntas.
3. Hacé clic en "¿Cómo pago la cuota?".
4. **Esperado:** la pregunta se envía como mensaje y Ianna responde.

## Paso 9 — Rate limit
1. Enviá más de 30 mensajes en la misma sesión (en menos de 1 hora).
2. **Esperado:** el mensaje 31 recibe la respuesta "Demasiados mensajes, esperá un minuto."
3. **Verificar:** en los logs del servidor aparece `[chatbot proxy] rate limit excedido`.

## Paso 10 — Persistencia de sesión (TTL 7 días)
1. Cerrá completamente el browser (no solo la pestaña).
2. Abrí nuevamente `alumno.html` y el widget.
3. **Esperado:** el `session_id` en LocalStorage es el **mismo** que antes (no se regeneró).
4. Comprobá que Ianna recuerda el contexto de la conversación (si el workflow n8n persiste historial).
5. Pasados 7 días, al abrir el widget se debe generar un nuevo `session_id`.

---

## Checklist final
- [ ] Bienvenida carga desde `/chatbot/welcome`
- [ ] Identificación por DNI funciona
- [ ] Pre-auth con JWT evita re-identificación
- [ ] Estado de cuotas correcto
- [ ] Pago con MP genera link/QR
- [ ] Comprobante manual se registra
- [ ] PDF descargable desde el chat
- [ ] FAQ visual funciona con chips
- [ ] Rate limit devuelve mensaje amigable al mensaje 31
- [ ] `session_id` persiste en LocalStorage al cerrar el browser
