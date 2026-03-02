import os
import sqlite3
from abc import ABC, abstractmethod
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Ruta absoluta a la raíz del proyecto (un nivel arriba de /app)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class BaseDB(ABC):
    """Interfaz base para persistencia."""

    @abstractmethod
    def save_prediction(self, symbol, prediction, confidence, reasoning, min_cushion=0, max_cushion=0):
        pass

    @abstractmethod
    def save_trade(self, trade_data):
        pass

    @abstractmethod
    def get_last_trades(self, limit=5):
        pass

    @abstractmethod
    def get_last_predictions(self, limit=5):
        pass

    @abstractmethod
    def get_active_position_cost(self, symbol):
        pass

    @abstractmethod
    def save_market_scan(self, scan_data):
        pass

    @abstractmethod
    def get_latest_market_recommendation(self, symbol, scan_id=None):
        pass

    @abstractmethod
    def save_execution_plan(self, plan_data):
        pass

    @abstractmethod
    def get_active_plan(self, symbol):
        pass

    @abstractmethod
    def update_plan_status(self, operation_id, status, entry_price=None, exit_price=None):
        pass

    @abstractmethod
    def save_heartbeat(self, bot_id):
        pass

    @abstractmethod
    def get_last_heartbeat(self, bot_id):
        pass


class SQLiteManager(BaseDB):
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(_PROJECT_ROOT, "db.db")
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
            # Tabla de escaneo de mercado
            conn.execute("""
                CREATE TABLE IF NOT EXISTS market_scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_id TEXT,
                    timestamp DATETIME,
                    symbol TEXT,
                    market_type TEXT,
                    rank INTEGER,
                    price REAL,
                    change_24h_pct REAL,
                    volume_24h REAL,
                    expected_profit_pct REAL,
                    expected_loss_pct REAL,
                    volatility TEXT,
                    recommended_strategy TEXT,
                    recommended_timeframe TEXT,
                    gas_fee_estimate REAL,
                    reasoning TEXT
                )
            """)
            # Tabla de planes de ejecución (El Contrato)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS execution_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_id TEXT UNIQUE,
                    status TEXT, -- WAITING_FOR_ENTRY, IN_POSITION, CLOSED, CANCELLED
                    symbol TEXT,
                    strategy_type TEXT,
                    timeframe TEXT,
                    expiration_date DATETIME,
                    entry_price REAL,
                    exit_price REAL,
                    execution_plan_json TEXT,
                    metadata_json TEXT,
                    timestamp DATETIME
                )
            """)

            # Tabla de estado del sistema (Heartbeat)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_status (
                    id TEXT PRIMARY KEY,
                    last_heartbeat DATETIME
                )
            """)
            
            # Migraciones manuales para columnas nuevas en tablas existentes
            cols = {
                "market_scans": ["scan_id TEXT", "market_type TEXT DEFAULT 'spot'", "price REAL", "change_24h_pct REAL", "volume_24h REAL"],
                "trades": ["balance_before REAL", "balance_after REAL", "min_cushion REAL", "max_cushion REAL", "ia_confidence REAL", "network TEXT", "order_id TEXT"]
            }
            for table, columns in cols.items():
                for col_def in columns:
                    col_name = col_def.split()[0]
                    try:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
                    except sqlite3.OperationalError:
                        pass # Ya existe

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
                trade_data.get('min_cushion', 0), trade_data.get('max_cushion', 0),
                trade_data.get('ia_confidence'), trade_data.get('network'),
                trade_data.get('order_id')
            ))

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
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT side, price, amount FROM trades 
                WHERE symbol = ? 
                ORDER BY timestamp DESC LIMIT 50
            """, (symbol,))
            trades = cursor.fetchall()
            total_amount = 0
            total_cost = 0
            for side, price, amount in trades:
                if side == "COMPRA":
                    total_amount += amount
                    total_cost += (price * amount)
                elif side == "VENTA":
                    total_amount -= amount
                    if total_amount <= 0: break
            return total_cost / total_amount if total_amount > 0 else 0

    def save_market_scan(self, scan_data):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO market_scans (
                    scan_id, timestamp, symbol, market_type, rank, price, change_24h_pct, volume_24h,
                    expected_profit_pct, expected_loss_pct, 
                    volatility, recommended_strategy, recommended_timeframe, 
                    gas_fee_estimate, reasoning
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                scan_data.get('scan_id'),
                datetime.utcnow(),
                scan_data['symbol'], scan_data.get('market_type', 'spot'), scan_data['rank'],
                scan_data.get('price'), scan_data.get('change_24h_pct'), scan_data.get('volume_24h'),
                scan_data['expected_profit_pct'], scan_data['expected_loss_pct'],
                scan_data['volatility'], scan_data['recommended_strategy'],
                scan_data['recommended_timeframe'], scan_data['gas_fee_estimate'],
                scan_data['reasoning']
            ))

    def get_latest_market_recommendation(self, symbol, scan_id=None):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            if scan_id:
                cursor = conn.execute("""
                    SELECT * FROM market_scans 
                    WHERE symbol = ? AND scan_id = ?
                    ORDER BY timestamp DESC LIMIT 1
                """, (symbol, scan_id))
            else:
                cursor = conn.execute("""
                    SELECT * FROM market_scans 
                    WHERE symbol = ? 
                    ORDER BY timestamp DESC LIMIT 1
                """, (symbol,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def save_execution_plan(self, plan_data):
        import json
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO execution_plans (
                    operation_id, status, symbol, strategy_type, timeframe, 
                    expiration_date, execution_plan_json, metadata_json, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan_data['operation_id'],
                plan_data['status'],
                plan_data['pair'],
                plan_data.get('strategy_type'),
                plan_data.get('timeframe_ref'),
                plan_data.get('expiration_date'),
                json.dumps(plan_data['execution_plan']),
                json.dumps(plan_data.get('metadata', {})),
                datetime.utcnow()
            ))

    def get_active_plan(self, symbol):
        import json
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM execution_plans 
                WHERE symbol = ? AND status IN ('WAITING_FOR_ENTRY', 'IN_POSITION')
                ORDER BY timestamp DESC LIMIT 1
            """, (symbol,))
            row = cursor.fetchone()
            if row:
                res = dict(row)
                res['execution_plan'] = json.loads(res['execution_plan_json'])
                res['metadata'] = json.loads(res['metadata_json'])
                return res
            return None

    def update_plan_status(self, operation_id, status, entry_price=None, exit_price=None):
        with self._get_connection() as conn:
            if entry_price:
                conn.execute("UPDATE execution_plans SET status = ?, entry_price = ? WHERE operation_id = ?", (status, entry_price, operation_id))
            elif exit_price:
                conn.execute("UPDATE execution_plans SET status = ?, exit_price = ? WHERE operation_id = ?", (status, exit_price, operation_id))
            else:
                conn.execute("UPDATE execution_plans SET status = ? WHERE operation_id = ?", (status, operation_id))

    def save_heartbeat(self, bot_id):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO system_status (id, last_heartbeat) 
                VALUES (?, ?)
            """, (bot_id, datetime.utcnow()))

    def get_last_heartbeat(self, bot_id):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT last_heartbeat FROM system_status WHERE id = ?", (bot_id,))
            row = cursor.fetchone()
            if row:
                ts = row['last_heartbeat']
                return datetime.strptime(ts.split('.')[0], '%Y-%m-%d %H:%M:%S') if isinstance(ts, str) else ts
            return None


class MongoManager(BaseDB):
    def __init__(self):
        self.uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        self.db_name = os.getenv("MONGO_DB_NAME", "trading_bot")
        self.client = MongoClient(self.uri)
        self.db = self.client[self.db_name]

    def save_prediction(self, symbol, prediction, confidence, reasoning, min_cushion=0, max_cushion=0):
        data = {"timestamp": datetime.utcnow(), "symbol": symbol, "prediction": prediction, "confidence": confidence, "reasoning": reasoning, "min_cushion": min_cushion, "max_cushion": max_cushion}
        self.db.predictions.insert_one(data)

    def save_trade(self, trade_data):
        trade_data["timestamp"] = datetime.utcnow()
        self.db.trades.insert_one(trade_data)

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

    def save_market_scan(self, scan_data):
        scan_data["timestamp"] = datetime.utcnow()
        self.db.market_scans.insert_one(scan_data)

    def get_latest_market_recommendation(self, symbol, scan_id=None):
        query = {"symbol": symbol}
        if scan_id: query["scan_id"] = scan_id
        return self.db.market_scans.find_one(query, sort=[("timestamp", -1)])

    def save_execution_plan(self, plan_data):
        plan_data["timestamp"] = datetime.utcnow()
        self.db.execution_plans.replace_one({"operation_id": plan_data["operation_id"]}, plan_data, upsert=True)

    def get_active_plan(self, symbol):
        return self.db.execution_plans.find_one({"symbol": symbol, "status": {"$in": ["WAITING_FOR_ENTRY", "IN_POSITION"]}}, sort=[("timestamp", -1)])

    def update_plan_status(self, operation_id, status, entry_price=None, exit_price=None):
        update = {"$set": {"status": status}}
        if entry_price: update["$set"]["entry_price"] = entry_price
        if exit_price: update["$set"]["exit_price"] = exit_price
        self.db.execution_plans.update_one({"operation_id": operation_id}, update)

    def save_heartbeat(self, bot_id):
        self.db.system_status.replace_one({"id": bot_id}, {"id": bot_id, "last_heartbeat": datetime.utcnow()}, upsert=True)

    def get_last_heartbeat(self, bot_id):
        doc = self.db.system_status.find_one({"id": bot_id})
        return doc["last_heartbeat"] if doc else None


def get_db_manager():
    env = os.getenv("APP_ENV", "development").lower()
    if env == "production":
        return MongoManager()
    else:
        return SQLiteManager()
