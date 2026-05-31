"""Logging interno de eventos del sistema.

La tabla `auditoria` y el panel admin de auditoría se eliminaron en la
migración 004. Este módulo se conserva como shim de logging para que los
routers existentes (pagos, avisos, alumnos, auth, etc.) sigan emitiendo
eventos al stderr del backend sin escribir en BD.

Si en el futuro hace falta volver a persistir auditoría, recrear la tabla
y reemplazar el `logger.info` por la inserción correspondiente.
"""
import logging
from typing import Optional

logger = logging.getLogger("amicana.audit")


def registrar(usuario_email: Optional[str], accion: str,
              detalle: str = "", ip: str = "") -> None:
    """Loguea un evento de negocio. Nunca lanza excepción."""
    logger.info("audit user=%s action=%s detail=%s ip=%s",
                usuario_email or "-", accion, detalle, ip)
