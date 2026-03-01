import os
import time
import ccxt
import pandas as pd
from dotenv import load_dotenv
from database import get_db_manager
from predictor import GeminiPredictor

# Cargar variables de entorno
load_dotenv()

class TradingBot:
    def __init__(self):
        self.db = get_db_manager()
        self.predictor = GeminiPredictor()
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
        """Ciclo principal de decisión usando IA."""
        try:
            print(f"\n[{pd.Timestamp.now()}] --- Iniciando ciclo de análisis ---")
            df = self.fetch_data()
            
            # Obtener predicción de Gemini
            result = self.predictor.get_prediction(df)
            
            signal = result.get("signal", "HOLD")
            confidence = result.get("confidence", 0)
            reason = result.get("reasoning", "No data")

            # Guardar en Base de Datos (SQLite/Mongo según entorno)
            self.db.save_prediction(self.symbol, signal, confidence)
            
            print(f"[*] Señal IA: {signal} ({confidence*100:.1f}%)")
            print(f"[*] Razonamiento: {reason}")
            
            # Lógica simple de ejecución (opcional por ahora)
            if signal == "BUY" and confidence > 0.7:
                print("[!] OPORTUNIDAD DE COMPRA DETECTADA")
                # Aquí iría self.exchange.create_order(...)
            
        except Exception as e:
            print(f"[!] Error en el ciclo: {e}")

    def run(self):
        while True:
            self.execute_logic()
            time.sleep(60) # Esperar 1 minuto

if __name__ == "__main__":
    bot = TradingBot()
    bot.run()
