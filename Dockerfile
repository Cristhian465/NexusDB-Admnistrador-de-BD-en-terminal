FROM python:3.10-slim

# Instalar cliente de Docker para permitir validación en sandbox local (DooD)
RUN apt-get update && apt-get install -y \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar e instalar requerimientos primero para caché de capas
COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el proyecto
COPY . .

WORKDIR /app/src

# Comando por defecto para iniciar interactivo
CMD ["python", "main.py"]
