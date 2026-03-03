# Trading Bot con IA - Resumen del Proyecto

Este proyecto es un ecosistema de trading automatizado que combina análisis técnico tradicional con modelos de lenguaje de última generación (Gemini y DeepSeek) para operar en el mercado de criptomonedas (Binance) de forma inteligente.

## 🚀 Flujo de Operación
1. **Escaneo de Mercado (`MarketScanner`)**: Filtra los activos con mayor volumen o volatilidad en Binance y solicita a la IA un ranking de rentabilidad.
2. **Generación de Señales**: La IA analiza velas de 1h y devuelve una recomendación técnica detallada.
3. **Plan Blindado (`TradingBot`)**: Antes de operar, el bot solicita a la IA un plan de ejecución que define el precio de entrada (trigger), niveles de Take Profit/Stop Loss y un "cojín de seguridad" (rangos de precio para abortar en caso de anomalías).
4. **Ejecución y Monitoreo**: El bot ejecuta las órdenes vía API de Binance (Testnet/Mainnet) y persiste cada movimiento en la base de datos.

## 🏗️ Arquitectura y Componentes
- **`app/bot/market_scanner_bot.py`**: El "radar" del sistema. Identifica oportunidades globales. Soporta `run_script_id` para trazabilidad de escaneos.
- **`app/bot/trading_bot.py`**: El ejecutor. Gestiona el ciclo de vida de la posición, órdenes de mercado y seguridad. Implementa sesiones de ejecución (`run_script_id`) para reportes financieros independientes (ganancias, inversión, capital actual).
- **`app/bot/ia/predictor.py`**: Interfaz con los LLMs (Gemini/DeepSeek). Traduce datos técnicos a lenguaje natural y planes JSON.
- **`app/database.py`**: Capa de persistencia (SQLite para local, MongoDB para producción). Almacena sesiones (`run_scripts`), trades, escaneos y planes de ejecución vinculados por ID de sesión.
- **`app/api.py`**: Servidor FastAPI para exponer el estado del bot, trades y predicciones al frontend.
- **`frontend/`**: Interfaz de usuario en React + Vite para visualizar el ranking y el historial de operaciones en tiempo real.

## 🛠️ Stack Tecnológico
- **Backend**: Python 3.x, FastAPI.
- **Frontend**: React (JS), Tailwind CSS, Vite.
- **Trading**: `ccxt` (Datos), `python-binance` (Ejecución).
- **IA**: Google Generative AI SDK, OpenAI SDK (para DeepSeek).
- **Datos**: Pandas (Análisis), SQLite/MongoDB (Persistencia).

## ⚙️ Configuración y Ejecución
El sistema se lanza mediante scripts especializados en la carpeta `scripts/`:
- `run_market_scanner_bot.py`: Inicia el escaneo global.
- `run_trading_bot.py`: Activa el bot de ejecución para un par específico.
- `run_api_server.py`: Levanta la API para el dashboard.

## ⚠️ Seguridad y Redes
- **Sandbox (Testnet)**: Configuración por defecto para pruebas seguras sin fondos reales.
- **Colchón IA**: Protección dinámica contra volatilidad extrema basada en el razonamiento de la IA.
- **Variables de Entorno**: Las claves se gestionan vía `.env` (nunca se suben al repositorio).

## 🤖 Mandatos para Agentes de IA
- **Preservación de Logs**: NO eliminar los comandos `print`. Son fundamentales para el seguimiento del bot en tiempo real a través de la consola y logs.
- **Documentación Crítica**: NO eliminar ni reducir los comentarios de documentación (`docstrings`) ni los comentarios explicativos en español dentro del código. Son esenciales para el mantenimiento del sistema.
- **Integridad Técnica**: Cualquier modificación debe respetar los filtros de precisión de Binance y la lógica de sincronización de tiempo ya implementada.
