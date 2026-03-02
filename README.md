# Crypto Prediction Bot (Binance Testnet & AI)

Este repositorio contiene un ecosistema de trading algorítmico avanzado que utiliza **Inteligencia Artificial (Gemini o DeepSeek)** para analizar el mercado, detectar oportunidades y ejecutar operaciones en **Binance Spot**.

Ahora incluye una arquitectura moderna dividida en un backend con **FastAPI** y un frontend moderno y responsivo desarrollado con **React**, **Vite** y **Tailwind CSS v4**.

## 🚀 Características Principales
- **Interfaz Gráfica Moderna (Dashboard):** Visualiza en tiempo real el estado del bot, las operaciones recientes, el presupuesto disponible y el registro de predicciones de la IA.
- **Análisis con IA Consciente:** La IA recibe el **balance real**, el **precio promedio de compra** de tus activos y el **historial de predicciones** recientes para aprender de errores pasados.
- **Lógica de Recuperación Automática:** Si el bot detecta una posición abierta (`holdings > 0`), bloquea nuevas compras con el presupuesto restante hasta que la posición actual se cierre (recuperación de capital).
- **Módulo de Escaneo Dinámico (Scanner):** Analiza automáticamente los activos con mayor movimiento en Binance (Top Volumen o Top Volatilidad) para generar un **Ranking de Rentabilidad**.
- **Ejecución Robusta y Precisa:** 
  - Manejo automático de filtros de Binance (`LOT_SIZE`, `STEP_SIZE`, `MIN_NOTIONAL`).
  - Sincronización automática de tiempo con los servidores de Binance.
- **Base de Datos Híbrida:** Persistencia de trades, predicciones y escaneos de mercado en **SQLite** o **MongoDB**.

## 📦 Instalación

### Requisitos Previos:
- Python 3.8+
- Node.js 18+ y npm

### 1. Configuración del Backend (Python)
1. Crea tu entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```
2. Instala las dependencias:
```bash
pip install -r requirements.txt
```
3. Configura el entorno:
```bash
cp .env.example .env
# Edita .env con tus API Keys de Binance y de la IA (Gemini/DeepSeek)
```

### 2. Configuración del Frontend (React)
1. Navega a la carpeta del frontend y descarga las dependencias:
```bash
cd frontend
npm install
```

## ⚙️ Uso y Modos de Ejecución

El proyecto está diseñado para ser usado desde la nueva interfaz web interactiva o de manera separada como scripts por consola.

### Interfaz Web (Dashboard 🚀)

Para levantar el ecosistema completo con la interfaz visual, abre dos consolas terminales diferentes:

**Terminal 1 (Backend - FastAPI):**
Desde la carpeta raíz del proyecto, inicializa la API:
```bash
#uvicorn app.api:app --reload
python scripts/run_api_server.py
```

**Terminal 2 (Frontend - React):**
Levanta la interfaz web:
```bash
cd frontend
npm run dev
```

El Dashboard estará disponible en tu navegador (`http://localhost:5173` por defecto). Desde allí podrás **Iniciar/Detener** el bot y ver el registro en vivo.

### Ejecución Directa por Consola (Scripts Modulares)

**1. Bot Operativo (Ejecución Táctica):**
Puedes seguir ejecutando el bot directamente por consola (gestiona el capital para un par específico).
```bash
python scripts/run_trading_bot.py --symbol SOL/USDT --budget 500 --provider deepseek --network testnet
```

### Argumentos Disponibles
| Argumento | Descripción | Valor por Defecto |
|-----------|-------------|-------------------|
| `--provider` | Proveedor de IA (`gemini` o `deepseek`) | `gemini` |
| `--symbol` | Par de trading (ej. `ETH/USDT`) | `BTC/USDT` |
| `--timeframe` | Intervalo de velas (`15m`, `1h`, `4h`) | `1h` |
| `--budget` | Presupuesto total asignado al bot | — |
| `--min-price` | Precio mínimo (0 = Automático por IA) | `0.0` |
| `--max-price` | Precio máximo (999999 = Automático por IA) | `999999.0` |
| `--network` | Red: `sandbox`, `testnet`, `mainnet`, `demo` | `sandbox` |

**2. Escáner Estratégico (Análisis de Mercado):**
Rastrea Binance en busca de las mejores oportunidades del momento en Spot, Futuros o ambos simultáneamente.
```bash
# Ejemplo: Escanear ambos mercados (Spot y Futures) para un símbolo específico
python scripts/run_market_scanner_bot.py --symbol BTC/USDT --type both --provider gemini

# Ejemplo: Escanear top volumen en Futuros
python scripts/run_market_scanner_bot.py --type future --mode volume --capital 500
```

### Argumentos del Escáner
| Argumento | Descripción | Valor por Defecto |
|-----------|-------------|-------------------|
| `--provider` | Proveedor de IA (`gemini` o `deepseek`) | `gemini` |
| `--capital` | Capital ficticio para simular inversión | `100.0` |
| `--quote` | Moneda base del mercado (ej. `USDT`, `BTC`) | `USDT` |
| `--mode` | Filtro de búsqueda (`volume` o `volatility`) | `volume` |
| `--symbol` | (Opcional) Símbolo específico a analizar | `None` |
| `--type` | Mercado a analizar (`spot`, `future` o `both`) | `spot` |

## 📂 Estructura del Proyecto

- **`app/api.py`**: Interfaz de comunicación REST (FastAPI) que expone los endpoints para manejar el bot web y obtener históricos.
- **`app/bot/trading_bot.py`**: Motor táctico. Ejecuta órdenes y gestiona el balance 24/7 en un par específico con lógica de recuperación.
- **`app/bot/market_scanner_bot.py`**: Motor estratégico. Descubre los activos más calientes de Binance dinámicamente.
- **`app/predictor.py`**: Cerebro de IA compartido. Implementa lógica de "Fund Manager" y "Market Analyst" para Gemini y DeepSeek.
- **`app/database.py`**: Capa de persistencia. Calcula costos promedio y audita toda la operación.
- **`frontend/`**: Aplicación React + Vite responsable de la Interfaz Visual Moderna (Dashboard y Log UI).

## ⚠️ Notas de Seguridad
- **Testnet:** Se recomienda encarecidamente probar el bot en la red de pruebas (`testnet` o `sandbox`) antes de usar `mainnet`.
- Nunca compartas el `.env` con tus llaves reales.
