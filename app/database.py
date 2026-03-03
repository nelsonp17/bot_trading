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
    def get_all_trades(self, run_script_id=None):
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

    @abstractmethod
    def get_run_script_by_id(self, run_script_id):
        pass

    @abstractmethod
    def save_run_script(self, run_script):
        pass


class SQLiteManager(BaseDB):
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(_PROJECT_ROOT, "db.db")
        self._create_tables()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _create_tables(self):
        with self._get_connection() as conn:
            # Tabla de run scripts
            conn.execute("""
                         CREATE TABLE IF NOT EXISTS run_scripts
                         (
                             id
                             TEXT
                             PRIMARY
                             KEY,
                             start_time
                             DATETIME,
                             updated_at
                             DATETIME,
                             name_script
                             TEXT,
                             initial_capital
                             REAL,
                             params
                             TEXT
                         )
                         """)

            # Tabla de predicciones
            conn.execute("""
                         CREATE TABLE IF NOT EXISTS predictions
                         (
                             id
                             INTEGER
                             PRIMARY
                             KEY
                             AUTOINCREMENT,
                             timestamp
                             DATETIME,
                             symbol
                             TEXT,
                             prediction
                             TEXT,
                             confidence
                             REAL,
                             reasoning
                             TEXT,
                             min_cushion
                             REAL,
                             max_cushion
                             REAL,
                             run_script_id
                             TEXT
                         )
                         """)

            # Tabla de trades
            conn.execute("""
                         CREATE TABLE IF NOT EXISTS trades
                         (
                             id
                             INTEGER
                             PRIMARY
                             KEY
                             AUTOINCREMENT,
                             timestamp
                             DATETIME,
                             symbol
                             TEXT,
                             side
                             TEXT,
                             price
                             REAL,
                             amount
                             REAL,
                             cost
                             REAL,
                             fee
                             REAL,
                             balance_before
                             REAL,
                             balance_after
                             REAL,
                             min_cushion
                             REAL,
                             max_cushion
                             REAL,
                             ia_confidence
                             REAL,
                             network
                             TEXT,
                             order_id
                             TEXT,
                             run_script_id
                             TEXT
                         )
                         """)
            # Tabla de escaneo de mercado
            conn.execute("""
                         CREATE TABLE IF NOT EXISTS market_scans
                         (
                             id
                             INTEGER
                             PRIMARY
                             KEY
                             AUTOINCREMENT,
                             scan_id
                             TEXT,
                             timestamp
                             DATETIME,
                             symbol
                             TEXT,
                             market_type
                             TEXT,
                             rank
                             INTEGER,
                             price
                             REAL,
                             change_24h_pct
                             REAL,
                             volume_24h
                             REAL,
                             expected_profit_pct
                             REAL,
                             expected_loss_pct
                             REAL,
                             volatility
                             TEXT,
                             recommended_strategy
                             TEXT,
                             recommended_timeframe
                             TEXT,
                             gas_fee_estimate
                             REAL,
                             reasoning
                             TEXT,
                             run_script_id
                             TEXT
                         )
                         """)
            # Tabla de planes de ejecución (El Contrato)
            conn.execute("""
                         CREATE TABLE IF NOT EXISTS execution_plans
                         (
                             id
                             INTEGER
                             PRIMARY
                             KEY
                             AUTOINCREMENT,
                             operation_id
                             TEXT
                             UNIQUE,
                             status
                             TEXT, -- WAITING_FOR_ENTRY, IN_POSITION, CLOSED, CANCELLED
                             symbol
                             TEXT,
                             strategy_type
                             TEXT,
                             timeframe
                             TEXT,
                             expiration_date
                             DATETIME,
                             entry_price
                             REAL,
                             exit_price
                             REAL,
                             execution_plan_json
                             TEXT,
                             metadata_json
                             TEXT,
                             timestamp
                             DATETIME,
                             run_script_id
                             TEXT
                         )
                         """)

            # Tabla de estado del sistema (Heartbeat)
            conn.execute("""
                         CREATE TABLE IF NOT EXISTS system_status
                         (
                             id
                             TEXT
                             PRIMARY
                             KEY,
                             last_heartbeat
                             DATETIME,
                             run_script_id
                             TEXT
                         )
                         """)

            # Migraciones manuales para asegurar que todas las tablas tengan run_script_id
            cols = {
                "predictions": ["run_script_id TEXT"],
                "market_scans": ["run_script_id TEXT", "scan_id TEXT", "market_type TEXT DEFAULT 'spot'", "price REAL",
                                 "change_24h_pct REAL", "volume_24h REAL"],
                "trades": ["run_script_id TEXT", "balance_before REAL", "balance_after REAL", "min_cushion REAL",
                           "max_cushion REAL", "ia_confidence REAL", "network TEXT", "order_id TEXT"],
                "execution_plans": ["run_script_id TEXT"],
                "system_status": ["run_script_id TEXT"]
            }
            for table, columns in cols.items():
                for col_def in columns:
                    col_name = col_def.split()[0]
                    try:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
                    except sqlite3.OperationalError:
                        pass  # Ya existe

    def save_prediction(self, symbol, prediction, confidence, reasoning, min_cushion=0, max_cushion=0,
                        run_script_id=None):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO predictions (timestamp, symbol, prediction, confidence, reasoning, min_cushion, max_cushion, run_script_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (datetime.utcnow(), symbol, prediction, confidence, reasoning, min_cushion, max_cushion, run_script_id)
            )

    def save_trade(self, trade_data, run_script_id=None):
        with self._get_connection() as conn:
            conn.execute("""
                         INSERT INTO trades (timestamp, symbol, side, price, amount, cost, fee,
                                             balance_before, balance_after, min_cushion, max_cushion,
                                             ia_confidence, network, order_id, run_script_id)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                         """, (
                             datetime.utcnow(),
                             trade_data['symbol'], trade_data['side'], trade_data['price'],
                             trade_data['amount'], trade_data.get('cost'), trade_data.get('fee'),
                             trade_data.get('balance_before'), trade_data.get('balance_after'),
                             trade_data.get('min_cushion', 0), trade_data.get('max_cushion', 0),
                             trade_data.get('ia_confidence'), trade_data.get('network'),
                             trade_data.get('order_id'), run_script_id
                         ))

    def get_last_trades(self, limit=5, run_script_id=None):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            if run_script_id:
                cursor = conn.execute("SELECT * FROM trades WHERE run_script_id = ? ORDER BY timestamp DESC LIMIT ?",
                                      (run_script_id, limit))
            else:
                cursor = conn.execute("SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_all_trades(self, run_script_id=None):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            if run_script_id:
                cursor = conn.execute("SELECT * FROM trades WHERE run_script_id = ?", (run_script_id,))
            else:
                cursor = conn.execute("SELECT * FROM trades")
            return [dict(row) for row in cursor.fetchall()]

    def get_last_predictions(self, limit=5, run_script_id=None):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            if run_script_id:
                cursor = conn.execute(
                    "SELECT * FROM predictions WHERE run_script_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (run_script_id, limit))
            else:
                cursor = conn.execute("SELECT * FROM predictions ORDER BY timestamp DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_active_position_cost(self, symbol, run_script_id=None):
        with self._get_connection() as conn:
            if run_script_id:
                cursor = conn.execute("""
                                      SELECT side, price, amount
                                      FROM trades
                                      WHERE symbol = ?
                                        AND run_script_id = ?
                                      ORDER BY timestamp DESC LIMIT 50
                                      """, (symbol, run_script_id))
            else:
                cursor = conn.execute("""
                                      SELECT side, price, amount
                                      FROM trades
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

    def save_market_scan(self, scan_data, run_script_id=None):
        with self._get_connection() as conn:
            conn.execute("""
                         INSERT INTO market_scans (scan_id, timestamp, symbol, market_type, rank, price, change_24h_pct,
                                                   volume_24h,
                                                   expected_profit_pct, expected_loss_pct,
                                                   volatility, recommended_strategy, recommended_timeframe,
                                                   gas_fee_estimate, reasoning, run_script_id)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                         """, (
                             scan_data.get('scan_id'),
                             datetime.utcnow(),
                             scan_data['symbol'], scan_data.get('market_type', 'spot'), scan_data['rank'],
                             scan_data.get('price'), scan_data.get('change_24h_pct'), scan_data.get('volume_24h'),
                             scan_data['expected_profit_pct'], scan_data['expected_loss_pct'],
                             scan_data['volatility'], scan_data['recommended_strategy'],
                             scan_data['recommended_timeframe'], scan_data['gas_fee_estimate'],
                             scan_data['reasoning'], run_script_id
                         ))

    def get_latest_market_recommendation(self, symbol, scan_id=None, run_script_id=None):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            if scan_id:
                cursor = conn.execute("""
                                      SELECT *
                                      FROM market_scans
                                      WHERE symbol = ?
                                        AND scan_id = ?
                                      ORDER BY timestamp DESC LIMIT 1
                                      """, (symbol, scan_id))
            elif run_script_id:
                cursor = conn.execute("""
                                      SELECT *
                                      FROM market_scans
                                      WHERE symbol = ?
                                        AND run_script_id = ?
                                      ORDER BY timestamp DESC LIMIT 1
                                      """, (symbol, run_script_id))
            else:
                cursor = conn.execute("""
                                      SELECT *
                                      FROM market_scans
                                      WHERE symbol = ?
                                      ORDER BY timestamp DESC LIMIT 1
                                      """, (symbol,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def save_execution_plan(self, plan_data, run_script_id=None):
        import json
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO execution_plans (
                    operation_id, status, symbol, strategy_type, timeframe, 
                    expiration_date, execution_plan_json, metadata_json, timestamp, run_script_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan_data['operation_id'],
                plan_data['status'],
                plan_data['pair'],
                plan_data.get('strategy_type'),
                plan_data.get('timeframe_ref'),
                plan_data.get('expiration_date'),
                json.dumps(plan_data['execution_plan']),
                json.dumps(plan_data.get('metadata', {})),
                datetime.utcnow(),
                run_script_id
            ))

    def get_active_plan(self, symbol, run_script_id=None):
        import json
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            if run_script_id:
                cursor = conn.execute("""
                                      SELECT *
                                      FROM execution_plans
                                      WHERE symbol = ?
                                        AND status IN ('WAITING_FOR_ENTRY', 'IN_POSITION')
                                        AND run_script_id = ?
                                      ORDER BY timestamp DESC LIMIT 1
                                      """, (symbol, run_script_id))
            else:
                cursor = conn.execute("""
                                      SELECT *
                                      FROM execution_plans
                                      WHERE symbol = ?
                                        AND status IN ('WAITING_FOR_ENTRY', 'IN_POSITION')
                                      ORDER BY timestamp DESC LIMIT 1
                                      """, (symbol,))
            row = cursor.fetchone()
            if row:
                res = dict(row)
                res['execution_plan'] = json.loads(res['execution_plan_json'])
                res['metadata'] = json.loads(res['metadata_json'])
                return res
            return None

    def update_plan_status(self, operation_id, status, entry_price=None, exit_price=None, run_script_id=None):
        with self._get_connection() as conn:
            query_suffix = " AND run_script_id = ?" if run_script_id else ""
            params_suffix = (run_script_id,) if run_script_id else ()

            if entry_price:
                conn.execute(
                    f"UPDATE execution_plans SET status = ?, entry_price = ? WHERE operation_id = ?{query_suffix}",
                    (status, entry_price, operation_id) + params_suffix)
            elif exit_price:
                conn.execute(
                    f"UPDATE execution_plans SET status = ?, exit_price = ? WHERE operation_id = ?{query_suffix}",
                    (status, exit_price, operation_id) + params_suffix)
            else:
                conn.execute(f"UPDATE execution_plans SET status = ? WHERE operation_id = ?{query_suffix}",
                             (status, operation_id) + params_suffix)

    def save_heartbeat(self, bot_id, run_script_id=None):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO system_status (id, last_heartbeat, run_script_id) 
                VALUES (?, ?, ?)
            """, (bot_id, datetime.utcnow(), run_script_id))

    def get_last_heartbeat(self, bot_id, run_script_id=None):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            if run_script_id:
                cursor = conn.execute("SELECT last_heartbeat FROM system_status WHERE id = ? AND run_script_id = ?",
                                      (bot_id, run_script_id))
            else:
                cursor = conn.execute("SELECT last_heartbeat FROM system_status WHERE id = ?", (bot_id,))
            row = cursor.fetchone()
            if row:
                ts = row['last_heartbeat']
                return datetime.strptime(ts.split('.')[0], '%Y-%m-%d %H:%M:%S') if isinstance(ts, str) else ts
            return None

    def get_run_script_by_id(self, run_script_id):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM run_scripts WHERE id = ?", (run_script_id,))
            row = cursor.fetchone()
            if row:
                res = dict(row)
                res['params'] = json.loads(res['params']) if res['params'] else {}
                return res
            return None

    def save_run_script(self, run_data):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO run_scripts (id, start_time, updated_at, name_script, initial_capital, params) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                run_data['id'],
                run_data.get('start_time', datetime.utcnow()),
                datetime.utcnow(),
                run_data['name_script'],
                run_data.get('initial_capital', 0.0),
                json.dumps(run_data.get('params', {}))
            ))


class MongoManager(BaseDB):
    def __init__(self):
        self.uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        self.db_name = os.getenv("MONGO_DB_NAME", "trading_bot")
        self.client = MongoClient(self.uri)
        self.db = self.client[self.db_name]

    def save_prediction(self, symbol, prediction, confidence, reasoning, min_cushion=0, max_cushion=0,
                        run_script_id=None):
        data = {"timestamp": datetime.utcnow(), "symbol": symbol, "prediction": prediction, "confidence": confidence,
                "reasoning": reasoning, "min_cushion": min_cushion, "max_cushion": max_cushion,
                "run_script_id": run_script_id}
        self.db.predictions.insert_one(data)

    def save_trade(self, trade_data, run_script_id=None):
        trade_data["timestamp"] = datetime.utcnow()
        trade_data["run_script_id"] = run_script_id
        self.db.trades.insert_one(trade_data)

    def get_last_trades(self, limit=5, run_script_id=None):
        query = {}
        if run_script_id: query["run_script_id"] = run_script_id
        return list(self.db.trades.find(query).sort("timestamp", -1).limit(limit))

    def get_all_trades(self, run_script_id=None):
        query = {}
        if run_script_id: query["run_script_id"] = run_script_id
        return list(self.db.trades.find(query))

    def get_last_predictions(self, limit=5, run_script_id=None):
        query = {}
        if run_script_id: query["run_script_id"] = run_script_id
        return list(self.db.predictions.find(query).sort("timestamp", -1).limit(limit))

    def get_active_position_cost(self, symbol, run_script_id=None):
        query = {"symbol": symbol}
        if run_script_id: query["run_script_id"] = run_script_id
        trades = list(self.db.trades.find(query).sort("timestamp", -1).limit(50))
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

    def save_market_scan(self, scan_data, run_script_id=None):
        scan_data["timestamp"] = datetime.utcnow()
        scan_data["run_script_id"] = run_script_id
        self.db.market_scans.insert_one(scan_data)

    def get_latest_market_recommendation(self, symbol, scan_id=None, run_script_id=None):
        query = {"symbol": symbol}
        if scan_id: query["scan_id"] = scan_id
        if run_script_id: query["run_script_id"] = run_script_id
        return self.db.market_scans.find_one(query, sort=[("timestamp", -1)])

    def save_execution_plan(self, plan_data, run_script_id=None):
        plan_data["timestamp"] = datetime.utcnow()
        plan_data["run_script_id"] = run_script_id
        self.db.execution_plans.replace_one({"operation_id": plan_data["operation_id"]}, plan_data, upsert=True)

    def get_active_plan(self, symbol, run_script_id=None):
        query = {"symbol": symbol, "status": {"$in": ["WAITING_FOR_ENTRY", "IN_POSITION"]}}
        if run_script_id: query["run_script_id"] = run_script_id
        return self.db.execution_plans.find_one(query, sort=[("timestamp", -1)])

    def update_plan_status(self, operation_id, status, entry_price=None, exit_price=None, run_script_id=None):
        update = {"$set": {"status": status}}
        if entry_price: update["$set"]["entry_price"] = entry_price
        if exit_price: update["$set"]["exit_price"] = exit_price
        self.db.execution_plans.update_one({"operation_id": operation_id}, update)

    def save_heartbeat(self, bot_id, run_script_id=None):
        self.db.system_status.replace_one({"id": bot_id}, {"id": bot_id, "last_heartbeat": datetime.utcnow(),
                                                           "run_script_id": run_script_id}, upsert=True)

    def get_last_heartbeat(self, bot_id, run_script_id=None):
        doc = self.db.system_status.find_one({"id": bot_id})
        return doc["last_heartbeat"] if doc else None

    def get_run_script_by_id(self, run_script_id):
        return self.db.run_scripts.find_one({"id": run_script_id})

    def save_run_script(self, run_script):
        self.db.run_scripts.replace_one({"id": run_script["id"]}, run_script, upsert=True)


def get_db_manager():
    env = os.getenv("APP_ENV", "development").lower()
    if env == "production":
        return MongoManager()
    else:
        return SQLiteManager()
