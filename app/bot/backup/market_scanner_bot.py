import os
import sys
import ccxt
import pandas as pd
import argparse

from app.database import get_db_manager
from app.bot.ia.predictor import get_predictor
from dotenv import load_dotenv

# Cargar variables de entorno (API Keys, URLs de DB, etc.)
load_dotenv()


class MarketScanner:
    """
    Escáner de Mercado: Esta clase se encarga de monitorizar el exchange (Binance) 
    para identificar los activos con mayor movimiento y someterlos a un análisis de IA.
    Su objetivo es generar un ranking de rentabilidad para que el TradingBot sepa dónde operar.
    """

    def __init__(self, provider="gemini", quote="USDT", capital=100.0, mode="volume", symbol=None, market_type="spot",
                 num_top=15, run_script_id=None):
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
        self.market_types = ["spot", "future"] if market_type.lower() == "both" else [market_type.lower()]

        # Cliente CCXT para comunicación con Binance (solo lectura de datos públicos)
        self.exchange = ccxt.binance({'enableRateLimit': True})
        self.num_top = num_top

    def fetch_market_snapshot(self, market_type):
        """
        Obtiene una 'foto' instantánea de los activos más relevantes del mercado.
        Filtra por volumen o volatilidad y descarga velas recientes para contexto de la IA.
        """
        print(f"[*] Obteniendo mercados para {self.quote} (Tipo: {market_type}, Modo: {self.mode})...")
        try:
            # Limpiar caché del cliente CCXT para evitar mezclar mercados de Spot y Futuros
            self.exchange.markets = {}
            self.exchange.symbols = []
            self.exchange.options['defaultType'] = market_type
            self.exchange.load_markets(True)

            # Traducir market_type a los tipos internos de la librería CCXT
            target_types = ['spot'] if market_type == 'spot' else ['swap', 'future']

            if self.symbol:
                # Caso en que el usuario quiere analizar una moneda específica
                if self.symbol not in self.exchange.markets:
                    print(f"[!] El símbolo {self.symbol} no existe en {market_type}.")
                    return []
                top_tickers = [self.exchange.fetch_ticker(self.symbol)]
            else:
                # 1. Filtrar solo mercados activos que usen el par correcto (ej. BTC/USDT)
                markets = [
                    m for m in self.exchange.markets.values()
                    if m['quote'] == self.quote and m['active'] and m.get('type') in target_types
                ]

                # 2. Obtener tickers (precios y volúmenes) de los primeros 100 candidatos
                symbols_to_fetch = [m['symbol'] for m in markets[:100]]
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
                    top_tickers = sorted(tickers, key=lambda x: abs(x['percentage']) if x['percentage'] is not None else 0, reverse=True)[:self.num_top]
                else:
                    # Ordenar por volumen de transacciones en la moneda base (USDT)
                    top_tickers = sorted(tickers, key=lambda x: x['quoteVolume'] if x['quoteVolume'] else 0, reverse=True)[:self.num_top]

            # 4. Enriquecer cada activo con datos históricos (velas de 1 hora)
            all_data = []
            for ticker in top_tickers:
                symbol = ticker['symbol']
                try:
                    # Obtenemos las últimas 12 velas para que la IA vea la tendencia reciente
                    ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe='1h', limit=12)
                    df = pd.DataFrame(ohlcv, columns=['t', 'o', 'h', 'l', 'c', 'v'])
                    last_price = df['c'].iloc[-1]
                    change_pct = ticker['percentage']

                    all_data.append({
                        "symbol": symbol,
                        "market_type": market_type,
                        "price": last_price,
                        "change_24h_pct": round(change_pct, 2) if change_pct else 0,
                        "volume_24h": ticker['quoteVolume'],
                        # Enviamos solo Precio de Cierre y Volumen para ahorrar tokens
                        "recent_candles": df[['c', 'v']].tail(5).to_dict(orient='records')
                    })
                    print(f"    [+] {symbol} | Cambio: {change_pct:.2f}% | Vol: {ticker['quoteVolume']:.0f}")
                except Exception:
                    continue
            return all_data
        except Exception as e:
            print(f"[!] Error al cargar mercados ({market_type}): {e}")
            return []

    def run_scan(self):
        """
        Ejecuta el proceso principal de escaneo:
        Recopila datos -> Consulta a la IA -> Muestra Ranking -> Guarda en Base de Datos.
        """
        from datetime import datetime
        scan_id = f"SCAN_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        print(f"[*] Iniciando Escaneo Global - ID: {scan_id}")

        for m_type in self.market_types:
            market_snapshot = self.fetch_market_snapshot(m_type)
            if not market_snapshot:
                print(f"[!] No se pudieron obtener datos para el mercado {m_type}.")
                continue

            # Llamada al Predictor para que la IA genere el ranking de inversión
            print(f"[*] Analizando {len(market_snapshot)} activos con IA ({m_type})...")
            rankings = self.predictor.get_market_rank(market_snapshot, self.capital, self.quote, m_type)

            if not rankings:
                print(f"[!] La IA no devolvió recomendaciones para {m_type}.")
                continue

            # Visualización de resultados en consola
            print("\n" + "=" * 80)
            print(f" RANKING DE RENTABILIDAD ({m_type.upper()}) - ID: {scan_id} - CAPITAL: {self.capital} {self.quote}")
            print("=" * 80)

            for item in rankings:
                # Sincronizar la recomendación de la IA con los datos técnicos actuales
                original_data = next((d for d in market_snapshot if d['symbol'] == item['symbol']), {})

                item['price'] = original_data.get('price')
                item['change_24h_pct'] = original_data.get('change_24h_pct')
                item['volume_24h'] = original_data.get('volume_24h')
                item['market_type'] = m_type
                item['scan_id'] = scan_id

                # Imprimir ficha técnica de la recomendación
                print(
                    f"#{item['rank']} | {item['symbol']} | Precio: {item['price']} | Cambio: {item['change_24h_pct']}%")
                print(f"   - Estrategia: {item['recommended_strategy']}")
                print(f"   - Rentabilidad: +{item['expected_profit_pct']}% | Riesgo: -{item['expected_loss_pct']}%")
                print(f"   - Timeframe: {item['recommended_timeframe']} | Volatilidad: {item['volatility']}")
                print(f"   - Motivo: {item['reasoning']}")
                print("-" * 80)

                # Persistencia: Guardar el escaneo para que el TradingBot lo procese
                self.db.save_market_scan(item, run_script_id=self.run_script_id)

        print(f"[*] Escaneo {scan_id} completado. Resultados guardados en la base de datos.")
