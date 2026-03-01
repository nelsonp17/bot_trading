# Crypto Prediction Bot (Binance Testnet & AI)

Este repositorio contiene un bot de trading algorítmico avanzado que utiliza **Inteligencia Artificial (Gemini o DeepSeek)** para analizar el mercado y ejecutar operaciones en **Binance Spot Testnet**. Incluye gestión de riesgo y persistencia híbrida de datos.

## 🚀 Características Principales
- **Análisis con IA:** Consulta a modelos LLM para obtener señales de compra/venta con un nivel de confianza y un **razonamiento técnico**.
- **Ejecución de Órdenes:** Realiza operaciones reales en el entorno de prueba (Sandbox/Demo) o real de Binance.
- **Gestión de Riesgo (Colchón Automático):** El bot ahora puede **autodefinir** un rango de precios seguro (`min_price`, `max_price`) analizando la volatilidad. Puedes sobrescribirlo manualmente con `--min-price` y `--max-price`.
- **Gestión de Capital:** Configura la cantidad exacta de USDT a utilizar por operación (`--amount`).
- **Base de Datos Híbrida:** 
  - **SQLite:** Para desarrollo local (rápido y sin configuración).
  - **MongoDB:** Para despliegue en producción (Docker).

## 📦 Instalación

### En tu PC local (Desarrollo):
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
   # Edita .env y asegúrate de tener APP_ENV=development y tus API Keys
   ```

## ⚙️ Uso y Comandos

El bot es altamente configurable. La gran novedad es que ahora **la IA decide el colchón de seguridad** si no lo especificas.

### Ejecución con Colchón Automático (Recomendado)
```bash
python bot/main.py --symbol SOL/USDT --amount 20 --provider deepseek
```
*En este modo, el bot le pedirá a DeepSeek que defina el rango seguro basado en el análisis técnico actual.*

### Ejecución con Rango Manual
```bash
python bot/main.py --symbol BTC/USDT --amount 50 --min-price 40000 --max-price 60000
```
*Aquí ignorará la sugerencia de la IA y solo operará si BTC está entre 40k y 60k.*

### Argumentos Disponibles
| Argumento | Descripción | Valor por Defecto |
|-----------|-------------|-------------------|
| `--provider` | Proveedor de IA (`gemini` o `deepseek`) | `gemini` |
| `--symbol` | Par de trading (ej. `ETH/USDT`) | `BTC/USDT` |
| `--timeframe` | Intervalo de velas (`15m`, `1h`, `4h`) | `1h` |
| `--amount` | Cantidad de USDT por operación | `100.0` |
| `--min-price` | Precio mínimo (0 = Automático por IA) | `0.0` |
| `--max-price` | Precio máximo (999999 = Automático por IA) | `999999.0` |
| `--network` | Red: `sandbox`, `testnet`, `mainnet`, `demo` | `sandbox` |

## 🐳 Despliegue en Producción (Docker)

Para ejecutar en un VPS con MongoDB:

1. Asegúrate de que tu `.env` tenga `APP_ENV=production`.
2. Ejecuta el script de despliegue:
   ```bash
   bash deploy.sh
   ```
   *Esto levantará los contenedores de Docker en segundo plano.*

## 📂 Estructura del Proyecto
- **`bot/main.py`**: Lógica principal, conexión a Binance, ejecución de órdenes y ciclo de vida.
- **`bot/predictor.py`**: Integración con las APIs de IA (Gemini/DeepSeek) y generación de prompts.
- **`bot/database.py`**: Capa de persistencia (SQLite/MongoDB) para guardar predicciones, razonamientos y trades.
- **`GEMINI.md`**: Documentación técnica optimizada para agentes de IA.

## ⚠️ Notas de Seguridad
- El bot está configurado en modo **Sandbox** por defecto.
- **Nunca subas tu archivo `.env`** con claves reales a un repositorio público.
