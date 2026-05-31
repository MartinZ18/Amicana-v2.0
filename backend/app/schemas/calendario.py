from datetime import date, time
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class ClaseCreate(BaseModel):
    """Cuerpo de POST /calendario."""
    curso_id:    int  = Field(..., ge=1)
    titulo:      str  = Field(..., min_length=1, max_length=150)
    fecha:       date
    hora_inicio: time
    hora_fin:    time
    descripcion: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def hora_fin_posterior(self) -> "ClaseCreate":
        if self.hora_fin <= self.hora_inicio:
            raise ValueError("La hora de fin debe ser posterior a la de inicio")
        return self


class ClaseUpdate(BaseModel):
    curso_id:    Optional[int]  = Field(default=None, ge=1)
    titulo:      Optional[str]  = Field(default=None, min_length=1, max_length=150)
    fecha:       Optional[date] = None
    hora_inicio: Optional[time] = None
    hora_fin:    Optional[time] = None
    descripcion: Optional[str]  = Field(default=None, max_length=2000)


class ClaseResponse(BaseModel):
    id:          int
    curso_id:    int
    curso:       Optional[str] = None
    titulo:      str
    fecha:       str
    hora_inicio: str
    hora_fin:    str
    descripcion: Optional[str] = None
