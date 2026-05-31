from typing import Optional
from pydantic import BaseModel, Field


class AvisoCreate(BaseModel):
    """Cuerpo de POST /avisos."""
    titulo: str = Field(..., min_length=1, max_length=150)
    contenido: str = Field(..., min_length=1, max_length=5000)
    importante: bool = False


class AvisoUpdate(BaseModel):
    """Cuerpo de PUT /avisos/{id}."""
    titulo: Optional[str] = Field(default=None, min_length=1, max_length=150)
    contenido: Optional[str] = Field(default=None, min_length=1, max_length=5000)
    importante: Optional[bool] = None
    activo: Optional[bool] = None


class AvisoResponse(BaseModel):
    id: int
    titulo: str
    contenido: str
    importante: bool
    fecha_publicacion: str
    creado_por: int
    creado_por_nombre: Optional[str] = None
    activo: bool
