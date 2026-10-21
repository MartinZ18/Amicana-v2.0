"""Operaciones sobre cuotas compartidas por varios routers."""


def marcar_cuotas_vencidas(conn, cursor) -> None:
    """Pasa a 'vencida' toda cuota 'pendiente' cuya fecha de vencimiento ya pasó.

    Se ejecuta al inicio de los endpoints de lectura que muestran el estado de
    cuotas, para que no devuelvan 'pendiente' sobre cuotas ya vencidas. Usa el
    índice idx_cuotas_estado_venc (migración 013).
    """
    cursor.execute("UPDATE cuotas SET estado='vencida' "
                   "WHERE estado='pendiente' AND fecha_vencimiento < CURDATE()")
    conn.commit()
