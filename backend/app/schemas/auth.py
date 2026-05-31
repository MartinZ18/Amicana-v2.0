from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator

from ..utils.validators import validar_email_corporativo, validar_password_fuerte


ROLES = ("admin", "administrativo", "alumno")


class UsuarioCreate(BaseModel):
    """Cuerpo de POST /auth/register."""
    nombre: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    rol: Literal["admin", "administrativo", "alumno"] = "alumno"

    @field_validator("nombre")
    @classmethod
    def trim_nombre(cls, v: str) -> str:
        return v.strip()

    @field_validator("email")
    @classmethod
    def email_corporativo(cls, v: str) -> str:
        if not validar_email_corporativo(str(v)):
            raise ValueError("Email no permitido por la política corporativa")
        return v

    @field_validator("password")
    @classmethod
    def password_debe_ser_fuerte(cls, v: str) -> str:
        if not validar_password_fuerte(v):
            raise ValueError(
                "La contraseña debe tener al menos 8 caracteres, una letra y un número"
            )
        return v


class UsuarioCreateLegacy(BaseModel):
    """Cuerpo del alias deprecated /usuarios.

    Unificado con /auth/register: mínimo 8 caracteres, letra y número.
    """
    nombre: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    rol: Literal["admin", "administrativo", "alumno"] = "alumno"

    @field_validator("password")
    @classmethod
    def password_debe_ser_fuerte(cls, v: str) -> str:
        if not validar_password_fuerte(v):
            raise ValueError(
                "La contraseña debe tener al menos 8 caracteres, una letra y un número"
            )
        return v


class LoginRequest(BaseModel):
    """Cuerpo de POST /auth/login (JSON, no form)."""
    email: EmailStr
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Respuesta estándar de login (JWT)."""
    access_token: str
    token_type: str = "bearer"
    rol: str
    nombre: Optional[str] = None
    id: Optional[int] = None


class MeResponse(BaseModel):
    """Respuesta de GET /auth/me."""
    id: int
    nombre: str
    email: str
    rol: str
    dni: Optional[str] = None
    telefono: Optional[str] = None
    auth_provider: str = "local"
