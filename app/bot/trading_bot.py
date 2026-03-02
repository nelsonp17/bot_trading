import os
import sys
import time
import ccxt
import pandas as pd
import argparse
from binance.client import Client
from dotenv import load_dotenv

from app.database import get_db_manager
from app.bot.ia.predictor import get_predictor

load_dotenv()

class TradingBot:
    def __init__(self, provider="gemini", symbol="BTC/USDT", timeframe="1h", budget=100.0, network="sandbox", market_type="spot", scan_id=None):
        self.db = get_db_manager()
        self.predictor = get_predictor(provider)
        self.symbol = symbol
        self.timeframe = timeframe
        self.total_budget = budget # Límite máximo para la IA
        self.network = network.lower()
        self.market_type = market_type.lower()
        self.scan_id = scan_id
        self.current_confidence = 0
        self.is_running = False

        # Filtros de Binance
        self.lot_size_filter = {}
        self.min_notional_filter = 0.0
        self.binance_symbol = self.symbol.split(':')[0].replace("/", "")

        # Selección de llaves y Cliente
        api_key, secret_key, use_testnet = self._setup_keys()
        self.binance_client = Client(api_key, secret_key, testnet=use_testnet)
        
        self._sync_time()
        self._load_symbol_info()

        # CCXT para datos públicos
        self.exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': self.market_type}})
        if use_testnet: self.exchange.set_sandbox_mode(True)

        print(f"[*] Bot inicializado para {self.symbol} ({self.market_type})")
        print(f"[*] Presupuesto máximo gestionable por IA: {self.total_budget} USDT")
        print(f"[*] Red: {self.network}")
        print(f"[*] ID de escaneo: {self.scan_id}")
        self.print_balance()

    def _setup_keys(self):
        if self.network == "mainnet":
            if self.market_type == "future":
                api_key = os.getenv("BINANCE_FUTURES_API_KEY") or os.getenv("BINANCE_API_KEY")
                secret_key = os.getenv("BINANCE_FUTURES_SECRET_KEY") or os.getenv("BINANCE_SECRET_KEY")
                return api_key, secret_key, False
            return os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_SECRET_KEY"), False
        elif self.network == "demo":
            return os.getenv("BINANCE_DEMO_API_KEY"), os.getenv("BINANCE_DEMO_SECRET_KEY"), True
        else:
            # Testnet (sandbox)
            if self.market_type == "future":
                api_key = os.getenv("BINANCE_FUTURES_TESTNET_API_KEY") or os.getenv("BINANCE_TESTNET_API_KEY")
                secret_key = os.getenv("BINANCE_FUTURES_TESTNET_SECRET_KEY") or os.getenv("BINANCE_TESTNET_SECRET_KEY")
                return api_key, secret_key, True
            return os.getenv("BINANCE_TESTNET_API_KEY"), os.getenv("BINANCE_TESTNET_SECRET_KEY"), True

    def _sync_time(self):
        try:
            server_time = self.binance_client.get_server_time()
            self.binance_client.timestamp_offset = server_time['serverTime'] - int(time.time() * 1000)
        except Exception as e: print(f"[!] Error sinc: {e}")

    def _load_symbol_info(self):
        if self.market_type == "spot":
            info = self.binance_client.get_symbol_info(self.binance_symbol)
        else:
            info = self.binance_client.futures_exchange_info()
            info = next((s for s in info['symbols'] if s['symbol'] == self.binance_symbol), None)
        
        if info:
            for f in info['filters']:
                if f['filterType'] == 'LOT_SIZE': self.lot_size_filter = f
                if f['filterType'] in ['NOTIONAL', 'MIN_NOTIONAL']:
                    self.min_notional_filter = float(f.get('minNotional', f.get('notional', 0.0)))

    def _format_quantity(self, quantity):
        step_size = float(self.lot_size_filter.get('stepSize', 0.00000001))
        import math
        precision = len(str(step_size).split('.')[-1].rstrip('0')) if step_size < 1 else 0
        factor = 10 ** precision
        return math.floor(quantity * factor) / factor

    def print_balance(self):
        print("\n[+] Obteniendo balance...")
        try:
            base, quote = self.symbol.split('/')[0], self.symbol.split('/')[1]
            if self.market_type == "spot":
                print("\n[+] Obteniendo balance de spot...")
                balances = self.binance_client.get_account()['balances']
                for b in balances:
                    if b['asset'] in [base, quote]:
                        print(f" {b['asset']}: Disponible={float(b['free']):.8f}")
                return balances
            else:
                balances = self.binance_client.futures_account_balance()
                print("\n[+] Obteniendo balance de futuros...")
                for b in balances:
                    if b['asset'] in [base, quote, 'USDT']:
                        print(f" {b['asset']}: Balance={float(b['balance']):.4f}")
                return balances
        except Exception as e: 
            print(f"[!] Error obteniendo balance: {e}")
            return None

    def get_current_price(self):
        return self.exchange.fetch_ticker(self.symbol)['last']

    def fetch_data(self):
        ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df

    def execute_buy(self, price, amount_to_use):
        try:
            if self.market_type == "spot":
                balance_before = float(self.binance_client.get_asset_balance(asset='USDT')['free'])
            else:
                f_balances = self.binance_client.futures_account_balance()
                balance_before = float(next((b['withdrawAvailable'] for b in f_balances if b['asset'] == 'USDT'), 0))

            if balance_before < amount_to_use:
                amount_to_use = balance_before * 0.98 # Ajuste por seguridad
            
            if amount_to_use < self.min_notional_filter: return None

            quantity = self._format_quantity(amount_to_use / price)
            print(f">>> COMPRA {quantity} {self.symbol} @ {price} ({self.market_type})")

            if self.market_type == "spot":
                order = self.binance_client.order_market_buy(symbol=self.binance_symbol, quantity=quantity)
                executed_qty, cost = float(order['executedQty']), float(order['cummulativeQuoteQty'])
            else:
                order = self.binance_client.futures_create_order(symbol=self.binance_symbol, side='BUY', type='MARKET', quantity=quantity)
                executed_qty, cost = float(order['cumQty']), float(order['cumQuote'])

            time.sleep(2)
            balance_after = balance_before - cost # Simplificado para el log
            
            self.db.save_trade({
                "symbol": self.symbol, "side": "COMPRA", "price": price,
                "amount": executed_qty, "cost": cost, "fee": 0,
                "balance_before": balance_before, "balance_after": balance_after,
                "min_cushion": 0, "max_cushion": 0, # IA los gestiona en su plan
                "ia_confidence": self.current_confidence, "network": self.network, "order_id": order.get('orderId')
            })
            return order
        except Exception as e: print(f"[!] Error compra: {e}"); return None

    def execute_sell(self, price):
        try:
            if self.market_type == "spot":
                balance_before = float(self.binance_client.get_asset_balance(asset=self.symbol.split('/')[0])['free'])
            else:
                pos = self.binance_client.futures_position_information(symbol=self.binance_symbol)
                balance_before = abs(float(next(p['positionAmt'] for p in pos if p['symbol'] == self.binance_symbol)))

            if balance_before <= 0: return None
            quantity = self._format_quantity(balance_before)
            print(f">>> VENTA {quantity} {self.symbol} @ {price} ({self.market_type})")

            if self.market_type == "spot":
                order = self.binance_client.order_market_sell(symbol=self.binance_symbol, quantity=quantity)
                executed_qty, cost = float(order['executedQty']), float(order['cummulativeQuoteQty'])
            else:
                order = self.binance_client.futures_create_order(symbol=self.binance_symbol, side='SELL', type='MARKET', quantity=quantity)
                executed_qty, cost = float(order['cumQty']), float(order['cumQuote'])

            self.db.save_trade({
                "symbol": self.symbol, "side": "VENTA", "price": price,
                "amount": executed_qty, "cost": cost, "fee": 0,
                "balance_before": balance_before, "balance_after": 0,
                "min_cushion": 0, "max_cushion": 0,
                "ia_confidence": self.current_confidence, "network": self.network, "order_id": order.get('orderId')
            })
            return order
        except Exception as e: print(f"[!] Error venta: {e}"); return None

    def execute_logic(self):
        try:
            current_price = self.get_current_price()
            active_plan = self.db.get_active_plan(self.symbol)

            if not active_plan:
                recommendation = self.db.get_latest_market_recommendation(self.symbol, scan_id=self.scan_id)
                if not recommendation: return
                
                print(f"[*] Generando nuevo Plan Blindado para {self.symbol}...")
                account = self.binance_client.get_account() if self.market_type == "spot" else {}
                usdt_free = float(next((b['free'] for b in account.get('balances', []) if b['asset'] == 'USDT'), 0)) if account else self.total_budget
                
                new_plan = self.predictor.get_execution_plan(
                    self.symbol, self.fetch_data(), 
                    {"total_budget_assigned": self.total_budget, "real_account_usdt_available": usdt_free},
                    recommendation, market_type=self.market_type
                )
                if new_plan:
                    self.db.save_execution_plan(new_plan)
                    active_plan = self.db.get_active_plan(self.symbol)
            
            if not active_plan: return
            
            status, plan, op_id = active_plan['status'], active_plan['execution_plan'], active_plan['operation_id']

            if status == "WAITING_FOR_ENTRY":
                if current_price <= plan['entry_config']['trigger_price']:
                    if self.execute_buy(current_price, plan['entry_config']['allocated_capital_usdt']):
                        self.db.update_plan_status(op_id, "IN_POSITION", entry_price=current_price)

            elif status == "IN_POSITION":
                exit_cfg, safety = plan['exit_config'], plan['safety_cushion']
                
                # Take Profit / Stop Loss / Trailing
                if current_price >= exit_cfg['take_profit'] or current_price <= exit_cfg['stop_loss']:
                    if self.execute_sell(current_price): self.db.update_plan_status(op_id, "CLOSED", exit_price=current_price)
                
                # Cojín de Seguridad IA (Emergencia)
                elif current_price < safety['min_price_alert'] or current_price > safety['max_price_alert']:
                    print(f"[!!!] EMERGENCIA IA: Precio fuera de rango seguro ({current_price}).")
                    if self.execute_sell(current_price): self.db.update_plan_status(op_id, "CANCELLED", exit_price=current_price)

        except Exception as e: print(f"[!] Error ciclo: {e}")

    def run(self):
        try:
            self.is_running = True
            while self.is_running:
                self.execute_logic()
                for _ in range(60):
                    if not self.is_running: break
                    time.sleep(1)
        except Exception as e: print(f"[!] Error en el bot: {e}")
