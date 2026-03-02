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
    def __init__(self, provider="gemini", quote="USDT", capital=100.0, mode="volume"):
        self.db = get_db_manager()
        self.predictor = get_predictor(provider)
        self.quote = quote.upper()
        self.capital = capital
        self.mode = mode.lower()
        self.exchange = ccxt.binance({'enableRateLimit': True})

    def fetch_market_snapshot(self):
        """Obtiene datos rápidos de las monedas según el modo (volumen o volatilidad)."""
        print(f"[*] Obteniendo mercados para {self.quote} (Modo: {self.mode})...")
        try:
            self.exchange.load_markets()
            markets = [m for m in self.exchange.markets.values() if m['quote'] == self.quote and m['active']]

            # Obtener tickers para filtrar
            tickers = self.exchange.fetch_tickers([m['symbol'] for m in markets[:100]])

            # Seleccionar según el modo
            if self.mode == "volatility":
                # Ordenar por valor absoluto del cambio porcentual (mayores subidas O caídas)
                top_tickers = sorted(tickers.values(),
                                     key=lambda x: abs(x['percentage']) if x['percentage'] is not None else 0,
                                     reverse=True)[:15]
            else:
                # Por defecto: Volumen de 24h
                top_tickers = sorted(tickers.values(),
                                     key=lambda x: x['quoteVolume'] if x['quoteVolume'] else 0,
                                     reverse=True)[:15]

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
            print(f"[!] Error al cargar mercados: {e}")
            return []

    def run_scan(self):
        market_snapshot = self.fetch_market_snapshot()
        if not market_snapshot:
            print("[!] No se pudieron obtener datos del mercado.")
            return

        print(f"[*] Analizando {len(market_snapshot)} activos con IA...")
        rankings = self.predictor.get_market_rank(market_snapshot, self.capital, self.quote)

        if not rankings:
            print("[!] La IA no devolvió recomendaciones.")
            return

        print("\n" + "=" * 80)
        print(f" RANKING DE RENTABILIDAD - CAPITAL: {self.capital} {self.quote}")
        print("=" * 80)

        for item in rankings:
            # Imprimir en consola
            print(f"#{item['rank']} | {item['symbol']} | Estrategia: {item['recommended_strategy']}")
            print(f"   - Rentabilidad: +{item['expected_profit_pct']}% | Riesgo: -{item['expected_loss_pct']}%")
            print(f"   - Timeframe: {item['recommended_timeframe']} | Volatilidad: {item['volatility']}")
            print(f"   - Gas Est.: {item['gas_fee_estimate']} {self.quote}")
            print(f"   - Motivo: {item['reasoning']}")
            print("-" * 80)

            # Guardar en DB
            self.db.save_market_scan(item)

        print(f"[*] Escaneo completado. Resultados guardados en la base de datos.")


