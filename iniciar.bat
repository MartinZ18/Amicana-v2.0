@echo off
title AMICANA 2.0 — Servidor local
echo.
echo  ╔══════════════════════════════════════╗
echo  ║        AMICANA 2.0  - Arranque       ║
echo  ╚══════════════════════════════════════╝
echo.

REM ── Verificar que existe el venv ──────────────────────────────────────
if not exist "backend\venv\Scripts\activate.bat" (
    echo [ERROR] No se encontro el entorno virtual.
    echo         Ejecuta primero:  cd backend ^&^& python -m venv venv ^&^& pip install -r requirements.txt
    pause
    exit /b 1
)

REM ── Activar venv ─────────────────────────────────────────────────────
echo [1/2] Activando entorno virtual...
call backend\venv\Scripts\activate.bat

REM ── Iniciar servidor ─────────────────────────────────────────────────
echo [2/2] Iniciando FastAPI en http://localhost:8000/app
echo.
echo       Usa Ctrl+C para detener el servidor.
echo.
cd backend
uvicorn app.main:app --reload
