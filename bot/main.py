import os
import time
import ccxt
import pandas as pd
import argparse
from binance.client import Client 
from dotenv import load_dotenv
from database import get_db_manager
from predictor import get_predictor

# Cargar variables de entorno
load_dotenv()

class TradingBot:
    def __init__(self, provider="gemini", symbol="BTC/USDT", timeframe="1h", amount=10.0, min_price=0.0, max_price=float('inf'), network="sandbox"):
        self.db = get_db_manager()
        self.predictor = get_predictor(provider)
        self.symbol = symbol
        self.timeframe = timeframe
        self.amount_to_use = amount
        self.min_price = min_price
        self.max_price = max_price
        self.network = network.lower()
        self.current_confidence = 0
        
        # Símbolo para python-binance (ej: BTCUSDT)
        self.binance_symbol = self.symbol.replace("/", "")
        
        # Selección de llaves
        if self.network == "mainnet":
            print(f"[*] Configurando llaves para MAINNET")
            api_key = os.getenv("BINANCE_API_KEY")
            secret_key = os.getenv("BINANCE_SECRET_KEY")
            use_testnet = False
        elif self.network == "demo":
            print(f"[*] Configurando llaves para MODO DEMO (Testnet)")
            api_key = os.getenv("BINANCE_DEMO_API_KEY")
            secret_key = os.getenv("BINANCE_DEMO_SECRET_KEY")
            use_testnet = True
        else: # testnet o sandbox
            print(f"[*] Configurando llaves para TESTNET")
            api_key = os.getenv("BINANCE_TESTNET_API_KEY")
            secret_key = os.getenv("BINANCE_TESTNET_SECRET_KEY")
            use_testnet = True

        # Verificar que las llaves no estén vacías
        if not api_key or not secret_key:
            print(f"[!] ERROR: No se encontraron las llaves API para la red {self.network}")
            print(f"[!] Revisa tu archivo .env y asegúrate de tener las variables correctas.")
        else:
            print(f"[*] Llaves cargadas correctamente (Inician con: {api_key[:6]}...)")

        # Inicializar Cliente de python-binance
        # Forzamos testnet=True para demo/testnet
        self.binance_client = Client(api_key, secret_key, testnet=use_testnet)
        
        # Sincronización de tiempo
        try:
            print("[*] Sincronizando tiempo con el servidor de Binance...")
            server_time = self.binance_client.get_server_time()
            self.binance_client.timestamp_offset = server_time['serverTime'] - int(time.time() * 1000)
            
            def patched_get_timestamp():
                return int(time.time() * 1000) + getattr(self.binance_client, 'timestamp_offset', 0)
            self.binance_client._get_timestamp = patched_get_timestamp
            print(f"[*] Sincronización exitosa (Offset: {self.binance_client.timestamp_offset}ms)")
        except Exception as e:
            print(f"[!] Error al sincronizar tiempo: {e}")

        # CCXT solo para datos públicos
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        if use_testnet:
            self.exchange.set_sandbox_mode(True)

        self.print_balance()
        print(f"[*] Bot inicializado para {self.symbol}")
        print(f"[*] Red: {self.network.upper()}")

    def print_balance(self):
        """Muestra el saldo usando python-binance."""
        try:
            # Añadimos un pequeño retardo y recvWindow alto
            account = self.binance_client.get_account(recvWindow=60000)
            balances = account.get('balances', [])
            
            base = self.symbol.split('/')[0]
            quote = self.symbol.split('/')[1]
            
            print("\n" + "="*40)
            print(f" SALDO ACTUAL ({self.network.upper()})")
            print("-" * 40)
            
            found = False
            for asset in balances:
                if asset['asset'] in [base, quote]:
                    free = float(asset['free'])
                    locked = float(asset['locked'])
                    print(f" {asset['asset']}: Disponible={free:.8f} | Bloqueado={locked:.8f}")
                    found = True
            
            if not found:
                print(f" [!] No se encontró saldo para {base} o {quote}.")
                print(f" [!] Mostrando primeros 3 activos con saldo:")
                count = 0
                for asset in balances:
                    if float(asset['free']) > 0 and count < 3:
                        print(f" - {asset['asset']}: {asset['free']}")
                        count += 1

            print("="*40 + "\n")
            return balances
        except Exception as e:
            print(f"[!] Error al obtener saldo (binance-python): {e}")
            if "Signature for this request is not valid" in str(e):
                print("[!] Sugerencia: Tu Secret Key podría estar mal copiada o tiene espacios al final.")
            return None

    def fetch_data(self):
        ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df

    def get_current_price(self):
        ticker = self.exchange.fetch_ticker(self.symbol)
        return ticker['last']

    def execute_buy(self, price):
        try:
            asset_info = self.binance_client.get_asset_balance(asset='USDT', recvWindow=60000)
            balance_before = float(asset_info['free'])
            
            quantity = self.amount_to_use / price
            quantity = round(quantity, 4) # Reducimos precisión para evitar errores de lote
            
            print(f">>> Ejecutando COMPRA de {quantity} {self.symbol.split('/')[0]} a {price} USDT")
            
            order = self.binance_client.order_market_buy(
                symbol=self.binance_symbol,
                quantity=quantity,
                recvWindow=60000
            )
            
            time.sleep(2)
            asset_info_after = self.binance_client.get_asset_balance(asset='USDT', recvWindow=60000)
            balance_after = float(asset_info_after['free'])
            
            self.db.save_trade({
                "symbol": self.symbol,
                "side": "COMPRA",
                "price": price,
                "amount": quantity,
                "cost": float(order.get('cummulativeQuoteQty', quantity * price)),
                "fee": 0,
                "balance_before": balance_before,
                "balance_after": balance_after,
                "min_cushion": self.min_price,
                "max_cushion": self.max_price,
                "ia_confidence": self.current_confidence,
                "network": self.network,
                "order_id": order.get('orderId')
            })
            self.print_balance()
            return order
        except Exception as e:
            print(f"[!] Error al comprar (binance-python): {e}")
            return None

    def execute_sell(self, price):
        try:
            base_currency = self.symbol.split('/')[0]
            asset_info = self.binance_client.get_asset_balance(asset=base_currency, recvWindow=60000)
            balance_before = float(asset_info['free'])
            
            if balance_before > 0:
                quantity = round(balance_before, 4)
                print(f">>> Ejecutando VENTA de {quantity} {base_currency} a {price} USDT")
                
                order = self.binance_client.order_market_sell(
                    symbol=self.binance_symbol,
                    quantity=quantity,
                    recvWindow=60000
                )
                
                time.sleep(2)
                asset_info_after = self.binance_client.get_asset_balance(asset=base_currency, recvWindow=60000)
                balance_after = float(asset_info_after['free'])
                
                self.db.save_trade({
                    "symbol": self.symbol,
                    "side": "VENTA",
                    "price": price,
                    "amount": quantity,
                    "cost": float(order.get('cummulativeQuoteQty', quantity * price)),
                    "fee": 0,
                    "balance_before": balance_before,
                    "balance_after": balance_after,
                    "min_cushion": self.min_price,
                    "max_cushion": self.max_price,
                    "ia_confidence": self.current_confidence,
                    "network": self.network,
                    "order_id": order.get('orderId')
                })
                self.print_balance()
                return order
            else:
                print("[!] No hay saldo suficiente para vender.")
                return None
        except Exception as e:
            print(f"[!] Error al vender (binance-python): {e}")
            return None

    def execute_logic(self):
        try:
            print(f"\n[{pd.Timestamp.now()}] --- Ciclo de análisis ---")
            df = self.fetch_data()
            current_price = self.get_current_price()
            print(f"[*] Precio actual {self.symbol}: {current_price} USDT")

            result = self.predictor.get_prediction(df)
            signal = result.get("signal", "MANTENER").upper()
            confidence = result.get("confidence", 0)
            self.current_confidence = confidence
            reason = result.get("reasoning", "Sin descripción")
            
            ai_min = result.get("min_price", 0)
            ai_max = result.get("max_price", float('inf'))
            
            effective_min = self.min_price if self.min_price > 0 else ai_min
            effective_max = self.max_price if self.max_price < 999999 else ai_max

            self.db.save_prediction(self.symbol, signal, confidence, reason, ai_min, ai_max)
            
            print(f"[*] IA recomienda: {signal} | Confianza: {confidence*100:.1f}%")
            print(f"[*] Rango Seguro Sugerido: Mín={ai_min} | Máx={ai_max}")
            print(f"[*] Motivo: {reason}")
            
            if signal == "COMPRA" and confidence >= 0.65:
                if effective_min <= current_price <= effective_max:
                    self.execute_buy(current_price)
                else:
                    print(f"[!] COMPRA ignorada: Precio {current_price} fuera del rango seguro (Mín={effective_min}, Máx={effective_max})")
            
            elif signal == "VENTA" and confidence >= 0.65:
                if effective_min <= current_price <= effective_max:
                    self.execute_sell(current_price)
                else:
                    print(f"[!] VENTA ignorada: Precio {current_price} fuera del rango seguro (Mín={effective_min}, Máx={effective_max})")
            
            elif signal == "MANTENER":
                print(f"[*] Acción: MANTENER - Esperando mejores condiciones.")
            else:
                print(f"[*] Señal {signal} con confianza baja ({confidence*100:.1f}%). No se ejecuta acción.")

        except Exception as e:
            print(f"[!] Error en el ciclo: {e}")

    def run(self):
        while True:
            self.execute_logic()
            time.sleep(60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bot de Trading con IA")
    parser.add_argument("--provider", type=str, default="gemini", choices=["gemini", "deepseek"], help="Proveedor IA")
    parser.add_argument("--symbol", type=str, default="BTC/USDT", help="Par de trading")
    parser.add_argument("--timeframe", type=str, default="1h", help="Timeframe")
    parser.add_argument("--amount", type=float, default=100.0, help="USDT por operación")
    parser.add_argument("--min-price", type=float, default=0.0, help="Precio Mínimo")
    parser.add_argument("--max-price", type=float, default=999999.0, help="Precio Máximo")
    parser.add_argument("--network", type=str, default="sandbox", choices=["sandbox", "testnet", "mainnet", "demo"], 
                        help="Red de operación: sandbox, testnet, mainnet o demo")
    
    args = parser.parse_args()
    
    bot = TradingBot(
        provider=args.provider,
        symbol=args.symbol,
        timeframe=args.timeframe,
        amount=args.amount,
        min_price=args.min_price,
        max_price=args.max_price,
        network=args.network
    )
    bot.run()
