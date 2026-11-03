"""Tokens emitidos antes de cambiar de librería JWT siguen validando.

Los tokens se arman a mano con el formato que emitía python-jose (HS256, mismo SECRET_KEY).
"""
import base64
import hashlib
import hmac
import json
import os

import pytest
from fastapi import HTTPException

from app.auth import _decodificar, create_access_token

def _token_estilo_jose(claims: dict) -> str:
    """HS256 armado a mano con el mismo encoding que python-jose (header con typ, JSON compacto
    en orden de inserción, base64url sin padding), sin depender de ninguna librería JWT."""
    def b64(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    cuerpo = b64(json.dumps(claims, separators=(",", ":")).encode())
    firma = hmac.new(os.environ["SECRET_KEY"].encode(), f"{header}.{cuerpo}".encode(), hashlib.sha256).digest()
    return f"{header}.{cuerpo}.{b64(firma)}"


TOKEN_VIEJO = _token_estilo_jose({"sub": "viejo@amicana.com", "rol": "alumno", "id": 7, "exp": 4102444800})
TOKEN_VENCIDO = _token_estilo_jose({"sub": "viejo@amicana.com", "exp": 1000000000})


def test_token_emitido_con_la_libreria_anterior_sigue_valido():
    p = _decodificar(TOKEN_VIEJO)
    assert (p["sub"], p["rol"], p["id"]) == ("viejo@amicana.com", "alumno", 7)


def test_token_nuevo_se_decodifica_con_sus_claims_y_exp():
    p = _decodificar(create_access_token({"sub": "a@b.com", "rol": "admin", "id": 1}))
    assert p["sub"] == "a@b.com" and p["rol"] == "admin" and isinstance(p["exp"], int)


@pytest.mark.parametrize("token", [TOKEN_VENCIDO, "basura", TOKEN_VIEJO[:-3] + "AAA", ""])
def test_vencido_o_invalido_es_401(token):
    with pytest.raises(HTTPException) as e:
        _decodificar(token)
    assert e.value.status_code == 401
