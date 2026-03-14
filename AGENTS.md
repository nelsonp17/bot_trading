# Reglas del Agente - Proyecto Bot Trading

## ⚠️ IMPORTANTE - LEER ANTES DE HACER MODIFICACIONES

Este documento contiene las reglas y progresos del proyecto de trading automatizado. **NO ELIMINAR NI MODIFICAR** sin consultar primero con el usuario.

---

## Progreso Actual del Proyecto

### ✅ Funcionalidades Implementadas

1. **MarketScannerBot** (`app/bot/market_scanner_bot.py`)
   - Escaneo de mercados spot y future
   - Usa configuración de timeframes desde `data/timeframes/timeframes_config.json`
   - Limita a 15 activos enviados a IA (para evitar errores de parseo JSON)
   - Guarda resultados en `data/scanner/<run_script_id>/`
   - Validación de completitud del escaneo
   - NO genera README.md en los resultados

2. **TradingBot** (`app/bot/trading_bot.py`)
   - Ejecución de compras/ventas en spot y future
   - Continuación automática de planes existentes al reiniciar
   - Si hay delay de red, NO regenera plan si el anterior sigue vigente
   - Límite de 2% de desviación del precio objetivo para cancelar y regenerar plan
   - Tiempo máximo de posición: 1 hora
   - Muestra balance de la moneda operativa (ej: FET) además de USDT
   - Muestra posición actual con cantidad, valor y P/L en tiempo real
   - Persistencia de trades en SQLite con commit()

3. **Base de Datos** (`app/database.py`)
   - Import global de `json` agregado
   - `save_trade` ahora incluye `conn.commit()` para persistencia

---

## 📋 REGLAS OBLIGATORIAS

### 1. MarketScannerBot

```python
# En market_scanner_bot.py:
# - NO generar README.md en los directorios de salida
# - Limitar activos enviados a IA a máximo 15
max_assets_for_ai = min(self.num_top, 15)
```

### 2. TradingBot - Continuidad de Planes

```python
# En trading_bot.py - create_if_not_exist_run_script():
# - Al iniciar SIN run_script_id, primero buscar plan activo existente
# - Si existe, usar el mismo run_script_id para continuar
existing_plan = self.db.get_active_plan(self.symbol)
if existing_plan and existing_plan.get("run_script_id"):
    self.run_script_id = existing_plan["run_script_id"]
```

### 3. TradingBot - Cancelación de Plan por Desviación

```python
# En trading_bot.py - Gestión de WAITING_FOR_ENTRY:
# - Si precio se mueve >2% del objetivo, cancelar y regenerar
if abs(distancia) > 2.0:
    self.db.update_plan_status(op_id, "CANCELLED", ...)
    active_plan = None
```

### 4. TradingBot - Mostrar Balance de Moneda

```python
# En trading_bot.py - print_balance():
# - Mostrar posición abierta en futuros
positions = self.binance_client.futures_position_information(symbol=self.binance_symbol)
```

### 5. Base de Datos

```python
# En database.py - save_trade():
# - SIEMPRE incluir conn.commit() después de INSERT
conn.commit()
```

### 6. TradingBot - Gestión de Capital

```python
# En trading_bot.py - Gestión de capital al generar nuevo plan:
# - SIEMPRE calcular capital invertido del plan activo existente
# - Capital disponible = capital_inicial - inversión_actual
# - NO usar siempre self.total_budget sin importar lo ya invertido

# Obtener capital ya invertido
invested_capital = 0
if active_plan and active_plan.get("status") == "IN_POSITION":
    entry_price = active_plan.get("entry_price", 0)
    entry_config = active_plan.get("execution_plan", {}).get("entry_config", {})
    allocated_capital = entry_config.get("allocated_capital_usdt", 0)
    if entry_price > 0 and allocated_capital > 0:
        invested_capital = allocated_capital

# Calcular disponible
available_budget = self.total_budget - invested_capital

# Pasar a la IA
{
    "total_budget_assigned": self.total_budget,
    "available_budget": available_budget,
    "invested_capital": invested_capital,
    "real_account_usdt_available": usdt_free,
}
```

**Reglas de Capital:**
1. El capital inicial (--budget) se establece al iniciar el plan y es FIJO
2. Si el plan invierte 400 USDT de los 500, el capital disponible es 100 USDT
3. Al reanudar el bot (aunque el flag siga siendo 500), debe usar el capital disponible (100 USDT)
4. El capital disponible = initial_capital - inversión_actual (del plan)
5. La IA decide cómo usar ese capital (todo de golpe o fracciones)

### 7. MarketScannerBot - Análisis Dinámico de Timeframes

```python
# En market_scanner_bot.py:
# - Al analizar un símbolo que NO está en timeframes_config.json
# - Ejecutar analyze_timeframes.py automáticamente para generarlo
# - Agregar al JSON existente (no sobreescribir)

# Método _analyze_symbol_timeframe():
# - Busca scripts/analyze_timeframes.py
# - Ejecuta: python analyze_timeframes.py --symbol X --provider deepseek
# - Recarga la configuración actualizada
```

---

## ❌ PROHIBICIONES

1. **NO generar README.md** en los resultados del scanner
2. **NO regenerar plan** si ya existe uno activo (WAITING_FOR_ENTRY o IN_POSITION)
3. **NO eliminar** el `conn.commit()` en `save_trade`
4. **NO eliminar** el import de `json` en database.py
5. **NO cambiar** la lógica de continuidad de planes sin consultar
6. **NO usar siempre self.total_budget** sin calcular el capital ya invertido del plan activo

### 📝 Reglas para Documentación

1. **README.md - SOLO AGREGAR, NUNCA MODIFICAR**
   - Al documentar algo NUEVO, usar EXCLUSIVAMENTE la herramienta de edición para agregar contenido al final del archivo o en la sección correspondiente
   - **PROHIBIDO sobreescribir, eliminar o modificar** contenido existente en README.md
   - Si el usuario pide documentar algo, se AGREGA sin tocar lo que ya está
   - Usar la sección "Comandos Útiles" para scripts nuevos

2. **AGENTS.md - Actualizar siempre**
   - Cuando se implementen nuevas funcionalidades, actualizar este archivo
   - Incluir código de ejemplo de las nuevas reglas
   - Mantener la fecha de última actualización

---

## 🐛 Errores Comunes a Evitar

1. **Error "name 'json' is not defined"**: Asegurar que `import json` esté al inicio del archivo database.py
2. **Trades no se guardan**: Verificar que `save_trade` tiene `conn.commit()`
3. **Plan se regenera innecesariamente**: Verificar que `create_if_not_exist_run_script` busca planes existentes

---

## 📁 Archivos Clave

| Archivo | Propósito |
|---------|-----------|
| `app/bot/market_scanner_bot.py` | Escaneo de mercados |
| `app/bot/trading_bot.py` | Ejecución de trades |
| `app/database.py` | Persistencia SQLite/MongoDB |
| `app/bot/ia/predictor.py` | Integración con IA (Gemini/DeepSeek) |
| `data/timeframes/timeframes_config.json` | Configuración de timeframes por símbolo |
| `data/scanner/` | Resultados del escaneo |
| `scripts/reset_coin.py` | Resetear moneda a 0 (cierra posiciones) |

---

## ▶️ Comandos de Ejemplo

```bash
# Ejecutar scanner
python scripts/run_market_scanner_bot.py --capital 500 --quote USDT --provider deepseek --mode volume --type both --num_top 50

# Ejecutar trading bot (continuará plan existente automáticamente)
python scripts/run_trading_bot.py --symbol FET/USDT --budget 500 --market_type future --provider deepseek --scan_id SCAN_XXX --network testnet

# Resetear moneda a 0 (cierra posiciones y cancela órdenes pendientes)
python scripts/reset_coin.py --symbol FET/USDT --market_type future --network testnet
```

---

*Última actualización: 2026-03-13*

---

## 📋 NUEVA INTEGRACIÓN IMPLEMENTADA

### MarketScannerBot - Análisis Dinámico de Timeframes

El MarketScannerBot ahora analiza automáticamente timeframes para símbolos no configurados:

1. Al procesar un símbolo que NO existe en `data/timeframes/timeframes_config.json`
2. Ejecuta automáticamente `scripts/analyze_timeframes.py` para ese símbolo
3. Usa el mismo provider configurado (deepseek/gemini)
4. Agrega el resultado al JSON existente (no sobreescribe)
5. Recarga la configuración y usa los timeframes óptimos

Esto permite que el scanner sea completamente dinámico - puede analizar cualquier símbolo que aparezca en el top de volumen/volatility sin configuración previa.
