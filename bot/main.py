import os
import time
import ccxt
import pandas as pd
from dotenv import load_dotenv
from database import get_db_manager

# Cargar variables de entorno
load_dotenv()

class TradingBot:
    def __init__(self):
        self.db = get_db_manager()
        self.symbol = os.getenv("SYMBOL", "BTC/USDT")
        
        # Configuración de Binance Testnet
        self.exchange = ccxt.binance({
            'apiKey': os.getenv("BINANCE_API_KEY"),
            'secret': os.getenv("BINANCE_SECRET_KEY"),
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        
        # ACTIVAR MODO SANDBOX PARA TESTNET
        self.exchange.set_sandbox_mode(True)
        
        print(f"[*] Bot inicializado en Binance Testnet para {self.symbol}")

    def fetch_data(self):
        """Obtiene datos históricos para el modelo."""
        timeframe = os.getenv("TIMEFRAME", "1h")
        ohlcv = self.exchange.fetch_ohlcv(self.symbol, timeframe)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df

    def execute_logic(self):
        """Ciclo principal de decisión."""
        try:
            print(f"[{pd.Timestamp.now()}] Analizando mercado...")
            df = self.fetch_data()
            
            # TODO: Aquí integrarías tu modelo de scikit-learn
            # Por ahora simulamos una señal alcista
            last_price = df['close'].iloc[-1]
            
            # Guardar predicción en MongoDB
            self.db.save_prediction(self.symbol, "BUY", 0.85)
            
            print(f"[*] Último precio: {last_price} | Predicción guardada en Mongo.")
            
        except Exception as e:
            print(f"[!] Error en el ciclo: {e}")

    def run(self):
        while True:
            self.execute_logic()
            time.sleep(60) # Esperar 1 minuto

if __name__ == "__main__":
    bot = TradingBot()
    bot.run()
