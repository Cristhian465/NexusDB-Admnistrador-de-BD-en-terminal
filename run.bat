@echo off
title DBAdmin CLI - Unified Runner
echo =======================================================
echo   DBAdmin CLI - Instalador y Ejecutador Automatico
echo =======================================================
echo [Soporta: BD-CLI + SafeBridge local + Migrador ETL]
echo.

:: 1. Verificar si Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no esta instalado o no se encuentra en el PATH.
    echo Por favor instala Python 3.10 o superior para ejecutar esta aplicacion.
    echo.
    pause
    exit /b 1
)

:: 2. Crear entorno virtual si no existe
if not exist .venv (
    echo [INFO] Creando entorno virtual de Python .venv...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)

:: 3. Activar entorno virtual e instalar dependencias
echo [INFO] Activando entorno virtual...
call .venv\Scripts\activate

echo [INFO] Instalando/Actualizando dependencias desde src/requirements.txt...
pip install -r src\requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Hubo un error al instalar las dependencias.
    pause
    exit /b 1
)

:: 4. Ejecutar la aplicación
echo [INFO] Iniciando DBAdmin CLI...
echo.
python src\main.py

pause
