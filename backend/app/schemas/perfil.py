from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator

from ..utils.validators import validar_password_fuerte


class PerfilUpdate(BaseModel):
    """Cuerpo de PUT /perfil. Solo telefono y email; el resto de los campos
    (nombre, dni, rol) NO se modifican desde el perfil del alumno."""
    telefono: Optional[str] = Field(default=None, pattern=r"^\+?[\d\s\-]{8,15}$")
    email: Optional[EmailStr] = None


class CompletarPerfilInput(BaseModel):
    """Cuerpo de PUT /perfil/completar. Solo para cubrir campos faltantes tras login Google."""
    dni: Optional[str] = Field(default=None, pattern=r"^\d{7,8}$")
    telefono: Optional[str] = Field(default=None, pattern=r"^\+?[\d\s\-]{8,15}$")
    password: Optional[str] = Field(default=None, min_length=8, max_length=255)

    @field_validator("password")
    @classmethod
    def password_debe_ser_fuerte(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not validar_password_fuerte(v):
            raise ValueError(
                "La contraseña debe tener al menos 8 caracteres, una letra y un número"
            )
        return v


class PasswordUpdate(BaseModel):
    """Cuerpo de PUT /perfil/password.

    Requiere la password actual para validar identidad y la nueva (mínimo 8).
    """
    password_actual: str = Field(..., min_length=1, max_length=255)
    password_nueva:  str = Field(..., min_length=8, max_length=255)


class SetearPasswordInput(BaseModel):
    """Cuerpo de POST /perfil/setear-password."""
    password: str = Field(..., min_length=8, max_length=255)

    @field_validator("password")
    @classmethod
    def password_debe_ser_fuerte(cls, v: str) -> str:
        if not validar_password_fuerte(v):
            raise ValueError(
                "La contraseña debe tener al menos 8 caracteres, una letra y un número"
            )
        return v


class PerfilResponse(BaseModel):
    id: int
    nombre: str
    email: str
    rol: str
    auth_provider: Optional[str] = None
    tiene_password_local: bool = False
    dni: Optional[str] = None
    telefono: Optional[str] = None
    curso: Optional[str] = None
    modalidad: Optional[str] = None
    modalidad_curso: Optional[str] = None
