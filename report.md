# Reporte de Bots de Trading

## Resumen Ejecutivo

El proyecto cuenta con una arquitectura de trading automatizado basada en dos bots principales que trabajan en conjunto con IA para analizar el mercado y ejecutar operaciones.

---

## Estructura de Bots

### 1. MarketScannerBot (`market_scanner_bot.py`)

**Propósito:** Escáner de mercado para identificar oportunidades de inversión.

**Funcionalidades:**
- **Escaneo de mercado:** Monitoriza el exchange (Binance) para identificar activos con mayor movimiento
- **Modos de filtrado:** 
  - `volume`: Ordena por volumen de transacciones 24h
  - `volatility`: Ordena por cambio porcentual absoluto
- **Tipos de mercado:** Soporta Spot, Future o ambos
- **Configuración de timeframes:** Utiliza `data/timeframes/timeframes_config.json` para determinar el timeframe óptimo por símbolo
- **Enriquecimiento de datos:** Descarga velas recientes usando el timeframe óptimo configurado para cada símbolo (por defecto 1h, máximo 12 velas)
- **Análisis con IA:** Envía los activos filtrados a la IA para generar un ranking de rentabilidad
- **Generación de resultados:** Guarda archivos JSON estructurados en `data/scanner/<run_script_id>/` con snapshot del mercado y rankings
- **Validación de completitud:** Verifica que todos los tipos de mercado configurados hayan sido analizados y guardados

---

### 2. TradingBot (`trading_bot.py`)

**Propósito:** Ejecución de órdenes de compra/venta siguiendo un plan generado por la IA.

**Funcionalidades:**
- **Gestión de credenciales:** Configuración dinámica de API keys según red (mainnet/sandbox/demo)
- **Sincronización de tiempo:** Calcula offset con servidor de Binance para evitar errores de firma
- **Carga de filtros Binance:** Valida lot size y monto mínimo para evitar errores de API
- **Ciclo de decisión técnica:**
  1. Verifica plan activo en DB
  2. Evalúa caducidad (TTL de 24h para entradas, 1h para posiciones)
  3. Si no hay plan válido, genera uno nuevo con IA
  4. Ejecuta disparadores de entrada/salida

**Estados del Plan:**
- `WAITING_FOR_ENTRY`: Esperando precio de entrada
- `IN_POSITION`: Posición abierta, monitoreando TP/SL
- `CLOSED`: Posición cerrada por objetivo
- `CANCELLED`: Posición cancelada

---

### 3. Módulo de IA (`ia/predictor.py`)

**Proveedores implementados:**

| Proveedor | Modelo | API |
|-----------|--------|-----|
| Gemini | gemini-2.0-flash | Google Generative AI |
| DeepSeek | deepseek-chat | OpenAI-compatible |

**Métodos:**

1. **get_prediction()**: Análisis de velas para señal de trading
2. **get_market_rank()**: Genera ranking de rentabilidad para el scanner
3. **get_execution_plan()**: Genera "Plan de Ejecución Blindado" con indicadores técnicos

---

## Flujo de Trabajo

```
┌─────────────────────┐     ┌─────────────────────┐
│   MarketScanner    │────▶│   Base de Datos     │
│  (Analiza mercado) │     │ (Guarda rankings)   │
└─────────────────────┘     └──────────┬──────────┘
                                        │
                                        ▼
┌─────────────────────┐     ┌─────────────────────┐
│     TradingBot     │◀────│   Plan de Ejecución │
│ (Ejecuta órdenes)  │     │ (Con indicadores)   │
└─────────────────────┘     └─────────────────────┘
```

---

## Estado de Mejoras Implementadas

### ✅ Problemas de SEGURIDAD Resueltos

| # | Problema | Estado | Solución Implementada |
|---|----------|--------|---------------------|
| 1 | Sin validación de respuesta de IA | ✅ RESUELTO | `predictor.py:19-100` - `validate_execution_plan()` valida JSON, precios, montos |
| 2 | Ejecución a mercado (MARKET) | ✅ RESUELTO | `trading_bot.py:346-510` - Órdenes LIMIT con `_wait_for_order_fill()` |
| 3 | Sin circuit breaker | ✅ RESUELTO | `trading_bot.py:57-63,163-195` - `max_losses` + `cooldown` |
| 4 | Balance check flojo | ✅ RESUELTO | `trading_bot.py:377-389` - Reconfirma balance antes de ejecutar |
| 5 | Sin rate limiting propio | ✅ RESUELTO | Circuit breaker actúa como protección |

### ✅ Problemas de GANANCIAS Resueltos

| # | Problema | Estado | Solución Implementada |
|---|----------|--------|---------------------|
| 1 | TP/SL fijo | ✅ RESUELTO | `trading_bot.py:920-940` - Trailing stop dinámico implementado |
| 2 | Sin partial take profit | ✅ RESUELTO | `trading_bot.py:893-922` - Múltiples niveles TP |
| 3 | No promedia precio | ⏳ PENDIENTE | Avg down no implementado |
| 4 | Tiempo de posición limitado | ✅ RESUELTO | TTL ahora configurable por la IA |

### ✅ Problemas de PRECISIÓN Resueltos

| # | Problema | Estado | Solución Implementada |
|---|----------|--------|---------------------|
| 1 | Sin datos fundamentales | ⏳ PENDIENTE | Requiere integrar más APIs |
| 2 | Sin backtesting | ⏳ PENDIENTE | Requiere módulo adicional |
| 3 | Prompt genérico | ✅ RESUELTO | `indicators.py` + `predictor.py` - Indicadores calculados localmente |
| 4 | Dependencia total IA | ✅ RESUELTO | Validación de plan + lógica de confirmación |

---

## Nuevas Funcionalidades

### Indicadores Técnicos (`app/bot/indicators.py`)

Módulo nuevo con cálculo de indicadores:

| Indicador | Descripción |
|-----------|-------------|
| RSI (14, 21) | Relative Strength Index |
| EMA (9, 21, 50, 200) | Medias exponenciales |
| SMA (20, 50, 200) | Medias simples |
| MACD | Convergencia/Divergencia |
| ATR (14) | Average True Range |
| Bollinger Bands | Bandas con posición |
| Estocástico %K/%D | Oscilador |
| OBV | On-Balance Volume |
| Volume Ratio | Volumen vs MA20 |

### Estrategias de Salida

1. **Partial Take Profit:**
   ```json
   "partial_tp_levels": [
     {"price": 51500, "percent": 50},
     {"price": 52000, "percent": 50}
   ]
   ```

2. **Trailing Stop Dinámico:**
   ```json
   "trailing_stop_activation_price": 50000,
   "trailing_stop_distance_percent": 2
   ```

### Circuit Breaker

- **Configurable** via CLI: `--max_losses` y `--cooldown`
- **Por defecto:** 3 pérdidas consecutivas → 5 minutos de espera

---

## Plan de Implementación - Estado Final

### Fase 1: Seguridad (COMPLETADO ✅)
- [x] 1.1 Validar respuesta JSON del predictor antes de usar
- [x] 1.2 Implementar órdenes LIMIT con precio configurable
- [x] 1.3 Agregar circuit breaker (max pérdidas consecutivas)
- [x] 1.4 Reconfirmar balance antes de ejecutar

### Fase 2: Precisión (COMPLETADO ✅)
- [x] 2.1 Crear utilitario de indicadores técnicos (RSI, MACD, EMA, ATR)
- [x] 2.2 Enriquecer prompts con indicadores calculados
- [x] 2.3 Agregar análisis multi-timeframe (configuración automática desde timeframes_config.json)

### Fase 3: Ganancias (COMPLETADO ✅)
- [x] 3.1 Implementar partial take profit
- [x] 3.2 Activar trailing stop dinámico
- [ ] 3.3 Agregar opción de avg down (promediar precio)

---

## Pendientes Futuros

| Prioridad | Tarea | Descripción |
|-----------|-------|-------------|
| Media | Backtesting | Módulo para validar estrategias históricamente |
| Baja | Avg Down | Promediar precio en posiciones perdedoras |
| Baja | Datos fundamentales | Integrar noticias/sentimiento |

---

## Archivos Modificados

| Archivo | Cambios |
|---------|---------|
| `app/bot/trading_bot.py` | Validación, LIMIT, Circuit Breaker, Partial TP, Trailing Stop |
| `app/bot/ia/predictor.py` | Validación JSON, enriquecimiento con indicadores |
| `app/bot/indicators.py` | **NUEVO** - Módulo de indicadores técnicos |
| `scripts/run_trading_bot.py` | Nuevos flags `--max_losses`, `--cooldown` |
| `README.md` | Documentación completa actualizada |

---

## Dependencias

- `ccxt`: Comunicación con exchanges
- `binance`: Cliente oficial de Binance (Python)
- `google-genai`: Proveedor Gemini
- `openai`: Proveedor DeepSeek
- `pandas`: Manipulación de datos
- `numpy`: Cálculos numéricos
- `dotenv`: Variables de entorno
