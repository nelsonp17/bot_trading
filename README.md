# Crypto Prediction Bot (Binance Testnet)

Este repositorio contiene un bot de trading algorítmico básico configurado para operar en **Binance Spot Testnet** (Paper Trading) y almacenar datos en **MongoDB**.

# Instalacción
## En tu PC local (Desarrollo):
1. Crea tu entorno virtual: `python -m venv venv`
2. Actívalo e instala: `pip install -r requirements.txt`
3. Copia el .env: `cp .env.example .env` (asegúrate que APP_ENV=development).
4. Lanza el bot: `python bot/main.py`
    * Verás logs como: `[SQLite] Predicción guardada: BUY`

## En el VPS (Producción):
1. Usas el script bash deploy.sh.
2. El archivo .env en el servidor debe tener APP_ENV=production.
3. Docker levantará MongoDB y el bot se conectará a él automáticamente.

## Stack Tecnológico
- **Lenguaje:** Python 3.10+
- **Exchange:** CCXT (Binance Sandbox)
- **Base de Datos:** MongoDB
- **Despliegue:** Docker & Docker Compose

## Modos de Ejecución

### 1. Desarrollo Local (SQLite, sin Docker)
Ideal para desarrollo rápido sin dependencias pesadas.
```bash
# Crear entorno virtual e instalar dependencias
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configurar .env (asegúrate que APP_ENV=development)
cp .env.example .env
python bot/main.py
```
*Los datos se guardarán en `trading_bot.db` automáticamente.*

### 2. Producción (MongoDB + Docker)
Ideal para VPS.
```bash
bash deploy.sh
```
*Requiere cambiar `APP_ENV=production` en el `.env`.*

## Estructura de Archivos
- `bot/main.py`: Punto de entrada, conexión a exchange y loop principal.
- `bot/database.py`: Clase `MongoManager` para persistencia.
- `docker-compose.yml`: Define los servicios de MongoDB y el Bot.

## Notas de Seguridad
- Nunca subas el archivo `.env` a un repositorio público.
- El archivo `deploy.sh` se encarga de levantar los servicios en modo *detached* (`-d`).

---
*Desarrollado para propósitos educativos de simulación.*
