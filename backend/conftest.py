"""
conftest.py — garantiza que SECRET_KEY esté disponible antes de cualquier import.
Las credenciales reales de test se inyectan vía .env.test o CI secrets.
"""
import os

# Forzar antes de que pytest importe app.*
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_pytest_only")
os.environ.setdefault("MP_ACCESS_TOKEN", "TEST-fake-for-tests")

# Credenciales de test — definir en .env.test (ver .env.test.example)
os.environ.setdefault("TEST_USER_EMAIL", "test_amicana_pytest@mail.com")
os.environ.setdefault("TEST_USER_PASSWORD", "CONFIGURAR_EN_ENV_TEST")
os.environ.setdefault("TEST_ADMIN_EMAIL", "admin@amicana.com")
os.environ.setdefault("TEST_ADMIN_PASSWORD", "CONFIGURAR_EN_ENV_TEST")
