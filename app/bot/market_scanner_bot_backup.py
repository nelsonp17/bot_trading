import os
import sys
import ccxt
import pandas as pd
import argparse

from app.database import get_db_manager
from app.bot.ia.predictor import get_predictor
from dotenv import load_dotenv

load_dotenv()


class MarketScanner:
    def __init__(self, provider="gemini", quote="USDT", capital=100.0, mode="volume", symbol=None, market_type="spot", num_top=15):
        self.db = get_db_manager()
        self.predictor = get_predictor(provider)
        self.quote = quote.upper()
        self.capital = capital
        self.mode = mode.lower()
        self.symbol = symbol.upper() if symbol else None
        # Si es 'both', guardamos ambos, si no, una lista con uno solo
        self.market_types = ["spot", "future"] if market_type.lower() == "both" else [market_type.lower()]
        self.exchange = ccxt.binance({'enableRateLimit': True})
        self.num_top = num_top

    def fetch_market_snapshot(self, market_type):
        """Obtiene datos de las monedas para un tipo de mercado específico."""
        print(f"[*] Obteniendo mercados para {self.quote} (Tipo: {market_type}, Modo: {self.mode})...")
        try:
            # Limpiar caché de mercados para evitar fugas entre Spot y Future
            self.exchange.markets = {}
            self.exchange.symbols = []
            self.exchange.options['defaultType'] = market_type
            self.exchange.load_markets(True)
            
            # Traducir market_type al tipo interno de CCXT para filtrado estricto
            target_types = ['spot'] if market_type == 'spot' else ['swap', 'future']
            
            if self.symbol:
                if self.symbol not in self.exchange.markets:
                    print(f"[!] El símbolo {self.symbol} no existe en {market_type}.")
                    return []
                top_tickers = [self.exchange.fetch_ticker(self.symbol)]
            else:
                # Filtrar solo mercados activos, del par base correcto y del tipo correcto
                markets = [
                    m for m in self.exchange.markets.values() 
                    if m['quote'] == self.quote and m['active'] and m.get('type') in target_types
                ]
                
                # Obtener tickers
                symbols_to_fetch = [m['symbol'] for m in markets[:100]]
                try:
                    tickers_data = self.exchange.fetch_tickers(symbols_to_fetch)
                    tickers = list(tickers_data.values())
                except Exception as e:
                    # Si falla en bloque (ej. por un símbolo inexistente), intentamos uno por uno
                    tickers = []
                    for s in symbols_to_fetch[:50]: # Limitar para no saturar si falla
                        try:
                            tickers.append(self.exchange.fetch_ticker(s))
                        except Exception: continue

                # Seleccionar según el modo
                if self.mode == "volatility":
                    top_tickers = sorted(tickers,
                                         key=lambda x: abs(x['percentage']) if x['percentage'] is not None else 0,
                                         reverse=True)[:self.num_top]
                else:
                    top_tickers = sorted(tickers,
                                         key=lambda x: x['quoteVolume'] if x['quoteVolume'] else 0,
                                         reverse=True)[:self.num_top]

            all_data = []
            for ticker in top_tickers:
                symbol = ticker['symbol']
                try:
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
        for m_type in self.market_types:
            market_snapshot = self.fetch_market_snapshot(m_type)
            if not market_snapshot:
                print(f"[!] No se pudieron obtener datos para el mercado {m_type}.")
                continue

            print(f"[*] Analizando {len(market_snapshot)} activos con IA ({m_type})...")
            rankings = self.predictor.get_market_rank(market_snapshot, self.capital, self.quote, m_type)

            if not rankings:
                print(f"[!] La IA no devolvió recomendaciones para {m_type}.")
                continue

            print("\n" + "=" * 80)
            print(f" RANKING DE RENTABILIDAD ({m_type.upper()}) - CAPITAL: {self.capital} {self.quote}")
            print("=" * 80)

            for item in rankings:
                # Buscar los datos originales para este símbolo
                original_data = next((d for d in market_snapshot if d['symbol'] == item['symbol']), {})
                
                # Enriquecer el objeto con datos técnicos reales
                item['price'] = original_data.get('price')
                item['change_24h_pct'] = original_data.get('change_24h_pct')
                item['volume_24h'] = original_data.get('volume_24h')
                item['market_type'] = m_type

                # Imprimir en consola
                print(f"#{item['rank']} | {item['symbol']} | Precio: {item['price']} | Cambio: {item['change_24h_pct']}%")
                print(f"   - Estrategia: {item['recommended_strategy']}")
                print(f"   - Rentabilidad: +{item['expected_profit_pct']}% | Riesgo: -{item['expected_loss_pct']}%")
                print(f"   - Timeframe: {item['recommended_timeframe']} | Volatilidad: {item['volatility']}")
                print(f"   - Motivo: {item['reasoning']}")
                print("-" * 80)

                # Guardar en DB
                self.db.save_market_scan(item)

        print(f"[*] Escaneo completado. Resultados guardados en la base de datos.")


