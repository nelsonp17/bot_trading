#!/bin/bash

# Script de despliegue automático para VPS
echo "--- Iniciando Despliegue del Bot de Trading ---"

# 1. Verificar si existe el archivo .env
if [ ! -f .env ]; then
    echo "[!] Archivo .env no encontrado. Creando uno desde la plantilla..."
    cp .env.example .env
    echo "[*] Por favor, edita el archivo .env con tus API Keys antes de continuar."
    exit 1
fi

# 2. Actualizar repositorio (si aplica)
# git pull origin main

# 3. Re-construir y levantar contenedores
docker compose down
docker compose up -d --build

echo "--- Despliegue completado con éxito ---"
docker compose ps
