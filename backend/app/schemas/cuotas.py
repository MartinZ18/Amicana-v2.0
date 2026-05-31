from datetime import date
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class CuotaItem(BaseModel):
    """Item de cuota dentro de un bulk asignar-cuotas."""
    alumno_id: int = Field(..., ge=1)
    concepto: str = Field(..., min_length=1, max_length=200)
    monto: float = Field(..., gt=0, le=1_000_000)
    fecha_vencimiento: date


class CuotaCreate(BaseModel):
    """Cuerpo de POST /cuotas (creación individual)."""
    alumno_id: int = Field(..., ge=1)
    concepto: str = Field(..., min_length=1, max_length=200)
    monto: float = Field(..., gt=0, le=1_000_000)
    fecha_vencimiento: date
    descripcion: Optional[str] = Field(default=None, max_length=255)

    @field_validator("fecha_vencimiento")
    @classmethod
    def fecha_no_en_pasado(cls, v: date) -> date:
        if v < date.today():
            raise ValueError("La fecha de vencimiento no puede ser en el pasado")
        return v


class CuotasBulkRequest(BaseModel):
    """Cuerpo de POST /asignar-cuotas (bulk)."""
    alumno_id: int = Field(..., ge=1)
    cuotas: List[CuotaItem] = Field(..., min_length=1)


class CuotaResponse(BaseModel):
    id: int
    alumno_id: int
    concepto: str
    monto: float
    fecha_vencimiento: str
    estado: Literal["pendiente", "vencida", "pagada", "pendiente_verificacion"]
    preference_id: Optional[str] = None
    pdf_url: Optional[str] = None
