# Crypto Prediction Bot (Binance Testnet & IA)

Este repositorio contiene un ecosistema de trading algorítmico avanzado que utiliza **Inteligencia Artificial (Gemini o DeepSeek)** bajo una arquitectura de dos niveles: **Cerebro (IA)** y **Músculo (Script de Ejecución)**.

---

## Tabla de Contenidos

1. [Características Principales](#-características-principales)
2. [Arquitectura](#-arquitectura)
3. [Instalación](#-instalación)
4. [Uso Básico](#-uso-básico)
5. [Comandos Detallados](#-comandos-detallados)
6. [Circuit Breaker](#-circuit-breaker)
7. [Gestión de Riesgos](#-gestión-de-riesgos)
8. [Indicadores Técnicos](#-indicadores-técnicos)
9. [Estrategias de Salida](#-estrategias-de-salida)
10. [Análisis Multi-Timeframe](#-análisis-multi-timeframe)
11. [Estructura del Proyecto](#-estructura-del-proyecto)
12. [Notas de Seguridad](#-notas-de-seguridad)
13. [FAQ](#-faq)
14. [Comandos Útiles](#-comandos-útiles)

---

## 🚀 Características Principales

- **Razonamiento Autónomo (Brain vs Muscle):** La IA no solo da señales; genera un **Plan de Ejecución Blindado** (Contrato JSON) con puntos de entrada, salida, montos y cojines de seguridad técnicos.
- **Sesiones de Ejecución (`run_script_id`):** Cada ejecución genera un ID único. Esto permite detener un bot y volverlo a ejecutar reanudando su estado financiero (ganancias, pérdidas e inversión actual) de forma independiente.
- **Gestión Estricta de Capital:** Tú defines un presupuesto máximo (`--budget`) y la IA decide cuánto invertir en cada operación sin exceder nunca ese límite.
- **Cojín de Seguridad IA:** La IA calcula dinámicamente rangos de precio seguros. Si el mercado rompe estos límites, el bot ejecuta un cierre de emergencia automáticamente.
- **Soporte Dual (Spot & Futuros):** Razonamiento diferenciado según el mercado.
- **Órdenes LIMIT:** Control preciso del precio de entrada para evitar slippage.
- **Circuit Breaker:** Protección automática contra rachas de pérdidas.
- **Partial Take Profit:** Salida escalonada para asegurar ganancias.
- **Trailing Stop Dinámico:** Stop loss que sube con el precio.
- **Indicadores Técnicos:** RSI, MACD, EMA, ATR, Bollinger Bands, Estocástico.
- **Análisis Multi-Timeframe Automático:** El bot carga automáticamente configuración óptima de `timeframes_config.json` (generado por IA) y usa el timeframe primary para análisis.

---

## 🧠 Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                        MERCADO (Binance)                        │
└─────────────────────────────────────────────────────────────────┘
                                ▲
                                │ OHLCV, Orders
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     TRADING BOT (Muscle)                         │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ Validación  │  │ Ejecución   │  │ Gestión de Riesgo  │    │
│  │ JSON Plan   │  │ Órdenes     │  │ Circuit Breaker    │    │
│  └─────────────┘  └──────────────┘  └────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ Plans, Recommendations
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PREDICTOR (Brain - IA)                       │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ Gemini      │  │ DeepSeek     │  │ Indicadores Tech.  │    │
│  │ 2.0 Flash  │  │ Chat         │  │ RSI,MACD,EMA,ATR   │    │
│  └─────────────┘  └──────────────┘  └────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MARKET SCANNER (Scanner)                      │
│  Escanea mercado, rankea oportunidades, genera recomendaciones  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BASE DE DATOS                               │
│  Plans, Trades, Run Scripts, Heartbeats                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📦 Instalación

### Requisitos

- **Python 3.8+**
- **Node.js 18+** (para frontend)
- **API Keys de Binance** (Testnet o Mainnet)
- **API Key de IA** (Gemini o DeepSeek)

### Pasos

1. **Clonar el repositorio:**
   ```bash
   git clone <repo_url>
   cd bot_trading
   ```

2. **Crear entorno virtual (opcional pero recomendado):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar variables de entorno:**
   ```bash
   cp .env.example .env
   # Edita .env con tus API Keys
   ```

5. **Instalar frontend (opcional):**
   ```bash
   cd frontend
   npm install
   ```

### Variables de Entorno (.env)

```bash
# Binance API Keys (Testnet)
BINANCE_TESTNET_API_KEY=tu_testnet_api_key
BINANCE_TESTNET_SECRET_KEY=tu_testnet_secret_key

# Binance API Keys (Mainnet)
BINANCE_API_KEY=tu_mainnet_api_key
BINANCE_SECRET_KEY=tu_mainnet_secret_key

# IA Providers
GEMINI_API_KEY=tu_gemini_api_key
DEEPSEEK_API_KEY=tu_deepseek_api_key

# Circuit Breaker (opcional, también se puede pasar por CLI)
MAX_CONSECUTIVE_LOSSES=3
CIRCUIT_BREAKER_COOLDOWN=300
```

---

## 🎯 Uso Básico

### Flujo de Trabajo Completo

```bash
# Paso 1: Escanear el mercado (genera oportunidades)
python scripts/run_market_scanner_bot.py \
  --provider gemini \
  --capital 500 \
  --type both

# Paso 2: Ejecutar trading (usa las oportunidades del scanner)
python scripts/run_trading_bot.py \
  --provider gemini \
  --symbol BTC/USDT \
  --budget 100 \
  --network sandbox
```

---

## ⚙️ Comandos Detallados

### Bot de Trading (`run_trading_bot.py`)

```bash
python scripts/run_trading_bot.py [OPCIONES]
```

| Argumento | Descripción | Valor por Defecto |
|-----------|-------------|-------------------|
| `--provider` | Proveedor de IA (`gemini` o `deepseek`) | `gemini` |
| `--symbol` | Par de trading (ej. `BTC/USDT`, `ETH/USDT`) | `BTC/USDT` |
| `--budget` | **[REQUERIDO]** Presupuesto máximo gestionable | — |
| `--market_type` | Tipo de mercado (`spot` o `future`) | `spot` |
| `--scan_id` | ID del escaneo específico a seguir | `None` |
| `--run_script_id` | ID de sesión para reanudar estado | `None` |
| `--timeframe` | Intervalo de análisis fallback (se usa si no existe `timeframes_config.json`) | `1h` |
| `--network` | Red (`sandbox`, `testnet`, `mainnet`, `demo`) | `sandbox` |
| `--max_losses` | Máx. pérdidas consecutivas antes de parar | `3` |
| `--cooldown` | Segundos de espera tras circuit breaker | `300` |

**Ejemplos:**

```bash
# Ejecución básica en testnet
python scripts/run_trading_bot.py --symbol BTC/USDT --budget 100 --network sandbox

# Con circuit breaker personalizado
python scripts/run_trading_bot.py --symbol ETH/USDT --budget 200 --max_losses 5 --cooldown 600

# Reanudar sesión anterior
python scripts/run_trading_bot.py --symbol BTC/USDT --budget 100 --run_script_id "abc-123"

# En mercado de futuros
python scripts/run_trading_bot.py --symbol BTC/USDT --budget 100 --market_type future

# Con análisis multi-timeframe automático (carga timeframes_config.json)
python scripts/run_trading_bot.py --symbol BTC/USDT --budget 100
# El bot usará automáticamente el timeframe óptimo de timeframes_config.json
```

---

### Market Scanner (`run_market_scanner_bot.py`)

```bash
python scripts/run_market_scanner_bot.py [OPCIONES]
```

| Argumento | Descripción | Valor por Defecto |
|-----------|-------------|-------------------|
| `--provider` | Proveedor de IA (`gemini` o `deepseek`) | `gemini` |
| `--capital` | Capital simulado para el ranking | `100.0` |
| `--quote` | Moneda base (`USDT`, `USDC`, `BTC`) | `USDT` |
| `--mode` | Modo de selección (`volume` o `volatility`) | `volume` |
| `--symbol` | Símbolo específico a analizar | `None` |
| `--type` | Mercado (`spot`, `future`, `both`) | `spot` |
| `--num_top` | Cantidad de activos a analizar | `15` |
| `--run_script_id` | ID de sesión de escaneo | `None` |

**Ejemplos:**

```bash
# Escanear top 15 por volumen
python scripts/run_market_scanner_bot.py --capital 500 --type both

# Escanear por volatilidad
python scripts/run_market_scanner_bot.py --capital 500 --mode volatility

# Analizar un símbolo específico
python scripts/run_market_scanner_bot.py --symbol BTC/USDT
```

---

## 🛡️ Circuit Breaker

El Circuit Breaker es una protección automática que detiene el bot después de un número configurable de pérdidas consecutivas.

### Cómo Funciona

1. Cada vez que se cierra una posición perdedora, el contador de pérdidas consecutivas aumenta.
2. Cuando el contador alcanza `--max_losses` (default: 3), el bot se detiene.
3. Espera `--cooldown` segundos (default: 300 = 5 minutos) antes de continuar.
4. El contador se resetea después de una operación exitosa.

### Configuración

```bash
# Valores por defecto
--max_losses 3    # Detener después de 3 pérdidas seguidas
--cooldown 300    # Esperar 5 minutos

# Configuración agresiva
--max_losses 2 --cooldown 180

# Configuración conservadora
--max_losses 5 --cooldown 600
```

---

## 📊 Gestión de Riesgos

### Validación del Plan de Ejecución

Antes de ejecutar cualquier orden, el bot valida:

- ✅ `trigger_price` debe ser válido y razonable
- ✅ `allocated_capital_usdt` debe estar dentro del presupuesto
- ✅ `take_profit` debe ser mayor al precio de entrada
- ✅ `stop_loss` debe ser menor al precio de entrada
- ✅ SL debe ser menor que TP
- ✅ El precio de entrada no debe estar a más del 5% del precio actual
- ✅ SL no debe representar más del 10% de pérdida

### Reconfirmación de Balance

El bot verifica el balance real en el exchange **inmediatamente antes** de ejecutar cada orden para garantizar que hay fondos suficientes.

---

## 📈 Indicadores Técnicos

El bot calcula automáticamente los siguientes indicadores técnicos y los incluye en los prompts de la IA:

| Indicador | Descripción |
|-----------|-------------|
| **RSI (14, 21)** | Relative Strength Index - Sobrecomprado/Sobrevendido |
| **EMA (9, 21, 50, 200)** | Medias móviles exponenciales |
| **SMA (20, 50, 200)** | Medias móviles simples |
| **MACD** | Convergencia/Divergencia de Medias Móviles |
| **ATR (14)** | Average True Range - Volatilidad |
| **Bollinger Bands** | Bandas de Bollinger con posición |
| **Estocástico %K/%D** | Oscilador Estocástico |
| **OBV** | On-Balance Volume |
| **Volumen Ratio** | Volumen vs Media de 20 períodos |

---

## 💰 Estrategias de Salida

### Take Profit (TP) Fijo

El nivel de precio configurado en el plan donde se cierra la posición con ganancia.

### Partial Take Profit

Permite cerrar solo una porción de la posición en niveles escalonados:

```json
"exit_config": {
  "take_profit": 52000,
  "partial_tp_levels": [
    {"price": 51500, "percent": 50},
    {"price": 52000, "percent": 50}
  ]
}
```

**Ejemplo:** Vende 50% cuando llegue a 51500, y el 50% restante cuando llegue a 52000.

### Trailing Stop

Stop loss dinámico que sube con el precio:

```json
"exit_config": {
  "take_profit": 52000,
  "stop_loss": 48000,
  "trailing_stop_activation_price": 50000,
  "trailing_stop_distance_percent": 2
}
```

**Ejemplo:** Cuando el precio suba de 50000, el SL dinámico será 2% por debajo del precio actual.

### Safety Cushion (Emergencia IA)

Rangos de precio calculados por la IA. Si el precio sale de estos límites, el bot cierra la posición inmediatamente:

```json
"safety_cushion": {
  "min_price_alert": 47000,
  "max_price_alert": 53000,
  "emergency_reasoning_trigger": "OUT_OF_RANGE"
}
```

---

## 📊 Análisis Multi-Timeframe

El bot **carga automáticamente** la configuración óptima de timeframes desde `data/timeframes/timeframes_config.json` (generado por el script de análisis). Esto significa que una vez que generes el archivo de configuración, el bot usará automáticamente el timeframe primary recomendado por la IA para cada símbolo.

### Uso Automático por el Bot

Cuando el bot inicia:
1. Busca `data/timeframes/timeframes_config.json` en la raíz del proyecto
2. Si encuentra configuración para el símbolo actual, usa `primary.timeframe` y `primary.history`
3. Si no hay configuración, usa el timeframe del parámetro `--timeframe` como fallback
4. Pasa el timeframe analizado a la IA para generar planes de ejecución precisos

### Script de Análisis de Timeframes

Antes de operar, puedes analizar qué timeframes son óptimos para cada símbolo usando IA:

```bash
python scripts/analyze_timeframes.py --symbol BTC/USDT
python scripts/analyze_timeframes.py --symbol BTC/USDT ETH/USDT SOL/USDT
python scripts/analyze_timeframes.py --symbol ALL  # Analiza los principales
```

### Opciones

| Argumento | Descripción | Valor por Defecto |
|-----------|-------------|-------------------|
| `--symbol` | Símbolo(s) a analizar | (requerido) |
| `--provider` | IA a usar (`gemini` o `deepseek`) | `gemini` |
| `--output` | Archivo de salida | `data/timeframes/timeframes_config.json` |
| `--timeframes` | Timeframes a analizar | `1m,5m,15m,1h,4h,1d` |
| `--network` | Red de Binance | `sandbox` |

### Salida

El script genera un `data/timeframes/timeframes_config.json` con:

```json
{
  "BTC/USDT": {
    "primary": {
      "timeframe": "1h",
      "history": 48,
      "reasoning": "Mejor equilibrio entre señales y ruido"
    },
    "secondary": [
      {"timeframe": "15m", "history": 100},
      {"timeframe": "4h", "history": 30}
    ],
    "analysis": {
      "recommended_strategy": "Swing Trading",
      "risk_level": "Medio"
    }
  }
}
```

### Beneficios

- **Optimizado por símbolo**: Cada activo puede tener diferente configuración
- **Análisis IA**: La IA decide basándose en volatilidad y tendencia real
- **Economico**: Solo analizas una vez, guardas configuración
- **Escalable**: Agrega nuevos símbolos fácilmente

---

## 📂 Estructura del Proyecto

```
bot_trading/
├── app/
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── trading_bot.py          # Motor de ejecución
│   │   ├── market_scanner_bot.py  # Escáner de mercado
│   │   ├── indicators.py          # Indicadores técnicos
│   │   ├── ia/
│   │   │   ├── __init__.py
│   │   │   └── predictor.py       # IA (Gemini/DeepSeek)
│   │   └── backup/
│   │       ├── trading_bot.py
│   │       └── market_scanner_bot.py
│   └── database.py                # Persistencia
├── scripts/
│   ├── run_trading_bot.py         # Punto de entrada trading
│   ├── run_market_scanner_bot.py # Punto de entrada scanner
│   ├── analyze_timeframes.py     # Análisis multi-timeframe
│   └── reset_system.py            # Limpieza del sistema
├── frontend/                      # Interfaz web (React)
├── tests/                         # Tests unitarios
├── timeframes_config.json         # Configuración de timeframes
├── .env                           # Variables de entorno
├── .env.example                   # Plantilla de variables
├── requirements.txt               # Dependencias Python
└── README.md                      # Este archivo
```

---

## ⚠️ Notas de Seguridad

1. **Empieza en Testnet:** Siempre prueba primero en `sandbox` o `testnet`.
2. **Presupuesto Máximo:** Nunca inviertas más de lo que puedas perder.
3. **Circuit Breaker:** Úsalo para evitar pérdidas catastróficas.
4. **Validación de Plan:** El bot rechaza planes con precios irracionales.
5. **No es Financiero:** Este bot es solo para fines educativos. No garantiza ganancias.

---

## ❓ FAQ

### ¿Necesito API Keys de Binance?

Sí, para conectar con el exchange. Para pruebas, usa las de **Testnet** (gratis).

### ¿Qué proveedor de IA debería usar?

- **Gemini 2.0 Flash:** Más rápido, menos costoso.
- **DeepSeek:** Mayor contexto, mejor para análisis complejos.

### ¿Puedo usar el bot con fondos reales?

**No recomendado** para uso en mainnet sin haber probado extensivamente en testnet.

### ¿Cómo reanudo una sesión anterior?

```bash
python scripts/run_trading_bot.py --symbol BTC/USDT --budget 100 \
  --run_script_id "TU_SESSION_ID"
```

### ¿El bot opera 24/7?

Sí, el bot corre en un loop infinito con polling cada 60 segundos. Incluye detección de downtime.

### ¿Qué pasa si pierdo la conexión a internet?

El bot detecta downtime y te notifica al reanudar. Puedes reanudar la sesión con `--run_script_id`.

### ¿Cómo modifico los indicadores técnicos?

Edita `app/bot/indicators.py`. Los cambios se reflejan automáticamente en los próximos análisis de IA.

---

## 🔧 Comandos Útiles

```bash
# Análisis de timeframes (multi-timeframe) - Genera data/timeframes/timeframes_config.json
python scripts/analyze_timeframes.py --symbol BTC/USDT
python scripts/analyze_timeframes.py --symbol ALL
# Nota: Después de generar data/timeframes/timeframes_config.json, el bot lo usará automáticamente

# Resetear una moneda a 0 (cierra posiciones y limpia órdenes pendientes)
python scripts/reset_coin.py --symbol FET/USDT --market_type future --network testnet

# Reset completo del sistema (limpia DB y posiciones)
python scripts/reset_system.py

# Ver ayuda
python scripts/run_trading_bot.py --help
python scripts/run_market_scanner_bot.py --help
python scripts/analyze_timeframes.py --help
python scripts/reset_coin.py --help
```

### Resetear Moneda (`reset_coin.py`)

Este script cierra posiciones abiertas y cancela órdenes pendientes para una moneda específica:

```bash
python scripts/reset_coin.py [OPCIONES]
```

| Argumento | Descripción | Valor por Defecto |
|-----------|-------------|-------------------|
| `--symbol` | **[REQUERIDO]** Símbolo a resetear (ej. `FET/USDT`) | — |
| `--market_type` | Tipo de mercado (`spot` o `future`) | `future` |
| `--network` | Red (`testnet`, `sandbox`, `demo`, `mainnet`) | `testnet` |

**Ejemplos:**

```bash
# Resetear FET en testnet futures
python scripts/reset_coin.py --symbol FET/USDT --market_type future --network testnet

# Resetear BTC en mainnet spot
python scripts/reset_coin.py --symbol BTC/USDT --market_type spot --network mainnet

# Resetear SOL en demo
python scripts/reset_coin.py --symbol SOL/USDT --network demo
```

**Qué hace:**
1. Cierra posiciones abiertas en Binance (vende lo que tengas)
2. Cancela órdenes pendientes
3. Muestra balance final para verificar

---

**Nota:** Este software es para fines educativos. El trading conlleva riesgos. Usa siempre money management adecuado.
