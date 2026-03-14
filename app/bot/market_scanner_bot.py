import os
import sys
import json
import ccxt
import pandas as pd
from datetime import datetime

from app.database import get_db_manager
from app.bot.ia.predictor import get_predictor
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from scripts.analyze_timeframes import analyze_single_symbol, save_config

# Cargar variables de entorno (API Keys, URLs de DB, etc.)
load_dotenv()


class MarketScanner:
    """
    Escáner de Mercado: Esta clase se encarga de monitorizar el exchange (Binance)
    para identificar los activos con mayor movimiento y someterlos a un análisis de IA.
    Su objetivo es generar un ranking de rentabilidad para que el TradingBot sepa dónde operar.
    """

    def __init__(
        self,
        provider="gemini",
        quote="USDT",
        capital=100.0,
        mode="volume",
        symbol=None,
        market_type="spot",
        num_top=15,
        run_script_id=None,
    ):
        """
        Inicializa el escáner con los parámetros de búsqueda.

        :param provider: El proveedor de IA a usar ('gemini' o 'deepseek').
        :param quote: La moneda base de los pares a buscar (ej. 'USDT').
        :param capital: El capital total estimado para distribuir entre las señales.
        :param mode: Modo de filtrado inicial: 'volume' (volumen 24h) o 'volatility' (% de cambio).
        :param symbol: Opcional, forzar el análisis de un solo símbolo específico.
        :param market_type: Tipo de mercado: 'spot', 'future' o 'both'.
        :param num_top: Cuántas monedas del ranking inicial enviar a la IA (limita el coste de tokens).
        :param run_script_id: ID de la sesión de ejecución actual.
        """
        self.db = get_db_manager()
        self.predictor = get_predictor(provider)
        self.quote = quote.upper()
        self.capital = capital
        self.mode = mode.lower()
        self.symbol = symbol.upper() if symbol else None
        self.run_script_id = run_script_id

        # Determinar los tipos de mercado a escanear
        self.market_types = (
            ["spot", "future"]
            if market_type.lower() == "both"
            else [market_type.lower()]
        )

        # Cliente CCXT para comunicación con Binance (solo lectura de datos públicos)
        self.exchange = ccxt.binance({"enableRateLimit": True})
        self.num_top = num_top

        # Cargar configuración de timeframes
        self.timeframes_config = self._load_timeframes_config()

        # Crear directorio de salida si no existe
        self.output_dir = self._setup_output_directory()

    def _load_timeframes_config(self):
        """Carga la configuración de timeframes desde el archivo JSON."""
        config_path = os.path.join("data", "timeframes", "timeframes_config.json")
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

        if not os.path.exists(config_path):
            config_path = os.path.join(
                base_dir, "data", "timeframes", "timeframes_config.json"
            )

        if not os.path.exists(config_path):
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w") as f:
                json.dump({}, f)
            print(f"[*] Archivo de configuración creado: {config_path}")
            return {}

        try:
            with open(config_path, "r") as f:
                content = f.read().strip()
                if content:
                    config = json.loads(content)
                    print(
                        f"[*] Configuración de timeframes cargada desde {config_path}"
                    )
                    return config
                else:
                    print(f"[*] Archivo de configuración vacío, iniciando vacío")
                    return {}
        except json.JSONDecodeError as e:
            print(f"[!] Archivo JSON corrupto, creando nuevo: {e}")
            with open(config_path, "w") as f:
                json.dump({}, f)
            return {}
        except Exception as e:
            print(f"[!] Error cargando configuración de timeframes: {e}")
            return {}

    def _setup_output_directory(self):
        """Crea el directorio de salida para los resultados del scanner."""
        if not self.run_script_id:
            self.run_script_id = f"SCAN_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        output_dir = os.path.join("data", "scanner", self.run_script_id)
        os.makedirs(output_dir, exist_ok=True)
        print(f"[*] Directorio de salida creado: {output_dir}")

        self.db.save_run_script(
            {
                "id": self.run_script_id,
                "start_time": datetime.utcnow(),
                "name_script": f"Market Scanner ({self.quote})",
                "initial_capital": self.capital,
                "params": {
                    "quote": self.quote,
                    "capital": self.capital,
                    "mode": self.mode,
                    "num_top": self.num_top,
                    "provider": self.predictor.__class__.__name__,
                    "market_types": self.market_types,
                },
            }
        )

        return output_dir

    def _get_symbol_timeframe_config(self, symbol):
        """Obtiene la configuración de timeframe para un símbolo específico."""
        config = self.timeframes_config or {}

        if symbol not in config:
            print(
                f"[*] Símbolo {symbol} no encontrado en configuración, generando análisis..."
            )
            self._analyze_symbol_timeframe(symbol)
            config = self.timeframes_config or {}

        symbol_config = config.get(symbol)
        if not symbol_config:
            return None, 12

        primary = symbol_config.get("primary", {})
        timeframe = primary.get("timeframe")
        history = primary.get("history", 12)

        return timeframe, history

    def _analyze_symbol_timeframe(self, symbol):
        """Ejecuta el análisis de timeframe para un símbolo y lo agrega al config."""
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            output_path = os.path.join(
                base_dir, "data", "timeframes", "timeframes_config.json"
            )

            provider_name = self.predictor.__class__.__name__.lower().replace(
                "predictor", ""
            )

            exchange = ccxt.binance({"enableRateLimit": True})

            print(f"[*] Analizando timeframe para {symbol}...")
            result = analyze_single_symbol(
                symbol, provider_name, exchange, self.timeframes_config
            )

            if result:
                self.timeframes_config = result
                save_config(result, output_path)
                print(f"[✓] Análisis de timeframe completado para {symbol}")
                return True
            else:
                print(f"[!] No se pudo completar el análisis para {symbol}")
                return False

        except Exception as e:
            print(f"[!] Error en _analyze_symbol_timeframe: {e}")
            return False

    def _save_scan_results(self, market_type, market_snapshot, rankings):
        """Guarda los resultados del escaneo en archivos JSON."""
        if not self.output_dir:
            return

        # Crear nombre de archivo basado en market_type
        filename = (
            f"scan_{market_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        )
        filepath = os.path.join(self.output_dir, filename)

        # Preparar datos para guardar
        results = {
            "scan_id": self.run_script_id,
            "timestamp": datetime.utcnow().isoformat(),
            "market_type": market_type,
            "parameters": {
                "quote": self.quote,
                "capital": self.capital,
                "mode": self.mode,
                "num_top": self.num_top,
                "provider": self.predictor.__class__.__name__,
            },
            "market_snapshot": market_snapshot,
            "rankings": rankings,
        }

        try:
            with open(filepath, "w") as f:
                json.dump(results, f, indent=2, default=str)
            print(f"[*] Resultados guardados en: {filepath}")

        except Exception as e:
            print(f"[!] Error guardando resultados: {e}")

    def fetch_market_snapshot(self, market_type):
        """
        Obtiene una 'foto' instantánea de los activos más relevantes del mercado.
        Filtra por volumen o volatilidad y descarga velas recientes para contexto de la IA.
        """
        print(
            f"[*] Obteniendo mercados para {self.quote} (Tipo: {market_type}, Modo: {self.mode})..."
        )
        try:
            # Limpiar caché del cliente CCXT para evitar mezclar mercados de Spot y Futuros
            self.exchange.markets = {}
            self.exchange.symbols = []
            self.exchange.options = self.exchange.options or {}
            self.exchange.options["defaultType"] = market_type
            self.exchange.load_markets(True)

            # Traducir market_type a los tipos internos de la librería CCXT
            target_types = ["spot"] if market_type == "spot" else ["swap", "future"]

            if self.symbol:
                # Caso en que el usuario quiere analizar una moneda específica
                if self.symbol not in self.exchange.markets:
                    print(f"[!] El símbolo {self.symbol} no existe en {market_type}.")
                    return []
                top_tickers = [self.exchange.fetch_ticker(self.symbol)]
            else:
                # 1. Filtrar solo mercados activos que usen el par correcto (ej. BTC/USDT)
                markets = [
                    m
                    for m in self.exchange.markets.values()
                    if m["quote"] == self.quote
                    and m["active"]
                    and m.get("type") in target_types
                ]

                # 2. Obtener tickers (precios y volúmenes) de los primeros 100 candidatos
                symbols_to_fetch = [m["symbol"] for m in markets[:100]]
                try:
                    tickers_data = self.exchange.fetch_tickers(symbols_to_fetch)
                    tickers = list(tickers_data.values())
                except Exception as e:
                    # Si falla la descarga en lote, intentamos descargar de uno en uno (más lento pero seguro)
                    tickers = []
                    for s in symbols_to_fetch[:50]:
                        try:
                            tickers.append(self.exchange.fetch_ticker(s))
                        except Exception:
                            continue

                # 3. Ordenar la lista según el modo elegido por el usuario
                if self.mode == "volatility":
                    # Ordenar por el valor absoluto del cambio porcentual (volatilidad)
                    top_tickers = sorted(
                        tickers,
                        key=lambda x: (
                            abs(float(x["percentage"]))
                            if x["percentage"] is not None
                            else 0
                        ),
                        reverse=True,
                    )[: self.num_top]
                else:
                    # Ordenar por volumen de transacciones en la moneda base (USDT)
                    top_tickers = sorted(
                        tickers,
                        key=lambda x: x["quoteVolume"] if x["quoteVolume"] else 0,
                        reverse=True,
                    )[: self.num_top]

            # 4. Enriquecer cada activo con datos históricos usando timeframe óptimo
            all_data = []
            for ticker in top_tickers:
                symbol = ticker["symbol"]
                try:
                    # Obtener timeframe óptimo desde configuración
                    timeframe, history = self._get_symbol_timeframe_config(symbol)
                    if not timeframe:
                        timeframe = "1h"  # Default si no hay configuración

                    # Usar history mínimo entre configurado y 12 para ahorrar tokens
                    limit = min(history, 12) if history else 12

                    # Obtenemos velas con timeframe óptimo
                    ohlcv = self.exchange.fetch_ohlcv(
                        str(symbol), timeframe=timeframe, limit=limit
                    )
                    df = pd.DataFrame(ohlcv, columns=["t", "o", "h", "l", "c", "v"])
                    last_price = df["c"].iloc[-1]
                    change_pct = ticker["percentage"]

                    all_data.append(
                        {
                            "symbol": symbol,
                            "market_type": market_type,
                            "timeframe_used": timeframe,
                            "candles_limit": limit,
                            "price": float(last_price),
                            "change_24h_pct": float(change_pct) if change_pct else 0.0,
                            "volume_24h": float(ticker["quoteVolume"])
                            if ticker["quoteVolume"]
                            else 0.0,
                            # Enviamos solo Precio de Cierre y Volumen para ahorrar tokens
                            "recent_candles": df[["c", "v"]]
                            .tail(5)
                            .to_dict(orient="records"),
                        }
                    )
                    print(
                        f"    [+] {symbol} | TF: {timeframe} | Cambio: {change_pct:.2f}% | Vol: {ticker['quoteVolume']:.0f}"
                    )
                except Exception as e:
                    print(f"    [!] Error procesando {symbol}: {e}")
                    continue
            return all_data
        except Exception as e:
            print(f"[!] Error al cargar mercados ({market_type}): {e}")
            return []

    def run_scan(self):
        """
        Ejecuta el proceso principal de escaneo:
        Recopila datos -> Consulta a la IA -> Muestra Ranking -> Guarda en Base de Datos y archivos.
        """
        print(f"[*] Iniciando Escaneo Global - ID: {self.run_script_id}")

        # Track processed market types for completeness validation
        processed_markets = []

        for m_type in self.market_types:
            market_snapshot = self.fetch_market_snapshot(m_type)
            if not market_snapshot:
                print(f"[!] No se pudieron obtener datos para el mercado {m_type}.")
                continue

            # Limitar activos enviados a la IA para evitar errores de parseo (máx 15)
            max_assets_for_ai = min(self.num_top, 15)
            assets_for_ai = market_snapshot[:max_assets_for_ai]
            print(f"[*] Analizando {len(assets_for_ai)} activos con IA ({m_type})...")
            rankings = self.predictor.get_market_rank(
                assets_for_ai, self.capital, self.quote, m_type
            )

            if not rankings:
                print(f"[!] La IA no devolvió recomendaciones para {m_type}.")
                continue

            # Guardar resultados en archivos JSON
            self._save_scan_results(m_type, market_snapshot, rankings)
            processed_markets.append(m_type)

            # Visualización de resultados en consola
            print("\n" + "=" * 80)
            print(
                f" RANKING DE RENTABILIDAD ({m_type.upper()}) - ID: {self.run_script_id} - CAPITAL: {self.capital} {self.quote}"
            )
            print("=" * 80)

            for item in rankings:
                # Sincronizar la recomendación de la IA con los datos técnicos actuales
                original_data = next(
                    (d for d in market_snapshot if d["symbol"] == item["symbol"]), {}
                )

                item["price"] = original_data.get("price")
                item["change_24h_pct"] = original_data.get("change_24h_pct")
                item["volume_24h"] = original_data.get("volume_24h")
                item["market_type"] = m_type
                item["scan_id"] = self.run_script_id

                # Imprimir ficha técnica de la recomendación
                print(
                    f"#{item['rank']} | {item['symbol']} | Precio: {item['price']} | Cambio: {item['change_24h_pct']}%"
                )
                print(f"   - Estrategia: {item['recommended_strategy']}")
                print(
                    f"   - Rentabilidad: +{item['expected_profit_pct']}% | Riesgo: -{item['expected_loss_pct']}%"
                )
                print(
                    f"   - Timeframe: {item['recommended_timeframe']} | Volatilidad: {item['volatility']}"
                )
                print(f"   - Motivo: {item['reasoning']}")
                print("-" * 80)

                # Persistencia: Guardar el escaneo para que el TradingBot lo procese
                self.db.save_market_scan(item, run_script_id=self.run_script_id)

        # Validación de completitud
        self._validate_completeness(processed_markets)

        print(
            f"[*] Escaneo {self.run_script_id} completado. Resultados guardados en base de datos y archivos."
        )

    def _validate_completeness(self, processed_markets):
        """Valida que el escaneo sea completo según los criterios definidos."""
        print(f"\n[*] Validando completitud del escaneo...")

        # Criterio 1: Se han analizado todos los market_types configurados
        missing = [mt for mt in self.market_types if mt not in processed_markets]
        if missing:
            print(f"[!] Criterio 1 incumplido: Faltan market types: {missing}")
        else:
            print(f"[OK] Criterio 1 cumplido: Todos los market types analizados")

        # Criterio 2: Cada market_type tiene al menos un ranking generado
        # (ya verificado en el loop principal, solo listar)
        for mt in processed_markets:
            print(
                f"[OK] Criterio 2 cumplido: Market type '{mt}' tiene rankings generados"
            )

        # Criterio 3: Los resultados han sido guardados correctamente en formato JSON
        json_files = []
        if self.output_dir:
            json_files = [f for f in os.listdir(self.output_dir) if f.endswith(".json")]
            if len(json_files) >= len(processed_markets):
                print(
                    f"[OK] Criterio 3 cumplido: {len(json_files)} archivos JSON guardados en {self.output_dir}"
                )
            else:
                print(
                    f"[!] Criterio 3 incumplido: Solo {len(json_files)} archivos JSON de {len(processed_markets)} esperados"
                )
        else:
            print(f"[!] Criterio 3 incumplido: No hay directorio de salida")

        # Resumen final
        if not missing and self.output_dir and json_files:
            print(f"[OK] ESCANEO COMPLETO: Todos los criterios cumplidos")
        else:
            print(f"[!] ESCANEO INCOMPLETO: Algunos criterios no cumplidos")
