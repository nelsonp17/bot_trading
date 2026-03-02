import os
import sys
import time
import ccxt
import pandas as pd
import importlib
import argparse
from binance.client import Client
from dotenv import load_dotenv

from app.database import get_db_manager
from app.bot.ia.predictor import get_predictor

# Cargar variables de entorno
load_dotenv()


class TradingBot:
    def __init__(self, provider="gemini", symbol="BTC/USDT", timeframe="1h", amount=10.0, budget=None, min_price=0.0,
                 max_price=float('inf'), network="sandbox"):
        self.db = get_db_manager()
        self.predictor = get_predictor(provider)
        self.symbol = symbol
        self.timeframe = timeframe
        self.amount_to_use = amount  # Fallback si no hay budget
        self.total_budget = budget if budget is not None else amount
        self.min_price = min_price
        self.max_price = max_price
        self.network = network.lower()
        self.current_confidence = 0
        self.is_running = False

        # Filtros de Binance (se cargan al iniciar)
        self.lot_size_filter = {}
        self.min_notional_filter = 0.0

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
        else:  # testnet o sandbox
            print(f"[*] Configurando llaves para TESTNET")
            api_key = os.getenv("BINANCE_TESTNET_API_KEY")
            secret_key = os.getenv("BINANCE_TESTNET_SECRET_KEY")
            use_testnet = True

        # Verificar que las llaves no estén vacías
        if not api_key or not secret_key:
            print(f"[!] ERROR: No se encontraron las llaves API para la red {self.network}")
        else:
            print(f"[*] Llaves cargadas correctamente (Inician con: {api_key[:6]}...)")

        # Inicializar Cliente de python-binance
        self.binance_client = Client(api_key, secret_key, testnet=use_testnet)

        # Sincronización de tiempo y filtros
        try:
            print("[*] Sincronizando tiempo con el servidor de Binance...")
            server_time = self.binance_client.get_server_time()
            self.binance_client.timestamp_offset = server_time['serverTime'] - int(time.time() * 1000)

            def patched_get_timestamp():
                return int(time.time() * 1000) + getattr(self.binance_client, 'timestamp_offset', 0)

            self.binance_client._get_timestamp = patched_get_timestamp

            # Cargar filtros del símbolo
            self._load_symbol_info()
            print(f"[*] Sincronización exitosa.")
        except Exception as e:
            print(f"[!] Error al sincronizar: {e}")

        # CCXT solo para datos públicos
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        if use_testnet:
            self.exchange.set_sandbox_mode(True)

        self.print_balance()
        print(f"[*] Bot inicializado para {self.symbol}")
        print(f"[*] Presupuesto total asignado: {self.total_budget} USDT")

    def _load_symbol_info(self):
        """Carga filtros como LOT_SIZE y MIN_NOTIONAL de Binance."""
        info = self.binance_client.get_symbol_info(self.binance_symbol)
        for f in info['filters']:
            if f['filterType'] == 'LOT_SIZE':
                self.lot_size_filter = f
            if f['filterType'] == 'NOTIONAL' or f['filterType'] == 'MIN_NOTIONAL':
                self.min_notional_filter = float(f.get('minNotional', f.get('notional', 0.0)))
        print(f"[*] Filtros cargados para {self.symbol}: Min Notional={self.min_notional_filter}")

    def _format_quantity(self, quantity):
        """Ajusta la cantidad según el stepSize de Binance."""
        step_size = float(self.lot_size_filter.get('stepSize', 0.00000001))
        precision = 0
        if step_size < 1:
            precision = len(str(step_size).split('.')[-1].rstrip('0'))

        # Ajustar por abajo para no exceder saldo
        import math
        factor = 10 ** precision
        return math.floor(quantity * factor) / factor

    def print_balance(self):
        """Muestra el saldo usando python-binance."""
        try:
            account = self.binance_client.get_account(recvWindow=60000)
            balances = account.get('balances', [])

            base = self.symbol.split('/')[0]
            quote = self.symbol.split('/')[1]

            print("\n" + "=" * 40)
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

            print("=" * 40 + "\n")
            return balances
        except Exception as e:
            print(f"[!] Error al obtener saldo: {e}")
            return None

    def fetch_data(self):
        ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df

    def get_current_price(self):
        ticker = self.exchange.fetch_ticker(self.symbol)
        return ticker['last']

    def execute_buy(self, price, amount_to_buy=None):
        try:
            amount_to_use = amount_to_buy if amount_to_buy else self.amount_to_use

            # Validar mínimo notacional (USDT totales)
            if amount_to_use < self.min_notional_filter:
                print(f"[!] Error: El monto {amount_to_use} USDT es menor al mínimo {self.min_notional_filter}")
                return None

            asset_info = self.binance_client.get_asset_balance(asset='USDT', recvWindow=60000)
            balance_before = float(asset_info['free'])

            if balance_before < amount_to_use:
                print(f"[!] Saldo insuficiente en cuenta ({balance_before} USDT) para comprar {amount_to_use} USDT.")
                amount_to_use = balance_before * 0.95  # Usar casi todo lo que queda
                if amount_to_use < self.min_notional_filter: return None

            raw_quantity = amount_to_use / price
            quantity = self._format_quantity(raw_quantity)

            print(f">>> Ejecutando COMPRA de {quantity} {self.symbol.split('/')[0]} a {price} USDT")

            order = self.binance_client.order_market_buy(
                symbol=self.binance_symbol,
                quantity=quantity,
                recvWindow=60000
            )

            # Solo guardamos si llegamos aquí (éxito)
            time.sleep(2)
            asset_info_after = self.binance_client.get_asset_balance(asset='USDT', recvWindow=60000)
            balance_after = float(asset_info_after['free'])

            self.db.save_trade({
                "symbol": self.symbol,
                "side": "COMPRA",
                "price": float(order.get('fills', [{'price': price}])[0]['price']),
                "amount": float(order.get('executedQty', quantity)),
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
                quantity = self._format_quantity(balance_before)

                # Validar mínimo notacional para la venta
                if (quantity * price) < self.min_notional_filter:
                    print(
                        f"[!] No se puede vender: El valor {quantity * price:.2f} USDT es inferior al mínimo permitido.")
                    return None

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
                    "price": float(order.get('fills', [{'price': price}])[0]['price']),
                    "amount": float(order.get('executedQty', quantity)),
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
            print(f"\n[{pd.Timestamp.now().strftime('%d/%m/%Y %H:%M:%S')}] --- Ciclo de análisis ---")

            # 1. Obtener balance real y presupuesto disponible
            balances = self.print_balance()
            base_currency = self.symbol.split('/')[0]
            quote_currency = self.symbol.split('/')[1]

            balance_dict = {}
            if balances:
                for b in balances:
                    if b['asset'] in [base_currency, quote_currency]:
                        balance_dict[b['asset']] = float(b['free'])

            # CORRECCIÓN: Calcular cuánto presupuesto REAL queda.
            # Presupuesto Gastado = Holdings * Precio Actual
            current_price = self.get_current_price()
            holdings = balance_dict.get(base_currency, 0)
            spent_budget = holdings * current_price

            # Obtener precio promedio de compra de la DB
            avg_buy_price = self.db.get_active_position_cost(self.symbol)
            unrealized_pnl_pct = 0
            if avg_buy_price > 0:
                unrealized_pnl_pct = ((current_price - avg_buy_price) / avg_buy_price) * 100

            remaining_budget = max(0, self.total_budget - spent_budget)
            current_usdt = balance_dict.get(quote_currency, 0)

            # BLOQUEO DE RECUPERACIÓN: 
            # Si ya tenemos activos, el presupuesto restante para "nuevas" compras es 0.
            # Solo permitimos usar el budget si holdings es 0.
            if holdings > 0:
                print(
                    f"[*] Posición activa detectada. Precio Promedio: {avg_buy_price:.2f} | PnL: {unrealized_pnl_pct:.2f}%")
                available_for_ia = 0  # No permitir nuevas compras hasta vender
            else:
                available_for_ia = min(remaining_budget, current_usdt)

            context_balance = {
                "total_budget_assigned": self.total_budget,
                "budget_already_spent_in_holdings": spent_budget,
                "budget_remaining_to_spend": remaining_budget,
                "real_account_usdt_available": current_usdt,
                "current_asset_holdings": holdings,
                "avg_buy_price": avg_buy_price,
                "unrealized_pnl_pct": unrealized_pnl_pct
            }

            # 2. Obtener historial reciente para "aprendizaje"
            history = self.db.get_last_predictions(limit=5)

            # 3. Obtener datos de mercado
            df = self.fetch_data()
            print(f"[*] Precio actual {self.symbol}: {current_price} USDT")

            # 4. Predicción con contexto financiero
            result = self.predictor.get_prediction(df, balance=context_balance, history=history)

            signal = result.get("signal", "MANTENER").upper()
            confidence = result.get("confidence", 0)
            required_threshold = result.get("required_threshold", 0.60)
            ai_trade_amount = result.get("trade_amount", 0)

            # --- VALIDACIÓN Y NORMALIZACIÓN DE UMBRALES ---
            # Si la IA envía valores > 1 (como 65 en vez de 0.65), normalizar.
            # Si envía valores gigantes (como precios), capar a 0.95 para permitir operar.
            if confidence > 1: confidence /= 100.0
            if required_threshold > 1:
                if required_threshold > 100:  # Es un precio o error grave
                    print(f"[!] Warning: IA envió umbral inválido ({required_threshold}). Ajustando a 0.70")
                    required_threshold = 0.70
                else:
                    required_threshold /= 100.0

            # Limitar a rango [0, 1]
            confidence = max(0.0, min(1.0, confidence))
            required_threshold = max(0.0, min(1.0, required_threshold))
            # ----------------------------------------------

            self.current_confidence = confidence
            reason = result.get("reasoning", "Sin descripción")

            ai_min = result.get("min_price", 0)
            ai_max = result.get("max_price", float('inf'))

            effective_min = self.min_price if self.min_price > 0 else ai_min
            effective_max = self.max_price if self.max_price < 999999 else ai_max

            self.db.save_prediction(self.symbol, signal, confidence, reason, ai_min, ai_max)

            print(f"[*] IA recomienda: {signal}")
            print(f"    - Presupuesto Restante: {remaining_budget:.2f} USDT")
            if signal == "COMPRA":
                print(f"    - Monto Sugerido: {ai_trade_amount} USDT")
            print(f"    - Confianza Actual: {confidence * 100:.1f}%")
            print(f"    - Umbral Requerido: {required_threshold * 100:.1f}%")
            print(f"[*] Motivo: {reason}")

            # Lógica de ejecución
            if signal == "COMPRA" and ai_trade_amount > 0:
                if confidence >= required_threshold:
                    if effective_min <= current_price <= effective_max:
                        # Usar el monto de la IA pero limitado por el presupuesto real
                        final_amount = min(ai_trade_amount, available_for_ia)
                        if final_amount >= self.min_notional_filter:
                            self.execute_buy(current_price, amount_to_buy=final_amount)
                        else:
                            print(f"[!] Monto {final_amount:.2f} insuficiente para el mínimo de exchange.")
                    else:
                        print(f"[!] COMPRA ignorada: Precio {current_price} fuera del rango seguro.")
                else:
                    print(f"[!] COMPRA ignorada: Confianza insuficiente.")

            elif signal == "VENTA":
                if confidence >= required_threshold:
                    if effective_min <= current_price <= effective_max:
                        self.execute_sell(current_price)
                    else:
                        print(f"[!] VENTA ignorada: Precio {current_price} fuera del rango seguro.")
                else:
                    print(f"[!] VENTA ignorada: Confianza insuficiente.")

            elif signal == "MANTENER" or ai_trade_amount == 0:
                print(f"[*] Acción: MANTENER - Esperando mejores condiciones o monto 0.")

        except Exception as e:
            print(f"[!] Error en el ciclo: {e}")

    def run(self):
        self.is_running = True
        try:
            while self.is_running:
                self.execute_logic()
                for _ in range(60):
                    if not self.is_running:
                        break
                    time.sleep(1)
        finally:
            self.is_running = False

