"""Schemas de cursos.

Modalidad y categoría se usan para filtros y badges en el panel admin.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


Modalidad = Literal["presencial", "virtual", "hibrido"]
Categoria = Literal["regular", "acelerado", "especial", "intensivo"]


class CursoCreate(BaseModel):
    nombre:      str  = Field(..., min_length=2, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=255)
    monto_cuota: float = Field(..., ge=0)
    modalidad:   Modalidad = "presencial"
    categoria:   Categoria = "regular"
    activo:      bool = True

    @field_validator("nombre")
    @classmethod
    def trim_nombre(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre no puede estar vacío")
        return v


class CursoUpdate(BaseModel):
    nombre:      Optional[str]       = Field(default=None, min_length=2, max_length=100)
    descripcion: Optional[str]       = Field(default=None, max_length=255)
    monto_cuota: Optional[float]     = Field(default=None, ge=0)
    modalidad:   Optional[Modalidad] = None
    categoria:   Optional[Categoria] = None
    activo:      Optional[bool]      = None


class CursoResponse(BaseModel):
    id:          int
    nombre:      str
    descripcion: Optional[str] = None
    monto_cuota: float
    modalidad:   Modalidad
    categoria:   Categoria
    activo:      bool

    model_config = {"from_attributes": True}
