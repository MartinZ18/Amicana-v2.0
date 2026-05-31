from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class ComunicadoCreate(BaseModel):
    """Cuerpo de POST /comunicados.

    Si `destinatarios = 'curso'`, `curso_id` pasa a ser obligatorio.
    """
    asunto:        str  = Field(..., min_length=1, max_length=200)
    cuerpo:        str  = Field(..., min_length=1, max_length=10000)
    destinatarios: Literal["todos", "curso"] = "todos"
    curso_id:      Optional[int] = Field(default=None, ge=1)

    @model_validator(mode="after")
    def curso_requerido_si_dirigido(self) -> "ComunicadoCreate":
        if self.destinatarios == "curso" and self.curso_id is None:
            raise ValueError("curso_id es obligatorio cuando destinatarios='curso'")
        return self


class ComunicadoResponse(BaseModel):
    id:                 int
    asunto:             str
    cuerpo:             str
    destinatarios:      str
    curso_id:           Optional[int] = None
    curso:              Optional[str] = None
    creado_por:         int
    creado_por_nombre:  Optional[str] = None
    fecha:              str
