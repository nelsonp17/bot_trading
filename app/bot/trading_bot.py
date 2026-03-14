import os
import sys
import time
import uuid
import json
from datetime import datetime, timedelta
import ccxt
import pandas as pd
import argparse
from binance.client import Client
from dotenv import load_dotenv

from app.database import get_db_manager
from app.bot.ia.predictor import get_predictor, validate_execution_plan

load_dotenv()


class TradingBot:
    """
    Bot de Ejecución: Se encarga de llevar a cabo las órdenes de compra y venta.
    No toma decisiones por sí solo; sigue un 'Plan de Ejecución' generado por la IA
    basado en un análisis previo del MarketScanner.
    """

    def __init__(
        self,
        provider="gemini",
        symbol="BTC/USDT",
        timeframe="1h",
        budget=100.0,
        network="sandbox",
        market_type="spot",
        scan_id=None,
        run_script_id=None,
        max_losses=None,
        cooldown=None,
    ):
        """
        Inicializa el bot y configura la conexión con Binance.

        Args:
            max_losses: Máximo de pérdidas consecutivas antes de circuit breaker
            cooldown: Segundos de espera después de activar circuit breaker
        """
        self.db = get_db_manager()
        self.provider = provider
        self.predictor = get_predictor(provider)
        self.symbol = symbol
        self.timeframe = timeframe  # mantener por compatibilidad
        self.timeframes_config = self._load_timeframes_config()
        self.primary_timeframe = timeframe  # por defecto
        self.primary_history = 100  # por defecto
        self.secondary_timeframes = []

        if self.timeframes_config and self.symbol in self.timeframes_config:
            symbol_config = self.timeframes_config[self.symbol]
            primary = symbol_config.get("primary", {})
            if primary.get("timeframe"):
                self.primary_timeframe = primary["timeframe"]
                self.primary_history = primary.get("history", 100)
            self.secondary_timeframes = symbol_config.get("secondary", [])
            print(
                f"[*] Timeframe primary configurado: {self.primary_timeframe} (history: {self.primary_history})"
            )
            if self.secondary_timeframes:
                print(
                    f"[*] Timeframes secondary: {[s.get('timeframe') for s in self.secondary_timeframes]}"
                )

        self.total_budget = budget  # Presupuesto máximo que la IA puede gestionar
        self.network = network.lower()
        self.market_type = market_type.lower()
        self.scan_id = scan_id
        self.run_script_id = run_script_id
        self.current_confidence = 0
        self.is_running = False

        # Circuit Breaker - Configuración de seguridad
        # Prioridad: parámetros > variables de entorno > valores por defecto
        self.max_consecutive_losses = (
            max_losses
            if max_losses is not None
            else int(os.getenv("MAX_CONSECUTIVE_LOSSES", "3"))
        )
        self.consecutive_losses = 0
        self.circuit_breaker_active = False
        self.circuit_breaker_cooldown = (
            cooldown
            if cooldown is not None
            else int(os.getenv("CIRCUIT_BREAKER_COOLDOWN", "300"))
        )

        # Filtros de precisión de Binance (evitan errores de 'APIError(code=-1013)')
        self.lot_size_filter = {}
        self.min_notional_filter = 0.0
        self.binance_symbol = self.symbol.split(":")[0].replace("/", "")

        self.create_if_not_exist_run_script()

        # Selección de credenciales (Testnet o Mainnet) y Cliente Oficial
        api_key, secret_key, use_testnet = self._setup_keys()
        self.binance_client = Client(api_key, secret_key, testnet=use_testnet)

        self._sync_time()  # Sincronizar reloj para evitar errores de firma
        self._load_symbol_info()  # Cargar límites de cantidad y precio mínimo

        # CCXT para descarga de datos públicos (OHLCV)
        self.exchange = ccxt.binance(
            {"enableRateLimit": True, "options": {"defaultType": self.market_type}}
        )
        if use_testnet:
            self.exchange.set_sandbox_mode(True)

        print(f"[*] Bot inicializado para {self.symbol} ({self.market_type})")
        print(f"[*] Red: {self.network} | Presupuesto: {self.total_budget} USDT")
        self._check_downtime()
        self.print_balance()
        self.print_inversion()

    def _load_timeframes_config(self):
        """Carga la configuración de timeframes desde el archivo JSON."""
        # Intentar desde el directorio actual (raíz del proyecto)
        config_path = "data/timeframes/timeframes_config.json"
        if not os.path.exists(config_path):
            # Intentar ruta relativa a este archivo
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            config_path = os.path.join(
                base_dir, "data/timeframes/timeframes_config.json"
            )

        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                    print(
                        f"[*] Configuración de timeframes cargada desde {config_path}"
                    )
                    return config
            except Exception as e:
                print(f"[!] Error cargando configuración de timeframes: {e}")
        else:
            print(
                f"[*] No se encontró archivo de configuración de timeframes. Usando timeframe por defecto: {self.timeframe}"
            )
        return None

    def create_if_not_exist_run_script(self):
        """Si no existe el run script id lo registra en la base de datos.
        Si ya existe un plan activo para este símbolo, usa ese run_script_id para continuar."""
        try:
            if self.run_script_id is None:
                # Primero verificar si hay un plan activo existente para este símbolo
                existing_plan = self.db.get_active_plan(self.symbol)
                if existing_plan and existing_plan.get("run_script_id"):
                    # Continuar con el plan existente
                    self.run_script_id = existing_plan["run_script_id"]
                    print(
                        f"[*] Continuando con plan existente (ID: {self.run_script_id})"
                    )

                    # Actualizar el run_script para marcar que fue restaurado
                    run_script = self.db.get_run_script_by_id(self.run_script_id)
                    if not run_script:
                        self.db.save_run_script(
                            {
                                "id": self.run_script_id,
                                "start_time": datetime.utcnow(),
                                "name_script": f"Bot Trading {self.symbol} ({self.market_type})",
                                "initial_capital": self.total_budget,
                                "params": {"restored": True, "symbol": self.symbol},
                            }
                        )
                else:
                    # No hay plan existente, crear nuevo run_script_id
                    self.run_script_id = str(uuid.uuid4())
                    self.db.save_run_script(
                        {
                            "id": self.run_script_id,
                            "start_time": datetime.utcnow(),
                            "name_script": f"Bot Trading {self.symbol} ({self.market_type})",
                            "initial_capital": self.total_budget,
                            "params": {
                                "timeframe": self.timeframe,
                                "budget": self.total_budget,
                                "network": self.network,
                                "market_type": self.market_type,
                                "scan_id": self.scan_id,
                                "provider": self.provider,
                                "symbol": self.symbol,
                            },
                        }
                    )
            else:
                run_script = self.db.get_run_script_by_id(self.run_script_id)
                if not run_script:
                    self.db.save_run_script(
                        {
                            "id": self.run_script_id,
                            "start_time": datetime.utcnow(),
                            "name_script": f"Bot Trading {self.symbol} ({self.market_type})",
                            "initial_capital": self.total_budget,
                            "params": {"restored": True, "symbol": self.symbol},
                        }
                    )
        except Exception as e:
            print(f"[!] Error gestionando run script: {e}")

    def _check_downtime(self):
        """Calcula y reporta cuánto tiempo estuvo el bot fuera de línea."""
        try:
            from datetime import datetime

            last_heartbeat = self.db.get_last_heartbeat(
                f"BOT_{self.symbol.replace('/', '_')}"
            )
            if last_heartbeat:
                ahora = datetime.utcnow()
                downtime = ahora - last_heartbeat
                if (
                    downtime.total_seconds() > 120
                ):  # Más de 2 minutos se considera downtime real
                    mins = int(downtime.total_seconds() / 60)
                    print(
                        f"\n[!] AVISO: El bot estuvo fuera de línea por aproximadamente {mins} minutos."
                    )
                    print(
                        f"[*] El mercado no fue monitoreado durante este intervalo. Retomando vigilancia..."
                    )
            else:
                print("[*] Primer arranque detectado o sin registro de latido previo.")
        except Exception as e:
            print(f"[!] Error chequeando downtime: {e}")

    def _check_circuit_breaker(self):
        """Verifica si el circuit breaker está activo."""
        if self.circuit_breaker_active:
            print(f"\n[!] CIRCUIT BREAKER ACTIVO")
            print(
                f"[*] Esperando {self.circuit_breaker_cooldown}s antes de reintentar..."
            )
            import time

            time.sleep(self.circuit_breaker_cooldown)
            self.circuit_breaker_active = False
            self.consecutive_losses = 0
            print(f"[*] Circuit breaker reseteado. Continuando operaciones...")
        return True

    def _update_circuit_breaker(self, is_profit):
        """Actualiza el contador de pérdidas consecutivas."""
        if is_profit:
            self.consecutive_losses = 0
            print("[*] Operación exitosa. Contador de pérdidas reseteado.")
        else:
            self.consecutive_losses += 1
            print(
                f"[!] Operación perdedora. Pérdidas consecutivas: {self.consecutive_losses}/{self.max_consecutive_losses}"
            )

            if self.consecutive_losses >= self.max_consecutive_losses:
                print(
                    f"\n[!] LÍMITE DE PÉRDIDAS CONSECUTIVAS ALCANZADO ({self.max_consecutive_losses})"
                )
                print(f"[!] Activando circuit breaker por seguridad...")
                self.circuit_breaker_active = True

    def _setup_keys(self):
        """Gestiona las API Keys dinámicamente según la red y el mercado."""
        if self.network == "mainnet":
            if self.market_type == "future":
                api_key = os.getenv("BINANCE_FUTURES_API_KEY") or os.getenv(
                    "BINANCE_API_KEY"
                )
                secret_key = os.getenv("BINANCE_FUTURES_SECRET_KEY") or os.getenv(
                    "BINANCE_SECRET_KEY"
                )
                return api_key, secret_key, False
            return os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_SECRET_KEY"), False
        elif self.network == "demo":
            return (
                os.getenv("BINANCE_DEMO_API_KEY"),
                os.getenv("BINANCE_DEMO_SECRET_KEY"),
                True,
            )
        else:
            # Red de pruebas (Sandbox / Testnet)
            if self.market_type == "future":
                api_key = os.getenv("BINANCE_FUTURES_TESTNET_API_KEY") or os.getenv(
                    "BINANCE_TESTNET_API_KEY"
                )
                secret_key = os.getenv(
                    "BINANCE_FUTURES_TESTNET_SECRET_KEY"
                ) or os.getenv("BINANCE_TESTNET_SECRET_KEY")
                return api_key, secret_key, True
            return (
                os.getenv("BINANCE_TESTNET_API_KEY"),
                os.getenv("BINANCE_TESTNET_SECRET_KEY"),
                True,
            )

    def _sync_time(self):
        """Calcula el offset entre el servidor de Binance y el equipo local."""
        try:
            server_time = self.binance_client.get_server_time()
            self.binance_client.timestamp_offset = server_time["serverTime"] - int(
                time.time() * 1000
            )
        except Exception as e:
            print(f"[!] Error sinc: {e}")

    def _load_symbol_info(self):
        """Carga las reglas de validación de Binance (paso de cantidad, monto mínimo)."""
        if self.market_type == "spot":
            info = self.binance_client.get_symbol_info(self.binance_symbol)
        else:
            info = self.binance_client.futures_exchange_info()
            info = next(
                (s for s in info["symbols"] if s["symbol"] == self.binance_symbol), None
            )

        if info:
            for f in info["filters"]:
                if f["filterType"] == "LOT_SIZE":
                    self.lot_size_filter = f
                if f["filterType"] in ["NOTIONAL", "MIN_NOTIONAL"]:
                    self.min_notional_filter = float(
                        f.get("minNotional", f.get("notional", 0.0))
                    )

    def _format_quantity(self, quantity):
        """Ajusta la cantidad de la orden para cumplir con el 'stepSize' de Binance."""
        step_size = float(self.lot_size_filter.get("stepSize", 0.00000001))
        import math

        precision = (
            len(str(step_size).split(".")[-1].rstrip("0")) if step_size < 1 else 0
        )
        factor = 10**precision
        return math.floor(quantity * factor) / factor

    def print_inversion(self):
        """Muestra el desglose financiero de la sesión actual."""
        print("\n" + "=" * 50)
        print(f"📊 RESUMEN DE INVERSIÓN (ID: {self.run_script_id})")
        print("=" * 50)
        try:
            run_script = self.db.get_run_script_by_id(self.run_script_id)
            initial_capital = (
                run_script["initial_capital"] if run_script else self.total_budget
            )

            trades = self.db.get_all_trades(self.run_script_id)

            inversion_total = sum(t["cost"] for t in trades if t["side"] == "COMPRA")
            capital_recuperado = sum(t["cost"] for t in trades if t["side"] == "VENTA")

            # Extraer la moneda base del símbolo
            base = self.symbol.split("/")[0]

            # Cálculo de Inversión Actual (lo que no se ha vendido aún)
            compras = [t for t in trades if t["side"] == "COMPRA"]
            ventas = [t for t in trades if t["side"] == "VENTA"]

            total_comprado_qty = sum(t["amount"] for t in compras)
            total_vendido_qty = sum(t["amount"] for t in ventas)
            qty_actual = total_comprado_qty - total_vendido_qty

            # Estimamos el costo de la inversión actual basándonos en el precio promedio de compra
            avg_buy_price = (
                inversion_total / total_comprado_qty if total_comprado_qty > 0 else 0
            )
            inversion_actual = qty_actual * avg_buy_price

            # P&L Realizado
            costo_de_lo_vendido = total_vendido_qty * avg_buy_price
            pnl_realizado = capital_recuperado - costo_de_lo_vendido

            ganancias = pnl_realizado if pnl_realizado > 0 else 0
            perdidas = abs(pnl_realizado) if pnl_realizado < 0 else 0

            capital_actual = initial_capital + capital_recuperado - inversion_total

            # Obtener posición actual si es futures
            posicion_actual = ""
            if self.market_type == "future" and qty_actual > 0:
                try:
                    current_price = self.get_current_price()
                    pos_value = qty_actual * current_price
                    pos_pnl_pct = (
                        ((current_price / avg_buy_price) - 1) * 100
                        if avg_buy_price > 0
                        else 0
                    )
                    posicion_actual = f" | Posición: {qty_actual:.4f} {base} ({pos_value:.2f} USDT) | P/L: {pos_pnl_pct:+.2f}%"
                except:
                    pass

            print(f" [+] Capital Inicial:      {initial_capital:.2f} USDT")
            print(f" [+] Inversión Total:      {inversion_total:.2f} USDT")
            print(f" [+] Capital Recuperado:   {capital_recuperado:.2f} USDT")
            print(
                f" [+] Inversión Actual:     {inversion_actual:.2f} USDT {posicion_actual}"
            )
            print(f" [+] Ganancias (Realiz.):  {ganancias:.2f} USDT")
            print(f" [+] Pérdidas (Realiz.):   {perdidas:.2f} USDT")
            print(f" [!] CAPITAL ACTUAL:       {capital_actual:.2f} USDT")
            print("=" * 50 + "\n")

        except Exception as e:
            print(f"[!] Error al calcular inversión: {e}")

    def print_balance(self):
        """Muestra el saldo disponible en la cuenta configurada y posiciones abiertas."""
        print("\n[+] Obteniendo balance en Binance...")
        try:
            base, quote = self.symbol.split("/")[0], self.symbol.split("/")[1]
            if self.market_type == "spot":
                balances = self.binance_client.get_account()["balances"]
                for b in balances:
                    if b["asset"] in [base, quote]:
                        print(
                            f" [*] TOTAL EN {b['asset']}: Disponible={float(b['free']):.8f}"
                        )
                return balances
            else:
                balances = self.binance_client.futures_account_balance()
                for b in balances:
                    if b["asset"] in [base, quote, "USDT"]:
                        print(
                            f" [*] TOTAL EN {b['asset']}: Balance={float(b['balance']):.4f}"
                        )

                # Mostrar posiciones abiertas en futuros
                try:
                    positions = self.binance_client.futures_position_information(
                        symbol=self.binance_symbol
                    )
                    for pos in positions:
                        if float(pos.get("positionAmt", 0)) != 0:
                            qty = float(pos["positionAmt"])
                            entry = float(pos["entryPrice"])
                            pnl = float(pos["unRealizedProfit"])
                            pos_value = qty * entry
                            pnl_pct = (pnl / pos_value * 100) if pos_value > 0 else 0
                            print(
                                f" [*] POSICIÓN: {pos['symbol']} - Cantidad: {qty:.4f} (~{pos_value:.2f} USDT) | Entry: {entry:.4f} | P/L: {pnl:+.4f} USDT ({pnl_pct:+.2f}%)"
                            )
                except Exception as e:
                    print(f" [!] Error obteniendo posición: {e}")

                return balances
        except Exception as e:
            print(f"[!] Error obteniendo balance: {e}")
            return None

    def get_current_price(self):
        """Obtiene el último precio de mercado (Last Price) del símbolo."""
        return self.exchange.fetch_ticker(self.symbol)["last"]

    def fetch_data(self):
        """Descarga datos históricos (OHLCV) para el análisis de la IA."""
        limit = (
            self.primary_history
            if self.primary_history and self.primary_history > 0
            else None
        )
        ohlcv = self.exchange.fetch_ohlcv(
            self.symbol, self.primary_timeframe, limit=limit
        )
        df = pd.DataFrame(
            ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df

    def execute_buy(
        self,
        price,
        amount_to_use,
        order_type="MARKET",
        limit_price=None,
        timeout_seconds=60,
    ):
        """
        Ejecuta una orden de COMPRA y registra los detalles en la DB.

        Args:
            price: Precio de referencia (para LIMIT es el precio de la orden)
            amount_to_use: Cantidad en USDT a usar
            order_type: "MARKET" o "LIMIT"
            limit_price: Precio específico para orden LIMIT (si es None, usa price)
            timeout_seconds: Tiempo máximo para esperar orden LIMIT
        """
        try:
            # Verificación de fondos reales - RECONFIRMAR antes de ejecutar
            if self.market_type == "spot":
                balance_before = float(
                    self.binance_client.get_asset_balance(asset="USDT")["free"]
                )
            else:
                f_balances = self.binance_client.futures_account_balance()
                asset_data = next((b for b in f_balances if b["asset"] == "USDT"), {})
                balance_before = float(
                    asset_data.get("availableBalance", asset_data.get("balance", 0))
                )

            # RECONFIRMAR: Verificar que el balance sigue siendo suficiente
            if balance_before < amount_to_use:
                print(
                    f"[!] Balance insuficiente. Disponible: {balance_before:.2f} USDT, Solicitado: {amount_to_use:.2f} USDT"
                )
                amount_to_use = (
                    balance_before * 0.98
                )  # Margen de seguridad para comisiones
                if amount_to_use < self.min_notional_filter:
                    print(
                        f"[!] Monto insuficiente para el mínimo de Binance ({self.min_notional_filter} USDT)."
                    )
                    return None

            if amount_to_use < self.min_notional_filter:
                print(
                    f"[!] Monto insuficiente para el mínimo de Binance ({self.min_notional_filter} USDT)."
                )
                return None

            quantity = self._format_quantity(amount_to_use / price)
            order_type = order_type.upper()

            print(
                f"\n>>> EJECUTANDO COMPRA: {quantity} {self.symbol} @ {price} ({order_type})"
            )

            # Determinar precio para orden LIMIT
            limit_price = limit_price if limit_price else price

            if self.market_type == "spot":
                if order_type == "LIMIT":
                    order = self.binance_client.order_limit_buy(
                        symbol=self.binance_symbol, quantity=quantity, price=limit_price
                    )
                    # Esperar a que se ejecute la orden
                    order = self._wait_for_order_fill(order["orderId"], timeout_seconds)
                    if not order or order["status"] != "FILLED":
                        print(
                            f"[!] Orden LIMIT no completada: {order.get('status') if order else 'N/A'}"
                        )
                        return None
                else:
                    order = self.binance_client.order_market_buy(
                        symbol=self.binance_symbol, quantity=quantity
                    )
                executed_qty = float(order["executedQty"])
                cost = float(order["cummulativeQuoteQty"])
                executed_price = float(order.get("price", price))
            else:
                if order_type == "LIMIT":
                    order = self.binance_client.futures_create_order(
                        symbol=self.binance_symbol,
                        side="BUY",
                        type="LIMIT",
                        quantity=quantity,
                        price=limit_price,
                        timeInForce="GTC",
                    )
                    # Esperar a que se ejecute la orden
                    order = self._wait_for_order_fill(
                        order["orderId"], timeout_seconds, is_future=True
                    )
                    if not order or order.get("status") != "FILLED":
                        print(
                            f"[!] Orden LIMIT no completada: {order.get('status') if order else 'N/A'}"
                        )
                        return None
                else:
                    order = self.binance_client.futures_create_order(
                        symbol=self.binance_symbol,
                        side="BUY",
                        type="MARKET",
                        quantity=quantity,
                    )
                executed_qty = float(order.get("cumQty", quantity))
                cost = float(order.get("cumQuote", executed_qty * price))
                executed_price = float(order.get("avgPrice", price))

            # Guardar trade en la base de datos
            self.db.save_trade(
                {
                    "symbol": self.symbol,
                    "side": "COMPRA",
                    "price": executed_price,
                    "amount": executed_qty,
                    "cost": cost,
                    "fee": 0,
                    "balance_before": balance_before,
                    "balance_after": balance_before - cost,
                    "ia_confidence": self.current_confidence,
                    "network": self.network,
                    "order_id": order.get("orderId"),
                    "order_type": order_type,
                },
                run_script_id=self.run_script_id,
            )

            self.print_inversion()
            return order
        except Exception as e:
            print(f"[!] Error en ejecución de compra: {e}")
            return None

    def _wait_for_order_fill(self, order_id, timeout_seconds=60, is_future=False):
        """Espera a que una orden LIMIT sea completada."""
        import time

        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            try:
                if is_future:
                    order = self.binance_client.futures_get_order(
                        symbol=self.binance_symbol, orderId=order_id
                    )
                    status = order.get("status")
                else:
                    order = self.binance_client.get_order(
                        symbol=self.binance_symbol, orderId=order_id
                    )
                    status = order.get("status")

                if status == "FILLED":
                    return order
                elif status in ["CANCELLED", "REJECTED", "EXPIRED"]:
                    return order
                time.sleep(1)
            except Exception as e:
                print(f"[!] Error esperando orden: {e}")
                time.sleep(1)

        return None

    def execute_sell(self, price):
        """Ejecuta una orden de VENTA a mercado (Cierre de posición)."""
        try:
            # Localizar activos disponibles para vender
            if self.market_type == "spot":
                balance_before = float(
                    self.binance_client.get_asset_balance(
                        asset=self.symbol.split("/")[0]
                    )["free"]
                )
            else:
                pos = self.binance_client.futures_position_information(
                    symbol=self.binance_symbol
                )
                asset_pos = next(
                    (p for p in pos if p["symbol"] == self.binance_symbol), {}
                )
                balance_before = abs(float(asset_pos.get("positionAmt", 0)))

            if balance_before <= 0:
                print(f"[*] No hay posición activa para {self.symbol} para cerrar.")
                return None

            quantity = self._format_quantity(balance_before)
            print(f"\n>>> EJECUTANDO VENTA: {quantity} {self.symbol} @ {price}")

            if self.market_type == "spot":
                order = self.binance_client.order_market_sell(
                    symbol=self.binance_symbol, quantity=quantity
                )
                executed_qty, cost = (
                    float(order["executedQty"]),
                    float(order["cummulativeQuoteQty"]),
                )
            else:
                order = self.binance_client.futures_create_order(
                    symbol=self.binance_symbol,
                    side="SELL",
                    type="MARKET",
                    quantity=quantity,
                )
                executed_qty, cost = float(order["cumQty"]), float(order["cumQuote"])

            self.db.save_trade(
                {
                    "symbol": self.symbol,
                    "side": "VENTA",
                    "price": price,
                    "amount": executed_qty,
                    "cost": cost,
                    "fee": 0,
                    "balance_before": balance_before,
                    "balance_after": 0,
                    "network": self.network,
                    "order_id": order.get("orderId"),
                },
                run_script_id=self.run_script_id,
            )

            self.print_inversion()
            return order
        except Exception as e:
            print(f"[!] Error en ejecución de venta: {e}")
            return None

    def execute_partial_sell(self, percent_to_sell, current_price, entry_price):
        """
        Ejecuta una venta parcial de la posición.

        Args:
            percent_to_sell: Porcentaje de la posición a vender (0-100)
            current_price: Precio actual del mercado
            entry_price: Precio de entrada para calcular P/L

        Returns:
            True si se ejecutó correctamente, False en caso contrario
        """
        try:
            # Obtener la posición actual
            if self.market_type == "spot":
                balance_before = float(
                    self.binance_client.get_asset_balance(
                        asset=self.symbol.split("/")[0]
                    )["free"]
                )
            else:
                pos = self.binance_client.futures_position_information(
                    symbol=self.binance_symbol
                )
                asset_pos = next(
                    (p for p in pos if p["symbol"] == self.binance_symbol), {}
                )
                balance_before = abs(float(asset_pos.get("positionAmt", 0)))

            if balance_before <= 0:
                print(f"[*] No hay posición para vender parcialmente.")
                return False

            # Calcular cantidad a vender
            quantity_to_sell = self._format_quantity(
                balance_before * (percent_to_sell / 100)
            )

            if quantity_to_sell <= 0:
                print(f"[!] Cantidad a vender insuficiente.")
                return False

            print(
                f"\n>>> EJECUTANDO VENTA PARCIAL: {quantity_to_sell} {self.symbol} @ {current_price} ({percent_to_sell}%)"
            )

            # Ejecutar la venta
            if self.market_type == "spot":
                order = self.binance_client.order_market_sell(
                    symbol=self.binance_symbol, quantity=quantity_to_sell
                )
                executed_qty = float(order["executedQty"])
                cost = float(order["cummulativeQuoteQty"])
            else:
                order = self.binance_client.futures_create_order(
                    symbol=self.binance_symbol,
                    side="SELL",
                    type="MARKET",
                    quantity=quantity_to_sell,
                )
                executed_qty = float(order.get("cumQty", quantity_to_sell))
                cost = float(order.get("cumQuote", executed_qty * current_price))

            # Calcular P/L de esta venta
            cost_basis = executed_qty * entry_price
            profit = cost - cost_basis
            profit_pct = (profit / cost_basis * 100) if cost_basis > 0 else 0

            # Guardar trade
            self.db.save_trade(
                {
                    "symbol": self.symbol,
                    "side": f"VENTA_PARCIAL_{percent_to_sell}%",
                    "price": current_price,
                    "amount": executed_qty,
                    "cost": cost,
                    "fee": 0,
                    "balance_before": balance_before,
                    "balance_after": balance_before - executed_qty,
                    "network": self.network,
                    "order_id": order.get("orderId"),
                    "profit_usdt": profit,
                    "profit_pct": profit_pct,
                },
                run_script_id=self.run_script_id,
            )

            print(
                f"[+] Venta parcial ejecutada: {profit:+.2f} USDT ({profit_pct:+.2f}%)"
            )
            self.print_inversion()
            return True

        except Exception as e:
            print(f"[!] Error en ejecución de venta parcial: {e}")
            return False

    def execute_logic(self):
        """
        Ciclo de decisión técnica:
        1. Comprobar si hay un plan activo en la DB.
        2. Evaluar caducidad del plan (TTL).
        3. Si no hay plan válido, pedir uno nuevo a la IA.
        4. Seguir disparadores de entrada o salida.
        """
        try:
            # --- VERIFICAR CIRCUIT BREAKER ---
            if not self._check_circuit_breaker():
                return

            current_price = self.get_current_price()
            active_plan = self.db.get_active_plan(self.symbol, self.run_script_id)

            # --- LÓGICA DE CADUCIDAD (TTL) ---
            if active_plan:
                # El timestamp en SQLite viene como string 'YYYY-MM-DD HH:MM:SS.mmmmmm'
                ts_str = active_plan["timestamp"]
                if isinstance(ts_str, str):
                    # Limpiar milisegundos si existen para compatibilidad
                    ts_str = ts_str.split(".")[0]
                    fecha_plan = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                else:
                    fecha_plan = ts_str  # En MongoDB ya es objeto datetime

                ahora = datetime.utcnow()
                antiguedad = ahora - fecha_plan
                status = active_plan["status"]
                op_id = active_plan["operation_id"]

                # 1. Si el plan es muy viejo (ej. > 24h) y no hemos entrado, se descarta
                if status == "WAITING_FOR_ENTRY" and antiguedad > timedelta(hours=24):
                    print(
                        f"\n[!] CADUCIDAD: El plan de entrada para {self.symbol} tiene {antiguedad.total_seconds() / 3600:.1f}h. Es demasiado viejo. Expirando..."
                    )
                    self.db.update_plan_status(
                        op_id, "CANCELLED", run_script_id=self.run_script_id
                    )
                    return

                # 2. Límite de ejecución de 1 hora (Mandato del usuario)
                if status == "IN_POSITION" and antiguedad > timedelta(hours=1):
                    print(
                        f"\n[!] TIEMPO LÍMITE: La posición de {self.symbol} ha superado 1 hora de ejecución ({antiguedad.total_seconds() / 60:.1f} min). Cerrando por caducidad técnica..."
                    )
                    if self.execute_sell(current_price):
                        self.db.update_plan_status(
                            op_id,
                            "CLOSED",
                            exit_price=current_price,
                            run_script_id=self.run_script_id,
                        )
                    return

            if not active_plan:
                # Buscar recomendación del MarketScanner
                recommendation = self.db.get_latest_market_recommendation(
                    self.symbol, scan_id=self.scan_id, run_script_id=self.run_script_id
                )
                if not recommendation:
                    return

                print(
                    f"[*] Generando nuevo Plan de Ejecución con IA para {self.symbol}..."
                )

                # Obtener capital ya invertido y calcular disponible
                # Si hay un plan activo, obtener la inversión actual del mismo
                invested_capital = 0
                if active_plan and active_plan.get("status") == "IN_POSITION":
                    entry_price = active_plan.get("entry_price", 0)
                    # Calcular cantidad basada en el capital invertido (allocated_capital / entry_price)
                    entry_config = active_plan.get("execution_plan", {}).get(
                        "entry_config", {}
                    )
                    allocated_capital = entry_config.get("allocated_capital_usdt", 0)
                    if entry_price > 0 and allocated_capital > 0:
                        invested_capital = allocated_capital
                    else:
                        invested_capital = 0

                # Calcular capital disponible (inicial - ya invertido)
                available_budget = self.total_budget - invested_capital
                if available_budget <= 0:
                    available_budget = 0

                # Obtener balance real de Binance para referencia
                try:
                    if self.market_type == "spot":
                        bal = self.binance_client.get_asset_balance(asset="USDT")
                        usdt_free = float(bal["free"]) if bal else 0
                    else:
                        f_bal = self.binance_client.futures_account_balance()
                        usdt_free = float(
                            next(
                                (
                                    b["availableBalance"]
                                    for b in f_bal
                                    if b["asset"] == "USDT"
                                ),
                                0,
                            )
                        )
                except Exception:
                    usdt_free = available_budget

                # La IA diseña el punto exacto de entrada y los límites de seguridad
                new_plan = self.predictor.get_execution_plan(
                    self.symbol,
                    self.fetch_data(),
                    {
                        "total_budget_assigned": self.total_budget,
                        "available_budget": available_budget,
                        "invested_capital": invested_capital,
                        "real_account_usdt_available": usdt_free,
                    },
                    recommendation,
                    market_type=self.market_type,
                    timeframe=self.primary_timeframe,
                )
                if new_plan:
                    # VALIDACIÓN DEL PLAN DE EJECUCIÓN
                    is_valid, validation_msg = validate_execution_plan(
                        new_plan, current_price, min_notional=self.min_notional_filter
                    )

                    if not is_valid:
                        print(f"\n[!] PLAN RECHAZADO: {validation_msg}")
                        print(
                            f"[*] El plan no será guardado. Reintentando en el siguiente ciclo..."
                        )
                        # No guardamos el plan inválido, esperamos nuevo análisis
                        return

                    # Detectar si el plan viene anidado (formato DeepSeek) o plano
                    inner_plan = new_plan.get("execution_plan", new_plan)
                    entry_cfg = inner_plan.get("entry_config", {})
                    exit_cfg = inner_plan.get("exit_config", {})

                    # Extraer razonamiento y estrategia desde la raíz o metadata
                    strategy = new_plan.get("strategy_type") or new_plan.get(
                        "strategy_name", "Técnica Dinámica"
                    )
                    reasoning = new_plan.get("reasoning") or new_plan.get(
                        "metadata", {}
                    ).get("reasoning_summary", "Sin descripción")

                    # Mostrar el razonamiento estratégico de la IA
                    print("\n" + "=" * 60)
                    print(f"🧠 RAZONAMIENTO ESTRATÉGICO DE LA IA ({self.symbol})")
                    print(f"🎯 Estrategia: {strategy}")
                    print(f"📖 Análisis: {reasoning}")

                    if entry_cfg and exit_cfg:
                        print(
                            f"🚀 Plan: Entrada en {entry_cfg.get('trigger_price')} | TP: {exit_cfg.get('take_profit')} | SL: {exit_cfg.get('stop_loss')}"
                        )
                    else:
                        print(
                            "[!] Advertencia: No se pudieron extraer los niveles de precio del plan."
                        )
                        import json

                        print(f"DEBUG JSON: {json.dumps(new_plan, indent=2)}")

                    print("=" * 60 + "\n")

                    self.db.save_execution_plan(
                        new_plan, run_script_id=self.run_script_id
                    )
                    active_plan = self.db.get_active_plan(
                        self.symbol, self.run_script_id
                    )

            if not active_plan:
                return

            status, plan, op_id = (
                active_plan["status"],
                active_plan["execution_plan"],
                active_plan["operation_id"],
            )

            # GESTIÓN DE ESTADOS CON LOGS EN TIEMPO REAL
            if status == "WAITING_FOR_ENTRY":
                trigger_price = plan["entry_config"]["trigger_price"]
                order_type = (
                    plan["entry_config"]
                    .get("order_type", "MARKET")
                    .replace("LIMIT_", "")
                )
                distancia = ((current_price / trigger_price) - 1) * 100
                print(
                    f"[*] [ESPERANDO ENTRADA] {self.symbol}: {current_price} | Objetivo: {trigger_price} (Distancia: {distancia:+.2f}%)"
                )

                # Si el precio se mueve muy lejos del objetivo (>2% away), cancelar y regenerar
                if abs(distancia) > 2.0:
                    print(
                        f"[!] Precio se mueve lejos del objetivo ({distancia:+.2f}%). Cancelando plan y regenerando..."
                    )
                    self.db.update_plan_status(
                        op_id,
                        "CANCELLED",
                        run_script_id=self.run_script_id,
                    )
                    active_plan = None

                if active_plan and current_price <= trigger_price:
                    if self.execute_buy(
                        current_price,
                        plan["entry_config"]["allocated_capital_usdt"],
                        order_type=order_type,
                        limit_price=trigger_price if order_type == "LIMIT" else None,
                    ):
                        self.db.update_plan_status(
                            op_id,
                            "IN_POSITION",
                            entry_price=current_price,
                            run_script_id=self.run_script_id,
                        )
                        self.print_balance()
                        self.print_inversion()

            elif status == "IN_POSITION":
                exit_cfg, safety = plan["exit_config"], plan["safety_cushion"]
                tp = exit_cfg.get("take_profit", 0)
                sl = exit_cfg.get("stop_loss", 0)

                # Partial Take Profit - Soporta múltiples niveles
                partial_tp_levels = exit_cfg.get("partial_tp_levels", [])

                # Trailing Stop
                trailing_stop = exit_cfg.get("trailing_stop_distance_percent", 0)
                trailing_activation = exit_cfg.get("trailing_stop_activation_price", 0)

                # Recuperar datos de la entrada (precio y cantidad)
                entry_price = active_plan.get("entry_price", 0)
                invested_usdt = plan["entry_config"].get("allocated_capital_usdt", 0)

                # Calcular métricas en tiempo real
                pl_flotante = (
                    ((current_price / entry_price) - 1) * 100 if entry_price > 0 else 0
                )
                dist_tp = ((tp / current_price) - 1) * 100 if tp > 0 else 0
                dist_sl = ((sl / current_price) - 1) * 100 if sl > 0 else 0

                print(f"[*] [EN POSICIÓN] {self.symbol}")
                print(
                    f"    > Precio Actual: {current_price} | Entrada: {entry_price} | P/L: {pl_flotante:+.2f}%"
                )
                print(
                    f"    > Inversión: {invested_usdt:.2f} USDT | TP: {tp} ({dist_tp:+.2f}%) | SL: {sl} ({dist_sl:+.2f}%)"
                )

                # 0. Partial Take Profit - Si hay niveles configurados
                if partial_tp_levels:
                    for level in partial_tp_levels:
                        tp_price = level.get("price", 0)
                        tp_percent = level.get("percent", 50)

                        if current_price >= tp_price and tp_price > 0:
                            print(
                                f"[*] ¡TP PARCIAL! Alcanzando nivel {tp_price} ({tp_percent}% de posición)"
                            )
                            # Vendemos solo una vez por nivel
                            if self.execute_partial_sell(
                                tp_percent, current_price, entry_price
                            ):
                                print(
                                    f"[+] Partial TP ejecutado: {tp_percent}% vendido a {current_price}"
                                )
                                break

                # 1. Trailing Stop - Si está activado y el precio subió lo suficiente
                if (
                    trailing_stop > 0
                    and trailing_activation > 0
                    and current_price > trailing_activation
                ):
                    trailing_sl = current_price * (1 - trailing_stop / 100)
                    if trailing_sl > sl:  # Solo si es mejor que el SL original
                        print(
                            f"[*] Trailing Stop activo: SL dinámico en {trailing_sl:.8f}"
                        )
                        sl = trailing_sl

                # 2. Salida por Objetivo (Take Profit) o Protección (Stop Loss)
                if current_price >= tp or current_price <= sl:
                    razon = "TAKE PROFIT" if current_price >= tp else "STOP LOSS"
                    print(
                        f"[*] ¡OBJETIVO ALCANZADO ({razon})! Cerrando posición completa..."
                    )
                    if self.execute_sell(current_price):
                        is_profit = current_price > entry_price
                        self._update_circuit_breaker(is_profit)
                        self.db.update_plan_status(
                            op_id,
                            "CLOSED",
                            exit_price=current_price,
                            run_script_id=self.run_script_id,
                        )

                # 2. Salida por Cojín de Seguridad (Emergencia IA)
                elif (
                    current_price < safety["min_price_alert"]
                    or current_price > safety["max_price_alert"]
                ):
                    print(
                        f"\n[!!!] EMERGENCIA IA: Precio ({current_price}) fuera de rango seguro [{safety['min_price_alert']} - {safety['max_price_alert']}]."
                    )
                    print(
                        f"[!] Motivo: Violación de estructura técnica definida por la IA. Abortando posición."
                    )
                    if self.execute_sell(current_price):
                        is_profit = current_price > entry_price
                        self._update_circuit_breaker(is_profit)
                        self.db.update_plan_status(
                            op_id,
                            "CANCELLED",
                            exit_price=current_price,
                            run_script_id=self.run_script_id,
                        )

        except Exception as e:
            print(f"[!] Error en ciclo de ejecución: {e}")

    def run(self):
        """Bucle principal de ejecución (Polling)."""
        try:
            self.is_running = True
            bot_id = f"BOT_{self.symbol.replace('/', '_')}"
            print(f"[*] Bot en marcha. Monitoreando cada 60 segundos...")
            while self.is_running:
                # Actualizar latido para control de downtime
                self.db.save_heartbeat(bot_id, self.run_script_id)

                self.execute_logic()
                for _ in range(60):
                    if not self.is_running:
                        break
                    time.sleep(1)
        except Exception as e:
            print(f"[!] El bot se ha detenido por un error: {e}")
