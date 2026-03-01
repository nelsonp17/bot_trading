import os
import time
import ccxt
import pandas as pd
import argparse
from dotenv import load_dotenv
from database import get_db_manager
from predictor import get_predictor

# Cargar variables de entorno
load_dotenv()

class TradingBot:
    def __init__(self, provider="gemini"):
        self.db = get_db_manager()
        self.predictor = get_predictor(provider)
        self.symbol = os.getenv("SYMBOL", "BTC/USDT")
        
        # Configuración de Binance Testnet
        self.exchange = ccxt.binance({
            'apiKey': os.getenv("BINANCE_API_KEY"),
            'secret': os.getenv("BINANCE_SECRET_KEY"),
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        self.exchange.set_sandbox_mode(True)
        
        print(f"[*] Bot inicializado para {self.symbol} | Entorno: {os.getenv('APP_ENV', 'development')}")

    def fetch_data(self):
        timeframe = os.getenv("TIMEFRAME", "1h")
        ohlcv = self.exchange.fetch_ohlcv(self.symbol, timeframe)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df

    def execute_logic(self):
        try:
            print(f"\n[{pd.Timestamp.now()}] --- Ciclo de análisis ---")
            df = self.fetch_data()
            result = self.predictor.get_prediction(df)
            
            signal = result.get("signal", "HOLD")
            confidence = result.get("confidence", 0)
            reason = result.get("reasoning", "No info")

            self.db.save_prediction(self.symbol, signal, confidence)
            
            print(f"[*] Resultado: {signal} | Confianza: {confidence*100:.1f}%")
            print(f"[*] Motivo: {reason}")
            
            if signal == "BUY" and confidence > 0.75:
                print(">>> ¡SEÑAL FUERTE DE COMPRA!")

        except Exception as e:
            print(f"[!] Error en el ciclo: {e}")

    def run(self):
        while True:
            self.execute_logic()
            time.sleep(60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bot de Trading con IA")
    parser.add_argument("--provider", type=str, default="gemini", choices=["gemini", "deepseek"], 
                        help="Proveedor de IA a usar (gemini o deepseek)")
    
    args = parser.parse_args()
    
    bot = TradingBot(provider=args.provider)
    bot.run()
