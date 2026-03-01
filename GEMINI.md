# Trading Bot with AI - Project Overview

Este proyecto es un bot de trading automatizado que utiliza modelos de Inteligencia Artificial (Gemini y DeepSeek) para analizar datos del mercado de criptomonedas y generar señales de inversión.

## 🚀 Propósito
El bot descarga datos históricos (OHLCV) de exchanges (vía CCXT), los procesa con Pandas y los envía a un modelo de lenguaje (LLM) para obtener una recomendación de trading (`COMPRA`, `VENTA`, `MANTENER`) con un nivel de confianza y razonamiento técnico en español.

## 🏗️ Arquitectura
- **`bot/main.py`**: Punto de entrada principal. Gestiona el ciclo de vida del bot, la conexión con Binance (Testnet) y la ejecución de órdenes de mercado. Implementa una estrategia de "colchón" de seguridad basada en rangos de precio.
- **`bot/predictor.py`**: Implementa el patrón Factory para manejar múltiples proveedores de IA (Gemini/DeepSeek) y generar predicciones en formato JSON.
- **`bot/database.py`**: Gestiona la persistencia de las predicciones (incluyendo el razonamiento de la IA) y los trades realizados.
    - **SQLite**: Utilizado por defecto en desarrollo.
    - **MongoDB**: Configurado para entornos de producción.

## 🛠️ Stack Tecnológico
- **Lenguaje**: Python 3.x
- **Bases de Datos**: SQLite (Dev) / MongoDB (Prod)
- **Librerías Clave**:
    - `ccxt`: Interacción con exchanges y ejecución de órdenes.
    - `pandas`: Manipulación y análisis de datos.
    - `google-genai` / `openai`: Integración con modelos de IA.

## ⚙️ Configuración y Uso
El bot acepta los siguientes argumentos por línea de comandos:
- `--provider`: `gemini` (por defecto) o `deepseek`.
- `--symbol`: Par de trading, ej. `BTC/USDT`.
- `--timeframe`: Intervalo de velas, ej. `1h`, `15m`.
- `--amount`: Cantidad en USDT a invertir por operación.
- `--min-price`: Precio mínimo por debajo del cual no se comprará (Colchón).
- `--max-price`: Precio máximo por encima del cual no se comprará (Colchón).
- `--network`: Red de operación (`sandbox`, `testnet` para pruebas, `mainnet` para real).

## ⚠️ Nota de Seguridad
El bot está configurado en modo **Sandbox (Testnet)** para evitar el uso de fondos reales. Nunca compartas tus API Keys reales.
