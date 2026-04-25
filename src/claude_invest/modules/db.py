import sqlite3
from datetime import datetime, timedelta, timezone


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def initialize(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                qty REAL NOT NULL,
                price REAL NOT NULL,
                timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                order_id TEXT,
                trade_type TEXT,
                status TEXT
            );

            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                qty REAL NOT NULL,
                entry_price REAL NOT NULL,
                entry_time TEXT NOT NULL DEFAULT (datetime('now')),
                current_stop REAL,
                trailing_stop REAL,
                status TEXT DEFAULT 'open'
            );

            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                sentiment_score REAL,
                rsi REAL,
                macd REAL,
                volume_ratio REAL,
                trend TEXT
            );

            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                ticker TEXT NOT NULL,
                action TEXT NOT NULL,
                reasoning TEXT,
                signals_snapshot TEXT
            );

            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                total_value REAL NOT NULL,
                cash REAL NOT NULL,
                positions_value REAL NOT NULL,
                daily_pnl REAL
            );

            CREATE TABLE IF NOT EXISTS discovery_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                ticker TEXT NOT NULL,
                volume_score REAL,
                news_score REAL,
                sentiment REAL,
                action_taken TEXT
            );

            CREATE TABLE IF NOT EXISTS pdt_tracker (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT NOT NULL,
                date TEXT NOT NULL DEFAULT (date('now'))
            );

            CREATE TABLE IF NOT EXISTS change_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                parameter_path TEXT NOT NULL,
                old_value TEXT NOT NULL,
                new_value TEXT NOT NULL,
                reason TEXT NOT NULL,
                trade_count INTEGER NOT NULL,
                auto_applied BOOLEAN NOT NULL DEFAULT 0,
                reverted BOOLEAN DEFAULT 0,
                reverted_at TEXT,
                revert_reason TEXT
            );
        """)
        for table in ("decisions", "trades"):
            cursor = conn.execute(f"PRAGMA table_info({table})")
            columns = {row[1] for row in cursor.fetchall()}
            if "position_id" not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN position_id TEXT")
        conn.commit()

    def list_tables(self) -> list[str]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        return [row["name"] for row in cursor.fetchall()]

    def insert_trade(self, trade: dict):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO trades (symbol, side, qty, price, order_id, trade_type, status, position_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (trade["symbol"], trade["side"], trade["qty"], trade["price"],
             trade.get("order_id"), trade.get("trade_type"), trade.get("status"),
             trade.get("position_id")),
        )
        conn.commit()

    def get_trades(self, symbol: str | None = None, limit: int = 100) -> list[dict]:
        conn = self._get_conn()
        if symbol:
            cursor = conn.execute(
                "SELECT * FROM trades WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?",
                (symbol, limit),
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,)
            )
        return [dict(row) for row in cursor.fetchall()]

    def insert_decision(self, decision: dict):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO decisions (ticker, action, reasoning, signals_snapshot, position_id) VALUES (?, ?, ?, ?, ?)",
            (decision["ticker"], decision["action"],
             decision.get("reasoning"), decision.get("signals_snapshot"),
             decision.get("position_id")),
        )
        conn.commit()

    def get_decisions(self, limit: int = 50) -> list[dict]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM decisions ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def insert_portfolio_snapshot(self, snapshot: dict):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO portfolio_snapshots (total_value, cash, positions_value, daily_pnl) VALUES (?, ?, ?, ?)",
            (snapshot["total_value"], snapshot["cash"],
             snapshot["positions_value"], snapshot.get("daily_pnl")),
        )
        conn.commit()

    def get_portfolio_snapshots(self, limit: int = 100) -> list[dict]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def insert_signal(self, signal: dict):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO signals (ticker, sentiment_score, rsi, macd, volume_ratio, trend) VALUES (?, ?, ?, ?, ?, ?)",
            (signal["ticker"], signal.get("sentiment_score"), signal.get("rsi"),
             signal.get("macd"), signal.get("volume_ratio"), signal.get("trend")),
        )
        conn.commit()

    def get_signals(self, ticker: str, limit: int = 50) -> list[dict]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM signals WHERE ticker = ? ORDER BY timestamp DESC LIMIT ?",
            (ticker, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def insert_discovery(self, entry: dict):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO discovery_log (ticker, volume_score, news_score, sentiment, action_taken) VALUES (?, ?, ?, ?, ?)",
            (entry["ticker"], entry.get("volume_score"), entry.get("news_score"),
             entry.get("sentiment"), entry.get("action_taken")),
        )
        conn.commit()

    def get_discovery_log(self, limit: int = 50) -> list[dict]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM discovery_log ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def record_day_trade(self, trade_id: str):
        conn = self._get_conn()
        conn.execute("INSERT INTO pdt_tracker (trade_id) VALUES (?)", (trade_id,))
        conn.commit()

    def get_day_trade_count(self, days: int = 5) -> int:
        conn = self._get_conn()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        cursor = conn.execute(
            "SELECT COUNT(*) as cnt FROM pdt_tracker WHERE date >= ?", (cutoff,)
        )
        return cursor.fetchone()["cnt"]

    def insert_change_log(self, entry: dict):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO change_log (parameter_path, old_value, new_value, reason, trade_count, auto_applied) VALUES (?, ?, ?, ?, ?, ?)",
            (entry["parameter_path"], entry["old_value"], entry["new_value"],
             entry["reason"], entry["trade_count"], entry.get("auto_applied", False)),
        )
        conn.commit()

    def get_change_log(self, limit: int = 50) -> list[dict]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM change_log ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def revert_change(self, change_id: int, reason: str):
        conn = self._get_conn()
        conn.execute(
            "UPDATE change_log SET reverted=1, reverted_at=datetime('now'), revert_reason=? WHERE id=?",
            (reason, change_id),
        )
        conn.commit()

    def get_active_changes(self) -> list[dict]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM change_log WHERE auto_applied=1 AND reverted=0 ORDER BY timestamp DESC"
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_matched_trades(self) -> list[dict]:
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT
                b.position_id,
                b.ticker,
                b.timestamp as entry_time,
                b.signals_snapshot as entry_signals,
                b.reasoning as entry_reasoning,
                s.timestamp as exit_time,
                s.signals_snapshot as exit_signals,
                s.reasoning as exit_reasoning,
                bt.price as entry_price,
                bt.trade_type as strategy_id,
                st.price as exit_price
            FROM decisions b
            JOIN decisions s ON b.position_id = s.position_id AND s.action = 'sell'
            LEFT JOIN trades bt ON b.position_id = bt.position_id AND bt.side = 'buy'
            LEFT JOIN trades st ON s.position_id = st.position_id AND st.side = 'sell'
            WHERE b.action = 'buy'
              AND b.position_id IS NOT NULL
              AND bt.price IS NOT NULL AND st.price IS NOT NULL
            ORDER BY b.timestamp DESC
        """)
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
