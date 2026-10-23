"""Pagos: cuotas, MP, confirmación manual, historial.

Schemas centralizados en `app.schemas.pagos` y `app.schemas.cuotas`.
Las shapes históricas de respuesta se mantienen para no romper el
frontend ni el workflow de n8n.
"""
import logging
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.concurrency import run_in_threadpool

from ..services.auditoria_service import registrar as registrar_accion
from ..database import get_connection
from ..dependencies import (get_chatbot_or_current_user, get_current_user,
                            is_chatbot, puede_pagar_cuota, puede_verificar_pago,
                            require_rol)
from ..schemas.cuotas import CuotasBulkRequest
from ..schemas.pagos import (ConfirmarManualRequest, GenerarFacturaPdfRequest,
                             PagarCuotaRequest, PagoMPRequest)
from ..services import mercadopago_service
from ..services.mercadopago_client import MP_MONEDA
from ..services.pdf_service import generar_factura_pdf
from ..utils import serialize_row
from ..utils.responses import error

router = APIRouter(prefix="/pagos", tags=["pagos"])

# Endpoints históricos sin prefijo /pagos. Mantenidos por compatibilidad
# con el frontend, n8n y tests existentes.
pagos_root_router = APIRouter(tags=["pagos-root"])


_STAFF = ("admin", "administrativo")

_log = logging.getLogger("amicana")

_TOLERANCIA_MONTO = Decimal("0.01")


def _pago_cubre_cuota(monto_recibido, moneda, monto_cuota) -> bool:
    """True si el pago de MP cubre la cuota: misma moneda y monto >= cuota (±1 centavo)."""
    if moneda != MP_MONEDA:
        return False
    try:
        recibido = Decimal(str(monto_recibido))
        if not recibido.is_finite():
            return False
        return recibido >= Decimal(str(monto_cuota)) - _TOLERANCIA_MONTO
    except Exception:
        return False


def _aplicar_pago_aprobado_a_cuota(cursor, cuota: dict, payment_id, monto_recibido, moneda) -> str:
    """Aplica un pago APROBADO de MP a una cuota y devuelve su estado final.

    Solo marca `pagada` si el monto y la moneda cubren la cuota; si no, la deja
    en `pendiente_verificacion` para revisión y loguea la diferencia. Una cuota
    ya `pagada` nunca se modifica, así los reintentos son idempotentes.
    """
    if cuota["estado"] == "pagada":
        return "pagada"
    if _pago_cubre_cuota(monto_recibido, moneda, cuota["monto"]):
        cursor.execute("UPDATE cuotas SET estado='pagada' WHERE id=%s AND estado<>'pagada'",
                       (cuota["id"],))
        registrar_accion(
            "mercadopago", "pago_mp_aplicado",
            f"cuota_id={cuota['id']} payment_id={payment_id} monto={monto_recibido} {moneda}",
        )
        return "pagada"
    _log.warning(
        "Pago MP aprobado no cubre la cuota: payment_id=%s cuota_id=%s "
        "esperado=%s %s recibido=%s %s",
        payment_id, cuota["id"], cuota["monto"], MP_MONEDA, monto_recibido, moneda,
    )
    cursor.execute("UPDATE cuotas SET estado='pendiente_verificacion' "
                   "WHERE id=%s AND estado<>'pagada'", (cuota["id"],))
    registrar_accion(
        "mercadopago", "pago_mp_no_cubre_cuota",
        f"cuota_id={cuota['id']} payment_id={payment_id} esperado={cuota['monto']} {MP_MONEDA} "
        f"recibido={monto_recibido} {moneda}",
    )
    return "pendiente_verificacion"


@router.post("/confirmar-manual")
def confirmar_pago_manual(data: ConfirmarManualRequest,
                          user: dict = Depends(get_chatbot_or_current_user)):
    """Registra una confirmación manual de pago. El admin deberá validarla."""
    es_staff = user.get("rol") in _STAFF
    if is_chatbot(user):
        if user.get("chatbot_alumno_id") != data.alumno_id:
            raise error("alumno_id no coincide con la sesión autenticada", 403)
    elif not es_staff and user.get("id") != data.alumno_id:
        raise error("Solo podés confirmar tus propias cuotas", 403)

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM cuotas WHERE id=%s AND alumno_id=%s",
                       (data.cuota_id, data.alumno_id))
        cuota = cursor.fetchone()
        if not cuota:
            raise error("Cuota no encontrada", 404)
        if cuota["estado"] == "pagada":
            raise error("La cuota ya está pagada", 400)

        cursor.execute(
            "UPDATE cuotas SET comprobante_manual=%s, confirmado_por_alumno=TRUE, "
            "estado='pendiente_verificacion' WHERE id=%s",
            (data.comprobante, data.cuota_id),
        )
        conn.commit()
    finally:
        conn.close()
    registrar_accion(user.get("sub", ""), "confirmar_pago_manual",
                     f"cuota_id={data.cuota_id} alumno_id={data.alumno_id}")
    return {
        "ok": True,
        "mensaje": "Confirmación registrada. Un administrador validará tu pago en breve.",
    }


@router.post("/generar-factura-pdf")
def generar_factura_pdf_endpoint(data: GenerarFacturaPdfRequest,
                                 user: dict = Depends(get_chatbot_or_current_user)):
    """Genera (o reutiliza) un PDF de comprobante para una cuota."""
    import os

    from ..services.pdf_service import FACTURAS_DIR

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT c.id, c.concepto, c.monto, c.fecha_vencimiento, c.alumno_id, c.pdf_url, "
            "       u.nombre, u.email, u.dni, cur.nombre AS curso "
            "FROM cuotas c JOIN usuarios u ON c.alumno_id = u.id "
            "LEFT JOIN cursos cur ON u.curso_id = cur.id "
            "WHERE c.id = %s",
            (data.cuota_id,),
        )
        cuota = cursor.fetchone()
        if not cuota:
            raise error("Cuota no encontrada", 404)

        es_staff = user.get("rol") in _STAFF
        if is_chatbot(user):
            if user.get("chatbot_alumno_id") != cuota["alumno_id"]:
                raise error("alumno_id no coincide con la sesión autenticada", 403)
        elif not es_staff and user.get("id") != cuota["alumno_id"]:
            raise error("Sin permisos para esta cuota", 403)

        existing_url = cuota.get("pdf_url")
        if existing_url:
            filename = existing_url.rsplit("/", 1)[-1]
            if os.path.isfile(os.path.join(FACTURAS_DIR, filename)):
                return {"ok": True, "pdf_url": existing_url,
                        "cuota_id": data.cuota_id, "reused": True}

        try:
            pdf_url = generar_factura_pdf(
                nombre=cuota["nombre"],
                email=cuota["email"],
                dni=cuota.get("dni"),
                curso=cuota.get("curso"),
                concepto=cuota["concepto"],
                monto=float(cuota["monto"]),
                vencimiento=str(cuota["fecha_vencimiento"]),
            )
        except Exception as e:
            raise error(f"Error generando PDF: {e}", 500)

        cursor.execute("UPDATE cuotas SET pdf_url=%s WHERE id=%s",
                       (pdf_url, data.cuota_id))
        conn.commit()
    finally:
        conn.close()

    registrar_accion(user.get("sub", ""), "generar_factura_pdf", f"cuota_id={data.cuota_id}")
    return {"ok": True, "pdf_url": pdf_url, "cuota_id": data.cuota_id, "reused": False}


@router.get("/pendiente-verificacion")
def listar_pendiente_verificacion(user: dict = Depends(require_rol(*_STAFF))):
    """Lista cuotas pendientes de verificación manual. Solo admin/administrativo."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT c.id, c.concepto, c.monto, c.fecha_vencimiento, c.comprobante_manual, "
            "       u.nombre AS alumno_nombre, u.email AS alumno_email "
            "FROM cuotas c JOIN usuarios u ON c.alumno_id = u.id "
            "WHERE c.estado = 'pendiente_verificacion' "
            "ORDER BY c.fecha_vencimiento ASC"
        )
        cuotas = cursor.fetchall()
    finally:
        conn.close()
    for c in cuotas:
        if hasattr(c.get("fecha_vencimiento"), "strftime"):
            c["fecha_vencimiento"] = c["fecha_vencimiento"].strftime("%Y-%m-%d")
    return {"ok": True, "cuotas": cuotas, "total": len(cuotas)}


# ── Historial del alumno autenticado (Fase 3) ────────────────────────────────

@router.get("/historial")
def historial_pagos(
    desde: Optional[date] = Query(default=None),
    hasta: Optional[date] = Query(default=None),
    user: dict = Depends(get_current_user),
):
    """Historial de pagos del alumno autenticado, con filtros opcionales por fecha."""
    email = user.get("sub")
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
        usuario = cursor.fetchone()
        if not usuario:
            raise error("Usuario no encontrado", 404)
        alumno_id = usuario["id"]

        sql = (
            "SELECT c.id, c.concepto, c.monto, c.fecha_vencimiento, c.estado, "
            "       c.preference_id, c.pdf_url, c.fecha_creacion "
            "FROM cuotas c "
            "WHERE c.alumno_id=%s AND c.estado='pagada'"
        )
        params: list = [alumno_id]
        if desde:
            sql += " AND c.fecha_vencimiento >= %s"
            params.append(desde)
        if hasta:
            sql += " AND c.fecha_vencimiento <= %s"
            params.append(hasta)
        sql += " ORDER BY c.fecha_vencimiento DESC"

        cursor.execute(sql, tuple(params))
        pagados = [serialize_row(c) for c in cursor.fetchall()]
    finally:
        conn.close()

    return {
        "ok": True,
        "alumno_id": alumno_id,
        "filtros": {
            "desde": desde.isoformat() if desde else None,
            "hasta": hasta.isoformat() if hasta else None,
        },
        "total": len(pagados),
        "monto_total": round(sum(float(c["monto"]) for c in pagados), 2),
        "pagos": pagados,
    }


@pagos_root_router.post("/asignar-cuotas")
def asignar_cuotas(data: CuotasBulkRequest,
                   user: dict = Depends(require_rol(*_STAFF))):
    """Asigna cuotas en bulk a un alumno. Solo admin/administrativo."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.executemany(
            "INSERT INTO cuotas (alumno_id, concepto, monto, fecha_vencimiento) "
            "VALUES (%s, %s, %s, %s)",
            [(data.alumno_id, c.concepto, c.monto, c.fecha_vencimiento)
             for c in data.cuotas],
        )
        conn.commit()
    except Exception as e:
        raise error(f"Error asignando cuotas: {e}", 500)
    finally:
        conn.close()
    registrar_accion(user.get("sub", ""), "asignar_cuotas",
                     f"Asignadas {len(data.cuotas)} cuotas a alumno_id={data.alumno_id}")
    return {"ok": True, "mensaje": f"{len(data.cuotas)} cuotas asignadas"}


@pagos_root_router.get("/mis-cuotas")
def mis_cuotas(user: dict = Depends(get_current_user)):
    """Cuotas del alumno logueado."""
    email = user.get("sub", "")
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
        usuario = cursor.fetchone()
        if not usuario:
            raise error("Usuario no encontrado", 404)
        alumno_id = usuario["id"]
        cursor.execute(
            "UPDATE cuotas SET estado='vencida' "
            "WHERE alumno_id=%s AND estado='pendiente' AND fecha_vencimiento < CURDATE()",
            (alumno_id,),
        )
        if cursor.rowcount:
            registrar_accion(email, "marcar_cuotas_vencidas",
                             f"alumno_id={alumno_id} cuotas={cursor.rowcount}")
        conn.commit()
        cursor.execute(
            "SELECT * FROM cuotas WHERE alumno_id=%s ORDER BY fecha_vencimiento ASC",
            (alumno_id,),
        )
        cuotas = [serialize_row(c) for c in cursor.fetchall()]
    finally:
        conn.close()

    pendientes = [c for c in cuotas if c["estado"] == "pendiente"]
    vencidas   = [c for c in cuotas if c["estado"] == "vencida"]
    pagadas    = [c for c in cuotas if c["estado"] == "pagada"]
    return {
        "ok": True, "cuotas": cuotas,
        "pendientes": len(pendientes),
        "vencidas": len(vencidas),
        "pagadas": len(pagadas),
        "deuda_total": sum(float(c["monto"]) for c in pendientes + vencidas),
    }


@pagos_root_router.post("/crear-pago")
def crear_pago_mp(pago: PagoMPRequest, user: dict = Depends(get_current_user)):
    """Crea un pago libre en MercadoPago."""
    resultado = mercadopago_service.crear_pago(
        titulo=pago.titulo, monto=pago.monto, cantidad=pago.cantidad,
        email_pagador=str(pago.email) if pago.email else "",
        creado_por=user.get("sub", ""),
    )
    if not resultado["ok"]:
        raise error(resultado.get("error", "Error"), 400)
    registrar_accion(user.get("sub", ""), "crear_pago", f"{pago.titulo} ${pago.monto}")
    return resultado


@pagos_root_router.get("/verificar-pago/{preference_id}")
def verificar_pago_mp(preference_id: str, user: dict = Depends(puede_verificar_pago)):
    """Verifica el estado de un pago en MercadoPago."""
    resultado = mercadopago_service.verificar_pago(preference_id, user.get("sub"))
    if not resultado["ok"]:
        raise error(resultado.get("error", "Error"), 400)
    if resultado.get("estado") == "aprobado":
        try:
            conn = get_connection()
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id, monto, estado FROM cuotas WHERE preference_id=%s",
                               (preference_id,))
                for cuota in cursor.fetchall():
                    estado = _aplicar_pago_aprobado_a_cuota(
                        cursor, cuota, resultado.get("payment_id"),
                        resultado.get("monto"), resultado.get("moneda"))
                    if estado != "pagada":
                        resultado["advertencia"] = (
                            "El monto o la moneda del pago no coincide con la cuota. "
                            "Quedó pendiente de verificación."
                        )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"⚠️  Error actualizando cuota tras pago aprobado ({preference_id}): {e}")
            registrar_accion(user.get("sub", ""), "error_cuota_pago",
                             f"preference_id={preference_id} error={e}")
            resultado["advertencia"] = (
                "Pago aprobado en MP pero no se pudo actualizar la cuota. "
                "Contactá al administrador."
            )
    return resultado


@pagos_root_router.get("/pagos")
def ver_pagos(user: dict = Depends(require_rol(*_STAFF))):
    """Lista todos los pagos de MercadoPago (incluye emails de pagadores: solo staff)."""
    resultado = mercadopago_service.listar_pagos()
    if not resultado["ok"]:
        raise error(resultado.get("error", "Error"), 500)
    return resultado


@pagos_root_router.post("/pagar-cuota/{cuota_id}")
def pagar_cuota(cuota_id: int,
                data: Optional[PagarCuotaRequest] = None,
                user: dict = Depends(puede_pagar_cuota)):
    """Genera link de pago MP para una cuota específica."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT c.id, c.concepto, c.monto, c.estado, c.alumno_id, "
            "       u.email AS alumno_email "
            "FROM cuotas c JOIN usuarios u ON c.alumno_id = u.id "
            "WHERE c.id = %s",
            (cuota_id,),
        )
        cuota = cursor.fetchone()
    finally:
        conn.close()
    if not cuota:
        raise error("Cuota no encontrada", 404)
    if cuota["estado"] == "pagada":
        raise error("Esta cuota ya está pagada", 400)

    if is_chatbot(user):
        if not data or data.alumno_id is None:
            raise error("alumno_id requerido para llamadas del chatbot", 403)
        if data.alumno_id != cuota["alumno_id"]:
            raise error("alumno_id no coincide con el dueño de la cuota", 403)
        if user.get("chatbot_alumno_id") != cuota["alumno_id"]:
            raise error("alumno_id no coincide con la sesión autenticada", 403)
        email_pagador = cuota["alumno_email"]
        creado_por = "chatbot@amicana.com"
    else:
        email_pagador = ""
        creado_por = user.get("sub", "")

    try:
        resultado = mercadopago_service.crear_pago(
            titulo=cuota["concepto"], monto=float(cuota["monto"]), cantidad=1,
            email_pagador=email_pagador, creado_por=creado_por,
            external_reference=f"CUOTA_{cuota_id}"
        )
    except Exception as e:
        return {"ok": False, "error": f"Error al conectar con Mercado Pago: {str(e)}"}
    if resultado["ok"]:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE cuotas SET preference_id=%s WHERE id=%s",
                           (resultado["preference_id"], cuota_id))
            conn.commit()
        finally:
            conn.close()
        registrar_accion(creado_por, "pagar_cuota", f"Generó pago para cuota_id={cuota_id}")
    return resultado


@router.post("/aprobar/{cuota_id}")
def aprobar_pago_manual(cuota_id: int, user: dict = Depends(require_rol(*_STAFF))):
    """Aprueba una cuota pendiente_verificacion y la marca como pagada."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, estado FROM cuotas WHERE id=%s", (cuota_id,))
        cuota = cursor.fetchone()
        if not cuota:
            raise error("Cuota no encontrada", 404)
        if cuota["estado"] != "pendiente_verificacion":
            raise error("La cuota no está pendiente de verificación", 400)
        cursor.execute("UPDATE cuotas SET estado='pagada' WHERE id=%s", (cuota_id,))
        conn.commit()
    finally:
        conn.close()
    registrar_accion(user.get("sub", ""), "aprobar_pago_manual",
                     f"Cuota {cuota_id} aprobada manualmente")
    return {"ok": True, "mensaje": "Pago aprobado exitosamente"}


@router.post("/webhook")
async def webhook_mp(request: Request):
    """Webhook IPN para MercadoPago.

    Solo el parseo del body es async; la consulta a MP y a la BD son
    sincrónicas y corren en el threadpool para no bloquear el event loop.
    """
    query = request.query_params

    # MP envía notificaciones POST con topic/type=payment y data.id o id
    action = query.get("type") or query.get("topic")
    payment_id = query.get("data.id") or query.get("id")

    # También puede venir en el JSON body
    if request.headers.get("content-type") == "application/json":
        try:
            body = await request.json()
            if not action:
                action = body.get("type") or body.get("action")
            if not payment_id:
                payment_id = body.get("data", {}).get("id")
        except Exception:
            pass

    if not payment_id or action not in ("payment", "payment.created", "payment.updated"):
        return {"ok": True, "mensaje": "Notificación ignorada"}

    return await run_in_threadpool(
        _procesar_webhook_mp, str(payment_id),
        request.headers.get("x-signature", ""), request.headers.get("x-request-id", ""),
    )


def _procesar_webhook_mp(payment_id: str, x_sig: str, x_req: str) -> dict:
    """Valida la firma, consulta el pago en MP y lo aplica a pagos_mp y a la cuota."""
    from ..mercadopago_qr import _ESTADOS_MP
    from ..services.mercadopago_client import buscar_pago_por_id, verificar_firma_webhook

    # Validar firma HMAC-SHA256 de MercadoPago.
    # Si MP_WEBHOOK_SECRET no está configurado, se loguea la advertencia y
    # se continúa (modo permisivo — solo pensado para desarrollo local; en
    # producción la variable es obligatoria, ver chequeo de arranque en main.py).
    if os.environ.get("MP_WEBHOOK_SECRET"):
        if not verificar_firma_webhook(x_sig, x_req, payment_id):
            _log.warning("Webhook MP rechazado: firma inválida payment_id=%s", payment_id)
            return {"ok": False, "error": "Firma inválida"}
    else:
        _log.warning(
            "Webhook MP aceptado SIN validar firma (MP_WEBHOOK_SECRET no configurado) "
            "payment_id=%s — modo dev únicamente, nunca debería ocurrir en producción",
            payment_id,
        )

    resp = buscar_pago_por_id(payment_id)
    if not resp.get("ok"):
        return {"ok": False, "error": resp.get("error")}
        
    pago = resp.get("pago", {})
    estado_mp = pago.get("status", "unknown")
    estado_es = _ESTADOS_MP.get(estado_mp, estado_mp)
    external_reference = pago.get("external_reference", "")
    email = pago.get("payer", {}).get("email", "")
    metodo = pago.get("payment_method_id", "")
    
    if not external_reference:
        return {"ok": True, "mensaje": "Pago sin external_reference"}

    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        # 1. IDEMPOTENCIA: Verificar si este payment_id ya se procesó
        cursor.execute("SELECT estado FROM pagos_mp WHERE payment_id = %s", (payment_id,))
        pago_existente = cursor.fetchone()
        
        if pago_existente and pago_existente["estado"] == "aprobado" and estado_es == "aprobado":
            return {"ok": True, "mensaje": "Ya procesado"}

        # 2. Actualizar pagos_mp
        cursor.execute(
            """UPDATE pagos_mp
               SET estado = %s, payment_id = %s, email_pagador = %s,
                   metodo_pago = %s, fecha_pago = %s
               WHERE external_reference = %s""",
            (estado_es, payment_id, email, metodo, datetime.now(), external_reference),
        )
        registrar_accion("mercadopago", "webhook_pago_mp",
                         f"payment_id={payment_id} estado={estado_es} ref={external_reference}")

        # 3. Actualizar cuota
        if external_reference.startswith("CUOTA_"):
            cuota_id_str = external_reference.replace("CUOTA_", "")
            if cuota_id_str.isdigit():
                if estado_es == "aprobado":
                    cursor.execute("SELECT id, monto, estado FROM cuotas WHERE id=%s",
                                   (int(cuota_id_str),))
                    cuota = cursor.fetchone()
                    if cuota:
                        _aplicar_pago_aprobado_a_cuota(
                            cursor, cuota, payment_id,
                            pago.get("transaction_amount"), pago.get("currency_id"))
        
        conn.commit()
    except Exception:
        # 500 para que MercadoPago reintente la notificación.
        _log.exception("Error procesando webhook IPN payment_id=%s", payment_id)
        raise error("Error procesando el pago", 500)
    finally:
        conn.close()

    return {"ok": True}

