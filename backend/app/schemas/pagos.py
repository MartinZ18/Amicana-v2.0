from datetime import date
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class PagoMPRequest(BaseModel):
    """Cuerpo de POST /crear-pago (legacy)."""
    titulo: str = Field(..., min_length=1, max_length=200)
    monto: float = Field(..., gt=0, le=1_000_000)
    cantidad: int = Field(default=1, ge=1, le=100)
    email: Optional[EmailStr] = None


class ConfirmarManualRequest(BaseModel):
    """Cuerpo de POST /pagos/confirmar-manual."""
    alumno_id: int = Field(..., ge=1)
    cuota_id: int = Field(..., ge=1)
    comprobante: str = Field(..., min_length=1, max_length=200)


class GenerarFacturaPdfRequest(BaseModel):
    cuota_id: int = Field(..., ge=1)


class PagarCuotaRequest(BaseModel):
    """Cuerpo opcional de POST /pagar-cuota/{id}.

    El alumno_id solo se usa cuando llega del chatbot (n8n) para validar
    contra el dueño real de la cuota.
    """
    alumno_id: Optional[int] = Field(default=None, ge=1)


class HistorialFiltro(BaseModel):
    """Filtro opcional para GET /pagos/historial."""
    desde: Optional[date] = None
    hasta: Optional[date] = None
