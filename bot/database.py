import os
import sqlite3
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class BaseDB:
    """Interfaz base para persistencia."""
    def save_prediction(self, symbol, prediction, confidence):
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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    symbol TEXT,
                    prediction TEXT,
                    confidence REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    symbol TEXT,
                    side TEXT,
                    price REAL,
                    amount REAL
                )
            """)

    def save_prediction(self, symbol, prediction, confidence):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO predictions (timestamp, symbol, prediction, confidence) VALUES (?, ?, ?, ?)",
                (datetime.utcnow(), symbol, prediction, confidence)
            )
        print(f"[SQLite] Predicción guardada: {prediction}")

    def save_trade(self, trade_data):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO trades (timestamp, symbol, side, price, amount) VALUES (?, ?, ?, ?, ?)",
                (datetime.utcnow(), trade_data['symbol'], trade_data['side'], trade_data['price'], trade_data['amount'])
            )

class MongoManager(BaseDB):
    def __init__(self):
        self.uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        self.db_name = os.getenv("MONGO_DB_NAME", "trading_bot")
        self.client = MongoClient(self.uri)
        self.db = self.client[self.db_name]

    def save_prediction(self, symbol, prediction, confidence):
        data = {
            "timestamp": datetime.utcnow(),
            "symbol": symbol,
            "prediction": prediction,
            "confidence": confidence
        }
        self.db.predictions.insert_one(data)
        print(f"[MongoDB] Predicción guardada: {prediction}")

    def save_trade(self, trade_data):
        trade_data["timestamp"] = datetime.utcnow()
        self.db.trades.insert_one(trade_data)

def get_db_manager():
    """Factory para obtener el manager según el entorno."""
    env = os.getenv("APP_ENV", "development").lower()
    if env == "production":
        return MongoManager()
    else:
        return SQLiteManager()
