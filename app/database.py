import os
import sqlite3
from abc import ABC, abstractmethod
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class BaseDB(ABC):
    """Interfaz base para persistencia."""

    def save_prediction(self, symbol, prediction, confidence, reasoning, min_cushion=0, max_cushion=0):
        pass

    def save_trade(self, trade_data):
        pass

    def get_last_trades(self, limit=5):
        pass

    def get_last_predictions(self, limit=5):
        pass

    @abstractmethod
    def get_active_position_cost(self, symbol):
        """Calcula el costo promedio de la posición actual."""
        pass


class SQLiteManager(BaseDB):
    def __init__(self, db_path="trading_bot.db"):
        self.db_path = db_path
        self._create_tables()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _create_tables(self):
        with self._get_connection() as conn:
            # Tabla de predicciones
            conn.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    symbol TEXT,
                    prediction TEXT,
                    confidence REAL,
                    reasoning TEXT,
                    min_cushion REAL,
                    max_cushion REAL
                )
            """)
            # Tabla de trades
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    symbol TEXT,
                    side TEXT,
                    price REAL,
                    amount REAL,
                    cost REAL,
                    fee REAL,
                    balance_before REAL,
                    balance_after REAL,
                    min_cushion REAL,
                    max_cushion REAL,
                    ia_confidence REAL,
                    network TEXT,
                    order_id TEXT
                )
            """)
            # NUEVA: Tabla de escaneo de mercado
            conn.execute("""
                CREATE TABLE IF NOT EXISTS market_scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    symbol TEXT,
                    rank INTEGER,
                    expected_profit_pct REAL,
                    expected_loss_pct REAL,
                    volatility TEXT,
                    recommended_strategy TEXT,
                    recommended_timeframe TEXT,
                    gas_fee_estimate REAL,
                    reasoning TEXT
                )
            """)

    def save_market_scan(self, scan_data):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO market_scans (
                    timestamp, symbol, rank, expected_profit_pct, expected_loss_pct, 
                    volatility, recommended_strategy, recommended_timeframe, 
                    gas_fee_estimate, reasoning
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.utcnow(),
                scan_data['symbol'], scan_data['rank'],
                scan_data['expected_profit_pct'], scan_data['expected_loss_pct'],
                scan_data['volatility'], scan_data['recommended_strategy'],
                scan_data['recommended_timeframe'], scan_data['gas_fee_estimate'],
                scan_data['reasoning']
            ))

    def save_prediction(self, symbol, prediction, confidence, reasoning, min_cushion=0, max_cushion=0):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO predictions (timestamp, symbol, prediction, confidence, reasoning, min_cushion, max_cushion) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (datetime.utcnow(), symbol, prediction, confidence, reasoning, min_cushion, max_cushion)
            )

    def save_trade(self, trade_data):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO trades (
                    timestamp, symbol, side, price, amount, cost, fee, 
                    balance_before, balance_after, min_cushion, max_cushion, 
                    ia_confidence, network, order_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.utcnow(),
                trade_data['symbol'], trade_data['side'], trade_data['price'],
                trade_data['amount'], trade_data.get('cost'), trade_data.get('fee'),
                trade_data.get('balance_before'), trade_data.get('balance_after'),
                trade_data.get('min_cushion'), trade_data.get('max_cushion'),
                trade_data.get('ia_confidence'), trade_data.get('network'),
                trade_data.get('order_id')
            ))
        print(f"[SQLite] Trade guardado: {trade_data['side']} {trade_data['symbol']}")

    def get_last_trades(self, limit=5):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_last_predictions(self, limit=5):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM predictions ORDER BY timestamp DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_active_position_cost(self, symbol):
        """Calcula el costo promedio de las compras que no han sido vendidas."""
        with self._get_connection() as conn:
            # Buscamos la última venta total (donde balance_after para el asset base sea ~0)
            # O simplemente sumamos compras y restamos ventas recientes.
            cursor = conn.execute("""
                SELECT side, price, amount FROM trades 
                WHERE symbol = ? 
                ORDER BY timestamp DESC LIMIT 50
            """, (symbol,))
            trades = cursor.fetchall()

            total_amount = 0
            total_cost = 0

            # Recorremos de más reciente a más antiguo para reconstruir la posición actual
            for side, price, amount in trades:
                if side == "COMPRA":
                    total_amount += amount
                    total_cost += (price * amount)
                elif side == "VENTA":
                    # Si hubo una venta, restamos proporcionalmente o reseteamos si fue venta total
                    total_amount -= amount
                    if total_amount <= 0: break  # Se cerró la posición previa

            if total_amount > 0:
                return total_cost / total_amount
            return 0


class MongoManager(BaseDB):
    def __init__(self):
        self.uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        self.db_name = os.getenv("MONGO_DB_NAME", "trading_bot")
        self.client = MongoClient(self.uri)
        self.db = self.client[self.db_name]

    def save_prediction(self, symbol, prediction, confidence, reasoning, min_cushion=0, max_cushion=0):
        data = {
            "timestamp": datetime.utcnow(),
            "symbol": symbol,
            "prediction": prediction,
            "confidence": confidence,
            "reasoning": reasoning,
            "min_cushion": min_cushion,
            "max_cushion": max_cushion
        }
        self.db.predictions.insert_one(data)

    def save_trade(self, trade_data):
        trade_data["timestamp"] = datetime.utcnow()
        self.db.trades.insert_one(trade_data)
        print(f"[MongoDB] Trade guardado: {trade_data['side']}")

    def get_last_trades(self, limit=5):
        return list(self.db.trades.find().sort("timestamp", -1).limit(limit))

    def get_last_predictions(self, limit=5):
        return list(self.db.predictions.find().sort("timestamp", -1).limit(limit))

    def get_active_position_cost(self, symbol):
        trades = list(self.db.trades.find({"symbol": symbol}).sort("timestamp", -1).limit(50))
        total_amount = 0
        total_cost = 0
        for t in trades:
            if t['side'] == "COMPRA":
                total_amount += t['amount']
                total_cost += (t['price'] * t['amount'])
            elif t['side'] == "VENTA":
                total_amount -= t['amount']
                if total_amount <= 0: break
        return total_cost / total_amount if total_amount > 0 else 0


def get_db_manager():
    env = os.getenv("APP_ENV", "development").lower()
    if env == "production":
        return MongoManager()
    else:
        return SQLiteManager()
