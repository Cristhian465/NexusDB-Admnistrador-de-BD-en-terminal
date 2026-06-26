#!/bin/bash
echo "======================================================="
echo "  DBAdmin CLI - Instalador y Ejecutador Automático"
echo "======================================================="
echo "[Soporta: BD-CLI + SafeBridge local + Migrador ETL]"
echo

# 1. Verificar si Python está instalado
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 no está instalado en el sistema."
    exit 1
fi

# 2. Crear entorno virtual si no existe
if [ ! -d ".venv" ]; then
    echo "[INFO] Creando entorno virtual de Python (.venv)..."
    python3 -m venv .venv
fi

# 3. Activar entorno virtual e instalar dependencias
echo "[INFO] Activando entorno virtual..."
source .venv/bin/activate

echo "[INFO] Instalando/Actualizando dependencias..."
pip install -r src/requirements.txt

# 4. Ejecutar la aplicación
echo "[INFO] Iniciando DBAdmin CLI..."
echo
python3 src/main.py
