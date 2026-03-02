# Crypto Prediction Bot (Binance Testnet & IA)

Este repositorio contiene un ecosistema de trading algorítmico avanzado que utiliza **Inteligencia Artificial (Gemini o DeepSeek)** bajo una arquitectura de dos niveles: **Cerebro (IA)** y **Músculo (Script de Ejecución)**.

## 🚀 Características Principales
- **Razonamiento Autónomo (Brain vs Muscle):** La IA no solo da señales; genera un **Plan de Ejecución Blindado** (Contrato JSON) con puntos de entrada, salida, montos y cojines de seguridad técnicos.
- **Gestión Estricta de Capital:** Tú defines un presupuesto máximo (`--budget`) y la IA decide cuánto invertir en cada operación sin exceder nunca ese límite, independientemente de tu balance total.
- **Cojín de Seguridad IA:** La IA calcula dinámicamente rangos de precio seguros. Si el mercado rompe estos límites, el bot ejecuta un cierre de emergencia automáticamente.
- **Soporte Dual (Spot & Futuros):** Razonamiento diferenciado según el mercado. Estrategias de acumulación para Spot y gestión de riesgo/liquidación para Futuros.
- **Interfaz Gráfica Moderna:** Dashboard en tiempo real con React y FastAPI para monitorear planes activos y el historial de la DB.

## 📦 Instalación y Reset

### Requisitos: Python 3.8+, Node.js 18+

1. **Backend:** `pip install -r requirements.txt`
2. **Frontend:** `cd frontend && npm install`
3. **Reset del Sistema:** Para limpiar la base de datos y liquidar activos en Testnet antes de una nueva prueba:
   ```bash
   python scripts/reset_system.py
   ```

## 🤖 Flujo de Trabajo Colaborativo

### Paso 1: Escanear el mercado (Estrategia)
El Scanner detecta oportunidades y las guarda en la DB con un **ID único de escaneo** (ej. `SCAN_20231027_100000`).
```bash
python scripts/run_market_scanner_bot.py --capital 500 --provider deepseek --type both
```

### Paso 2: Ejecución Blindada (Táctica)
El bot de trading puede seguir el último escaneo general o uno específico usando el `--scan_id`. Esto evita usar recomendaciones obsoletas si realizas múltiples escaneos con diferentes configuraciones.
```bash
# Ejecutar usando la última recomendación disponible para el símbolo
python scripts/run_trading_bot.py --symbol SOL/USDT --budget 500 --market_type future

# Ejecutar forzando un grupo de escaneo específico
python scripts/run_trading_bot.py --symbol SOL/USDT --budget 500 --scan_id SCAN_20231027_100000
```

---

## ⚙️ Uso y Argumentos

### Bot de Trading (El Músculo)
| Argumento | Descripción | Valor por Defecto |
|-----------|-------------|-------------------|
| `--provider` | Proveedor de IA (`gemini` o `deepseek`) | `gemini` |
| `--symbol` | Par de trading (ej. `BTC/USDT`) | `BTC/USDT` |
| `--budget` | **[REQUERIDO]** Presupuesto máximo gestionable | — |
| `--market_type`| Tipo de mercado (`spot` o `future`) | `spot` |
| `--scan_id` | ID del grupo de escaneo a seguir (opcional) | `None` |
| `--timeframe` | Intervalo de análisis para la IA | `1h` |
| `--network` | Red: `sandbox`, `testnet`, `mainnet` | `sandbox` |

*Nota: Los precios de compra, venta, montos y Stop Loss son calculados automáticamente por la IA basándose en el análisis técnico real.*

### Escáner Estratégico
| Argumento | Descripción | Valor por Defecto |
|-----------|-------------|-------------------|
| `--capital` | Capital simulado para el ranking | `100.0` |
| `--quote` | Moneda base (ej. `USDT`) | `USDT` |
| `--type` | Mercado a escanear (`spot`, `future`, `both`) | `spot` |
| `--num-top` | Cantidad de activos a analizar | `15` |

## 📂 Estructura del Proyecto
- **`app/bot/trading_bot.py`**: El Músculo. Ejecuta el plan de la IA minuto a minuto.
- **`app/bot/ia/predictor.py`**: El Cerebro. Genera planes blindados y rankings de mercado.
- **`app/database.py`**: Persistencia de "Contratos" (Execution Plans) y Auditoría.
- **`scripts/reset_system.py`**: Utilidad para limpieza total del entorno.

## ⚠️ Notas de Seguridad
- El bot está optimizado para **Binance Testnet**. No uses fondos reales sin antes validar tus planes de ejecución en modo demo.
- La IA tiene acceso a tu balance real para contextualizar el riesgo, pero solo operará con el presupuesto asignado.
