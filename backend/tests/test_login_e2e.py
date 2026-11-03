"""Login que no delata qué emails existen, de punta a punta (uvicorn real + MySQL descartable).

Se omite sin SEC_DB_PORT y SEC_DB_DISPOSABLE=1 (ver test_seguridad_e2e.py, cuyo servidor se reusa).

Formas de fallar:
  - email inexistente y contraseña errónea responden distinto (status o mensaje);
  - el email inexistente responde mucho más rápido (no corre bcrypt) y se puede enumerar por tiempo;
  - pasa en /auth/login pero no en el alias legacy /login.
"""
import time

import pytest
import requests

from .test_seguridad_e2e import (  # noqa: F401  (server es un fixture)
    SEC_DISPOSABLE, SEC_HOST, SEC_PORT, VICTIMA, server,
)

pytestmark = pytest.mark.skipif(
    not (SEC_PORT and SEC_DISPOSABLE and SEC_HOST in ("127.0.0.1", "localhost")),
    reason="SEC_DB_PORT y SEC_DB_DISPOSABLE=1 no definidos: E2E de login omitido",
)

FANTASMA = "no-existe@amicana-sec-e2e.com"


def _intentar(base, ruta, email):
    t = time.perf_counter()
    if ruta == "/login":
        r = requests.post(base + ruta, data={"username": email, "password": "Incorrecta123"})
    else:
        r = requests.post(base + ruta, json={"email": email, "password": "Incorrecta123"})
    return r, time.perf_counter() - t


@pytest.mark.parametrize("ruta", ["/auth/login", "/login"])
def test_email_inexistente_y_password_erronea_responden_igual(server, ruta):
    # La víctima existe pero sin contraseña local; para tener "password errónea" real se usa el admin.
    admin = "admin@amicana.com"
    _intentar(server, ruta, admin)  # calienta (primer bcrypt/conexión)
    r_mal, t_mal = _intentar(server, ruta, admin)
    r_no, t_no = _intentar(server, ruta, FANTASMA)

    assert r_no.status_code == r_mal.status_code == 400
    assert r_no.json() == r_mal.json(), (r_no.text, r_mal.text)
    # Sin bcrypt para el inexistente tardaría milisegundos contra ~100+ ms del otro.
    assert t_no >= t_mal * 0.5, f"inexistente {t_no:.3f}s vs errónea {t_mal:.3f}s"
