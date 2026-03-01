import os
import sqlite3
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class BaseDB:
    """Interfaz base para persistencia."""
    def save_prediction(self, symbol, prediction, confidence, reasoning, min_cushion=0, max_cushion=0):
        pass
    def save_trade(self, trade_data):
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
            # Tabla de trades expandida para estadísticas
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

def get_db_manager():
    env = os.getenv("APP_ENV", "development").lower()
    if env == "production":
        return MongoManager()
    else:
        return SQLiteManager()
