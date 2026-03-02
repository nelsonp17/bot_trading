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
    """
    Bot de Ejecución: Se encarga de llevar a cabo las órdenes de compra y venta.
    No toma decisiones por sí solo; sigue un 'Plan de Ejecución' generado por la IA
    basado en un análisis previo del MarketScanner.
    """

    def __init__(self, provider="gemini", symbol="BTC/USDT", timeframe="1h", budget=100.0, network="sandbox", market_type="spot", scan_id=None):
        """
        Inicializa el bot y configura la conexión con Binance.
        """
        self.db = get_db_manager()
        self.predictor = get_predictor(provider)
        self.symbol = symbol
        self.timeframe = timeframe
        self.total_budget = budget # Presupuesto máximo que la IA puede gestionar
        self.network = network.lower()
        self.market_type = market_type.lower()
        self.scan_id = scan_id
        self.current_confidence = 0
        self.is_running = False

        # Filtros de precisión de Binance (evitan errores de 'APIError(code=-1013)')
        self.lot_size_filter = {}
        self.min_notional_filter = 0.0
        self.binance_symbol = self.symbol.split(':')[0].replace("/", "")

        # Selección de credenciales (Testnet o Mainnet) y Cliente Oficial
        api_key, secret_key, use_testnet = self._setup_keys()
        self.binance_client = Client(api_key, secret_key, testnet=use_testnet)
        
        self._sync_time()          # Sincronizar reloj para evitar errores de firma
        self._load_symbol_info()   # Cargar límites de cantidad y precio mínimo

        # CCXT para descarga de datos públicos (OHLCV)
        self.exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': self.market_type}})
        if use_testnet: self.exchange.set_sandbox_mode(True)

        print(f"[*] Bot inicializado para {self.symbol} ({self.market_type})")
        print(f"[*] Red: {self.network} | Presupuesto: {self.total_budget} USDT")
        self._check_downtime()
        self.print_balance()

    def _check_downtime(self):
        """Calcula y reporta cuánto tiempo estuvo el bot fuera de línea."""
        try:
            from datetime import datetime
            last_heartbeat = self.db.get_last_heartbeat(f"BOT_{self.symbol.replace('/', '_')}")
            if last_heartbeat:
                ahora = datetime.utcnow()
                downtime = ahora - last_heartbeat
                if downtime.total_seconds() > 120: # Más de 2 minutos se considera downtime real
                    mins = int(downtime.total_seconds() / 60)
                    print(f"\n[!] AVISO: El bot estuvo fuera de línea por aproximadamente {mins} minutos.")
                    print(f"[*] El mercado no fue monitoreado durante este intervalo. Retomando vigilancia...")
            else:
                print("[*] Primer arranque detectado o sin registro de latido previo.")
        except Exception as e: print(f"[!] Error chequeando downtime: {e}")

    def _setup_keys(self):
        """Gestiona las API Keys dinámicamente según la red y el mercado."""
        if self.network == "mainnet":
            if self.market_type == "future":
                api_key = os.getenv("BINANCE_FUTURES_API_KEY") or os.getenv("BINANCE_API_KEY")
                secret_key = os.getenv("BINANCE_FUTURES_SECRET_KEY") or os.getenv("BINANCE_SECRET_KEY")
                return api_key, secret_key, False
            return os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_SECRET_KEY"), False
        elif self.network == "demo":
            return os.getenv("BINANCE_DEMO_API_KEY"), os.getenv("BINANCE_DEMO_SECRET_KEY"), True
        else:
            # Red de pruebas (Sandbox / Testnet)
            if self.market_type == "future":
                api_key = os.getenv("BINANCE_FUTURES_TESTNET_API_KEY") or os.getenv("BINANCE_TESTNET_API_KEY")
                secret_key = os.getenv("BINANCE_FUTURES_TESTNET_SECRET_KEY") or os.getenv("BINANCE_TESTNET_SECRET_KEY")
                return api_key, secret_key, True
            return os.getenv("BINANCE_TESTNET_API_KEY"), os.getenv("BINANCE_TESTNET_SECRET_KEY"), True

    def _sync_time(self):
        """Calcula el offset entre el servidor de Binance y el equipo local."""
        try:
            server_time = self.binance_client.get_server_time()
            self.binance_client.timestamp_offset = server_time['serverTime'] - int(time.time() * 1000)
        except Exception as e: print(f"[!] Error sinc: {e}")

    def _load_symbol_info(self):
        """Carga las reglas de validación de Binance (paso de cantidad, monto mínimo)."""
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
        """Ajusta la cantidad de la orden para cumplir con el 'stepSize' de Binance."""
        step_size = float(self.lot_size_filter.get('stepSize', 0.00000001))
        import math
        precision = len(str(step_size).split('.')[-1].rstrip('0')) if step_size < 1 else 0
        factor = 10 ** precision
        return math.floor(quantity * factor) / factor

    def print_balance(self):
        """Muestra el saldo disponible en la cuenta configurada."""
        print("\n[+] Obteniendo balance...")
        try:
            base, quote = self.symbol.split('/')[0], self.symbol.split('/')[1]
            if self.market_type == "spot":
                balances = self.binance_client.get_account()['balances']
                for b in balances:
                    if b['asset'] in [base, quote]:
                        print(f" {b['asset']}: Disponible={float(b['free']):.8f}")
                return balances
            else:
                balances = self.binance_client.futures_account_balance()
                for b in balances:
                    if b['asset'] in [base, quote, 'USDT']:
                        print(f" {b['asset']}: Balance={float(b['balance']):.4f}")
                return balances
        except Exception as e: 
            print(f"[!] Error obteniendo balance: {e}")
            return None

    def get_current_price(self):
        """Obtiene el último precio de mercado (Last Price) del símbolo."""
        return self.exchange.fetch_ticker(self.symbol)['last']

    def fetch_data(self):
        """Descarga datos históricos (OHLCV) para el análisis de la IA."""
        ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df

    def execute_buy(self, price, amount_to_use):
        """Ejecuta una orden de COMPRA a mercado y registra los detalles en la DB."""
        try:
            # Verificación de fondos reales
            if self.market_type == "spot":
                balance_before = float(self.binance_client.get_asset_balance(asset='USDT')['free'])
            else:
                f_balances = self.binance_client.futures_account_balance()
                asset_data = next((b for b in f_balances if b['asset'] == 'USDT'), {})
                balance_before = float(asset_data.get('availableBalance', asset_data.get('balance', 0)))

            if balance_before < amount_to_use:
                amount_to_use = balance_before * 0.98 # Margen de seguridad para comisiones
            
            if amount_to_use < self.min_notional_filter:
                print(f"[!] Monto insuficiente para el mínimo de Binance ({self.min_notional_filter} USDT).")
                return None

            quantity = self._format_quantity(amount_to_use / price)
            print(f"\n>>> EJECUTANDO COMPRA: {quantity} {self.symbol} @ {price} ({self.market_type})")

            if self.market_type == "spot":
                order = self.binance_client.order_market_buy(symbol=self.binance_symbol, quantity=quantity)
                executed_qty, cost = float(order['executedQty']), float(order['cummulativeQuoteQty'])
            else:
                order = self.binance_client.futures_create_order(symbol=self.binance_symbol, side='BUY', type='MARKET', quantity=quantity)
                executed_qty, cost = float(order['cumQty']), float(order['cumQuote'])

            # Guardar trade en la base de datos
            self.db.save_trade({
                "symbol": self.symbol, 
                "side": "COMPRA", 
                "price": price,
                "amount": executed_qty, 
                "cost": cost, 
                "fee": 0,
                "balance_before": balance_before, 
                "balance_after": balance_before - cost,
                "ia_confidence": self.current_confidence, 
                "network": self.network, 
                "order_id": order.get('orderId')
            })
            return order
        except Exception as e: print(f"[!] Error en ejecución de compra: {e}"); return None

    def execute_sell(self, price):
        """Ejecuta una orden de VENTA a mercado (Cierre de posición)."""
        try:
            # Localizar activos disponibles para vender
            if self.market_type == "spot":
                balance_before = float(self.binance_client.get_asset_balance(asset=self.symbol.split('/')[0])['free'])
            else:
                pos = self.binance_client.futures_position_information(symbol=self.binance_symbol)
                asset_pos = next((p for p in pos if p['symbol'] == self.binance_symbol), {})
                balance_before = abs(float(asset_pos.get('positionAmt', 0)))

            if balance_before <= 0: 
                print(f"[*] No hay posición activa para {self.symbol} para cerrar.")
                return None

            quantity = self._format_quantity(balance_before)
            print(f"\n>>> EJECUTANDO VENTA: {quantity} {self.symbol} @ {price}")

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
                "network": self.network, "order_id": order.get('orderId')
            })
            return order
        except Exception as e: print(f"[!] Error en ejecución de venta: {e}"); return None

    def execute_logic(self):
        """
        Ciclo de decisión técnica:
        1. Comprobar si hay un plan activo en la DB.
        2. Evaluar caducidad del plan (TTL).
        3. Si no hay plan válido, pedir uno nuevo a la IA.
        4. Seguir disparadores de entrada o salida.
        """
        try:
            from datetime import datetime, timedelta
            current_price = self.get_current_price()
            active_plan = self.db.get_active_plan(self.symbol)

            # --- LÓGICA DE CADUCIDAD (TTL) ---
            if active_plan:
                # El timestamp en SQLite viene como string 'YYYY-MM-DD HH:MM:SS.mmmmmm'
                ts_str = active_plan['timestamp']
                if isinstance(ts_str, str):
                    # Limpiar milisegundos si existen para compatibilidad
                    ts_str = ts_str.split('.')[0]
                    fecha_plan = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                else:
                    fecha_plan = ts_str # En MongoDB ya es objeto datetime

                ahora = datetime.utcnow()
                antiguedad = ahora - fecha_plan
                status = active_plan['status']
                op_id = active_plan['operation_id']

                # 1. Si el plan es muy viejo (ej. > 24h) y no hemos entrado, se descarta
                if status == "WAITING_FOR_ENTRY" and antiguedad > timedelta(hours=24):
                    print(f"\n[!] CADUCIDAD: El plan de entrada para {self.symbol} tiene {antiguedad.total_seconds()/3600:.1f}h. Es demasiado viejo. Expirando...")
                    self.db.update_plan_status(op_id, "CANCELLED")
                    return

                # 2. Límite de ejecución de 1 hora (Mandato del usuario)
                # Si estamos en posición por más de 1 hora, cerramos para evitar "trades fantasma"
                if status == "IN_POSITION" and antiguedad > timedelta(hours=1):
                    print(f"\n[!] TIEMPO LÍMITE: La posición de {self.symbol} ha superado 1 hora de ejecución ({antiguedad.total_seconds()/60:.1f} min). Cerrando por caducidad técnica...")
                    if self.execute_sell(current_price):
                        self.db.update_plan_status(op_id, "CLOSED", exit_price=current_price)
                    return

            if not active_plan:
                # Buscar recomendación del MarketScanner
                recommendation = self.db.get_latest_market_recommendation(self.symbol, scan_id=self.scan_id)
                if not recommendation: return
                
                print(f"[*] Generando nuevo Plan de Ejecución con IA para {self.symbol}...")
                
                # Obtener balance real para que la IA decida cuánto usar
                try:
                    if self.market_type == "spot":
                        bal = self.binance_client.get_asset_balance(asset='USDT')
                        usdt_free = float(bal['free']) if bal else 0
                    else:
                        f_bal = self.binance_client.futures_account_balance()
                        usdt_free = float(next((b['availableBalance'] for b in f_bal if b['asset'] == 'USDT'), 0))
                except Exception: usdt_free = self.total_budget

                # La IA diseña el punto exacto de entrada y los límites de seguridad
                new_plan = self.predictor.get_execution_plan(
                    self.symbol, self.fetch_data(), 
                    {
                        "total_budget_assigned": self.total_budget, 
                        "real_account_usdt_available": usdt_free
                    },
                    recommendation, market_type=self.market_type
                )
                if new_plan:
                    # Detectar si el plan viene anidado (formato DeepSeek) o plano
                    inner_plan = new_plan.get('execution_plan', new_plan)
                    entry_cfg = inner_plan.get('entry_config', {})
                    exit_cfg = inner_plan.get('exit_config', {})
                    
                    # Extraer razonamiento y estrategia desde la raíz o metadata
                    strategy = new_plan.get('strategy_type') or new_plan.get('strategy_name', 'Técnica Dinámica')
                    reasoning = new_plan.get('reasoning') or new_plan.get('metadata', {}).get('reasoning_summary', 'Sin descripción')
                    
                    # Mostrar el razonamiento estratégico de la IA
                    print("\n" + "="*60)
                    print(f"🧠 RAZONAMIENTO ESTRATÉGICO DE LA IA ({self.symbol})")
                    print(f"🎯 Estrategia: {strategy}")
                    print(f"📖 Análisis: {reasoning}")
                    
                    if entry_cfg and exit_cfg:
                        print(f"🚀 Plan: Entrada en {entry_cfg.get('trigger_price')} | TP: {exit_cfg.get('take_profit')} | SL: {exit_cfg.get('stop_loss')}")
                    else:
                        print("[!] Advertencia: No se pudieron extraer los niveles de precio del plan.")
                        import json
                        print(f"DEBUG JSON: {json.dumps(new_plan, indent=2)}")
                    
                    print("="*60 + "\n")
                    
                    self.db.save_execution_plan(new_plan)
                    active_plan = self.db.get_active_plan(self.symbol)
            
            if not active_plan: return
            
            status, plan, op_id = active_plan['status'], active_plan['execution_plan'], active_plan['operation_id']

            # GESTIÓN DE ESTADOS CON LOGS EN TIEMPO REAL
            if status == "WAITING_FOR_ENTRY":
                trigger_price = plan['entry_config']['trigger_price']
                distancia = ((current_price / trigger_price) - 1) * 100
                print(f"[*] [ESPERANDO ENTRADA] {self.symbol}: {current_price} | Objetivo: {trigger_price} (Distancia: {distancia:+.2f}%)")
                
                if current_price <= trigger_price:
                    if self.execute_buy(current_price, plan['entry_config']['allocated_capital_usdt']):
                        self.db.update_plan_status(op_id, "IN_POSITION", entry_price=current_price)

            elif status == "IN_POSITION":
                exit_cfg, safety = plan['exit_config'], plan['safety_cushion']
                tp = exit_cfg['take_profit']
                sl = exit_cfg['stop_loss']
                
                # Recuperar datos de la entrada (precio y cantidad)
                entry_price = active_plan.get('entry_price', 0)
                # Intentamos obtener la cantidad desde el plan o la DB
                invested_usdt = plan['entry_config'].get('allocated_capital_usdt', 0)
                
                # Calcular métricas en tiempo real
                pl_flotante = ((current_price / entry_price) - 1) * 100 if entry_price > 0 else 0
                dist_tp = ((tp / current_price) - 1) * 100
                dist_sl = ((sl / current_price) - 1) * 100
                
                print(f"[*] [EN POSICIÓN] {self.symbol}")
                print(f"    > Precio Actual: {current_price} | Entrada: {entry_price} | P/L: {pl_flotante:+.2f}%")
                print(f"    > Inversión: {invested_usdt:.2f} USDT | TP: {tp} ({dist_tp:+.2f}%) | SL: {sl} ({dist_sl:+.2f}%)")
                
                # 1. Salida por Objetivo (Take Profit) o Protección (Stop Loss)
                if current_price >= tp or current_price <= sl:
                    razon = "TAKE PROFIT" if current_price >= tp else "STOP LOSS"
                    print(f"[*] ¡OBJETIVO ALCANZADO ({razon})! Cerrando posición...")
                    if self.execute_sell(current_price): 
                        self.db.update_plan_status(op_id, "CLOSED", exit_price=current_price)
                
                # 2. Salida por Cojín de Seguridad (Emergencia IA)
                elif current_price < safety['min_price_alert'] or current_price > safety['max_price_alert']:
                    print(f"\n[!!!] EMERGENCIA IA: Precio ({current_price}) fuera de rango seguro [{safety['min_price_alert']} - {safety['max_price_alert']}].")
                    print(f"[!] Motivo: Violación de estructura técnica definida por la IA. Abortando posición.")
                    if self.execute_sell(current_price): 
                        self.db.update_plan_status(op_id, "CANCELLED", exit_price=current_price)

        except Exception as e: print(f"[!] Error en ciclo de ejecución: {e}")

    def run(self):
        """Bucle principal de ejecución (Polling)."""
        try:
            self.is_running = True
            bot_id = f"BOT_{self.symbol.replace('/', '_')}"
            print(f"[*] Bot en marcha. Monitoreando cada 60 segundos...")
            while self.is_running:
                # Actualizar latido para control de downtime
                self.db.save_heartbeat(bot_id)
                
                self.execute_logic()
                for _ in range(60):
                    if not self.is_running: break
                    time.sleep(1)
        except Exception as e: print(f"[!] El bot se ha detenido por un error: {e}")
