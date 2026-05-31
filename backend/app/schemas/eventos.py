"""Schemas de eventos institucionales.

Diferenciados de calendario_clases: no están atados a un curso.
"""
from datetime import date, time
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


TipoEvento = Literal["feriado", "conmemorativo", "intercambio", "evento", "otro"]


class _EventoBase(BaseModel):
    titulo:         str = Field(..., min_length=2, max_length=150)
    descripcion:    Optional[str] = None
    tipo:           TipoEvento = "evento"
    fecha_inicio:   date
    fecha_fin:      Optional[date] = None
    hora_inicio:    Optional[time] = None
    hora_fin:       Optional[time] = None
    todo_el_dia:    bool = False
    visible_alumno: bool = True

    @field_validator("titulo")
    @classmethod
    def trim_titulo(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El título no puede estar vacío")
        return v

    @model_validator(mode="after")
    def _validar_fechas_y_horas(self):
        if self.fecha_fin is not None and self.fecha_fin < self.fecha_inicio:
            raise ValueError("fecha_fin no puede ser anterior a fecha_inicio")
        if self.todo_el_dia:
            self.hora_inicio = None
            self.hora_fin = None
        elif self.hora_inicio is not None and self.hora_fin is not None:
            if self.hora_fin <= self.hora_inicio:
                raise ValueError("hora_fin debe ser posterior a hora_inicio")
        return self


class EventoCreate(_EventoBase):
    pass


class EventoUpdate(BaseModel):
    titulo:         Optional[str] = Field(default=None, min_length=2, max_length=150)
    descripcion:    Optional[str] = None
    tipo:           Optional[TipoEvento] = None
    fecha_inicio:   Optional[date] = None
    fecha_fin:      Optional[date] = None
    hora_inicio:    Optional[time] = None
    hora_fin:       Optional[time] = None
    todo_el_dia:    Optional[bool] = None
    visible_alumno: Optional[bool] = None

    @model_validator(mode="after")
    def _validar_fechas_y_horas(self):
        if (
            self.fecha_inicio is not None
            and self.fecha_fin is not None
            and self.fecha_fin < self.fecha_inicio
        ):
            raise ValueError("fecha_fin no puede ser anterior a fecha_inicio")
        if (
            self.hora_inicio is not None
            and self.hora_fin is not None
            and self.hora_fin <= self.hora_inicio
        ):
            raise ValueError("hora_fin debe ser posterior a hora_inicio")
        return self


class EventoResponse(_EventoBase):
    id:         int
    creado_por: Optional[int] = None

    model_config = {"from_attributes": True}
