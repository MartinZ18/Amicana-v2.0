"""Schemas para Mi Progreso (notas por unidad y sección)."""
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

Seccion = Literal["grammar", "vocabulary", "speaking", "listening", "writing", "reading"]


class NotaCreate(BaseModel):
    alumno_id:   int
    unidad_id:   int
    seccion:     Seccion
    nota:        float = Field(..., ge=0, le=10)
    pain_points: Optional[str] = Field(default=None, max_length=2000)
    fecha:       Optional[date] = None


class UnidadCreate(BaseModel):
    curso_id: int
    numero:   int = Field(..., ge=1, le=100)
    titulo:   str = Field(..., min_length=1, max_length=150)
    orden:    int = 0
    activa:   bool = True
