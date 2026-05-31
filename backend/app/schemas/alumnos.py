"""Schemas de alumnos.

El alumno se crea sin password desde el panel admin: el alumno luego se
registra con su email para fijar la suya. Por eso `AlumnoCreate` no
acepta password.
"""
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


Modalidad = Literal["presencial", "virtual", "hibrido"]


class AlumnoCreate(BaseModel):
    """Cuerpo de POST /alumnos.

    El admin crea la ficha del alumno. El alumno deberá registrarse
    luego con el mismo email para crear su contraseña.
    Si `modalidad` no se envía, se hereda del curso al insertar.
    """
    nombre:    str  = Field(..., min_length=2, max_length=100)
    apellido:  str  = Field(..., min_length=2, max_length=100)
    email:     EmailStr
    dni:       str  = Field(..., pattern=r"^\d{7,8}$")
    telefono:  str  = Field(..., pattern=r"^\d{8,15}$")
    curso_id:  int  = Field(..., ge=1)
    modalidad: Optional[Modalidad] = None

    @field_validator("nombre", "apellido")
    @classmethod
    def trim_y_no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("No puede estar vacío")
        return v


class AlumnoUpdate(BaseModel):
    """Cuerpo de PUT /alumnos/{id}. Todos los campos opcionales (PATCH-style)."""
    nombre:    Optional[str]       = Field(default=None, min_length=2, max_length=100)
    apellido:  Optional[str]       = Field(default=None, min_length=2, max_length=100)
    email:     Optional[EmailStr]  = None
    dni:       Optional[str]       = Field(default=None, pattern=r"^\d{7,8}$")
    telefono:  Optional[str]       = Field(default=None, pattern=r"^\d{8,15}$")
    curso_id:  Optional[int]       = Field(default=None, ge=1)
    modalidad: Optional[Modalidad] = None


class AlumnoResponse(BaseModel):
    id:              int
    nombre:          str
    apellido:        Optional[str] = None
    email:           str
    dni:             Optional[str] = None
    telefono:        Optional[str] = None
    curso_id:        Optional[int] = None
    curso:           Optional[str] = None
    modalidad:       Optional[Modalidad] = None
    modalidad_curso: Optional[Modalidad] = None

    model_config = {"from_attributes": True}
