"""Validadores reutilizables."""
import os
import re


_DNI_RE = re.compile(r"^\d{7,8}$")
_TEL_RE = re.compile(r"^\+?[\d\s\-]{8,15}$")


def validar_dni(dni: str) -> bool:
    """True si es un DNI argentino plausible (7 u 8 dígitos)."""
    if not isinstance(dni, str):
        return False
    return bool(_DNI_RE.match(dni.strip()))


def validar_telefono_ar(tel: str) -> bool:
    """True si el teléfono tiene formato argentino aceptable (8-15 dígitos, permite +, espacios, guiones)."""
    if not isinstance(tel, str):
        return False
    return bool(_TEL_RE.match(tel.strip()))


def validar_email_corporativo(email: str) -> bool:
    """True si el email pertenece al dominio corporativo configurado.

    Si EMAIL_DOMAIN_WHITELIST no está definida o es vacía, acepta cualquier
    email (modo dev). Si tiene valores (CSV de dominios), rechaza emails
    cuyo dominio no esté en la lista.
    """
    whitelist = os.environ.get("EMAIL_DOMAIN_WHITELIST", "").strip()
    if not whitelist:
        return True
    dominios = {d.strip().lower() for d in whitelist.split(",") if d.strip()}
    dominio = email.split("@")[-1].lower() if "@" in email else ""
    return dominio in dominios


def validar_password_fuerte(pw: str) -> bool:
    """True si la contraseña tiene ≥8 caracteres, al menos una letra y al menos un número."""
    return (
        len(pw) >= 8
        and any(c.isalpha() for c in pw)
        and any(c.isdigit() for c in pw)
    )
