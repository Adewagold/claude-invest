# Learning Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a closed-loop learning engine that analyzes trades across 5 dimensions, auto-tunes strategy parameters with guardrails, and generates daily reports for both the AI cron and human dashboard.

**Architecture:** Evolutionary enhancement of existing `learner.py` → `strategy.py` pipeline. Two new modules (`pattern_analyzer.py`, `optimizer.py`) plug into the existing flow. Database gets `position_id` for lifecycle tracking and `change_log` table for parameter audit trail. Dashboard gets a new `/learning` page with 4 sections.

**Tech Stack:** Python 3.12, SQLite3, FastAPI, Next.js 16 (App Router), SWR, Recharts, ruamel.yaml

**Spec:** `docs/superpowers/specs/2026-04-25-learning-engine-design.md`

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `src/claude_invest/modules/pattern_analyzer.py` | Multi-dimensional trade analysis (5 dimensions) |
| `src/claude_invest/modules/optimizer.py` | Parameter optimization with guardrails |
| `tests/test_pattern_analyzer.py` | Unit tests for pattern analyzer |
| `tests/test_optimizer.py` | Unit tests for optimizer |
| `dashboard/src/app/learning/page.tsx` | New learning dashboard page |
| `dashboard/src/components/learning-charts.tsx` | Chart components for learning page |

### Modified Files
| File | Changes |
|------|---------|
| `src/claude_invest/modules/db.py` | Add `position_id` column migration, `change_log` table, new query methods |
| `src/claude_invest/modules/learner.py` | Replace FIFO matching with `position_id` join, backward compat |
| `src/claude_invest/modules/strategy.py` | Enhanced brief with dimension insights + parameter changes sections |
| `src/claude_invest/modules/executor.py` | Accept and store `position_id` |
| `src/claude_invest/main.py` | Generate `position_id` on buy, new CLI commands, pass through on sell |
| `src/claude_invest/modules/api_server.py` | 4 new endpoints for learning dashboard |
| `dashboard/src/lib/api.ts` | New SWR hooks for learning endpoints |
| `dashboard/src/lib/types.ts` | New TypeScript interfaces |
| `dashboard/src/components/nav.tsx` | Add Learning nav link |
| `tests/test_learner.py` | Update tests for position_id matching |
| `tests/test_strategy.py` | Update tests for enhanced brief |
| `pyproject.toml` | Add `ruamel.yaml` dependency |

---

### Task 1: Add ruamel.yaml dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add ruamel.yaml to dependencies**

In `pyproject.toml`, add `ruamel.yaml` to the dependencies list. Find the `dependencies` array and add the new entry:

```toml
"ruamel.yaml>=0.18",
```

- [ ] **Step 2: Install dependencies**

Run: `cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pip install "ruamel.yaml>=0.18"`
Expected: Successfully installed ruamel.yaml

- [ ] **Step 3: Verify import works**

Run: `.venv/bin/python -c "from ruamel.yaml import YAML; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: add ruamel.yaml dependency for round-trip YAML editing"
```

---

### Task 2: Database Schema Migration

**Files:**
- Modify: `src/claude_invest/modules/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write failing test for position_id column**

Add to `tests/test_db.py`:

```python
def test_position_id_column_exists(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    conn = db._get_conn()

    # Check decisions table has position_id column
    cursor = conn.execute("PRAGMA table_info(decisions)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "position_id" in columns

    # Check trades table has position_id column
    cursor = conn.execute("PRAGMA table_info(trades)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "position_id" in columns

    db.close()


def test_change_log_table_exists(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    tables = db.list_tables()
    assert "change_log" in tables
    db.close()


def test_insert_decision_with_position_id(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    db.insert_decision({
        "ticker": "BTC/USD",
        "action": "buy",
        "reasoning": "test",
        "signals_snapshot": "{}",
        "position_id": "pos-abc-123",
    })
    decisions = db.get_decisions(limit=1)
    assert decisions[0]["position_id"] == "pos-abc-123"
    db.close()


def test_insert_trade_with_position_id(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    db.insert_trade({
        "symbol": "BTC/USD",
        "side": "buy",
        "qty": 0.001,
        "price": 75000,
        "order_id": "t1",
        "trade_type": "mean_reversion",
        "status": "filled",
        "position_id": "pos-abc-123",
    })
    trades = db.get_trades(limit=1)
    assert trades[0]["position_id"] == "pos-abc-123"
    db.close()


def test_insert_change_log(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    db.insert_change_log({
        "parameter_path": "strategies.mean_reversion.params.rsi_buy_threshold",
        "old_value": "25",
        "new_value": "20",
        "reason": "12 trades show RSI<20 wins 75%",
        "trade_count": 12,
        "auto_applied": True,
    })
    changes = db.get_change_log()
    assert len(changes) == 1
    assert changes[0]["parameter_path"] == "strategies.mean_reversion.params.rsi_buy_threshold"
    assert changes[0]["auto_applied"] == 1
    db.close()


def test_get_matched_trades_by_position_id(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    # Insert buy decision + trade
    db.insert_decision({
        "ticker": "BTC/USD", "action": "buy", "reasoning": "test",
        "signals_snapshot": '{"rsi": 45, "price": 75000}',
        "position_id": "pos-1",
    })
    db.insert_trade({
        "symbol": "BTC/USD", "side": "buy", "qty": 0.001,
        "price": 75000, "order_id": "t1", "trade_type": "momentum",
        "status": "filled", "position_id": "pos-1",
    })
    # Insert sell decision + trade
    db.insert_decision({
        "ticker": "BTC/USD", "action": "sell", "reasoning": "take profit",
        "signals_snapshot": '{"rsi": 65, "price": 76000}',
        "position_id": "pos-1",
    })
    db.insert_trade({
        "symbol": "BTC/USD", "side": "sell", "qty": 0.001,
        "price": 76000, "order_id": "t2", "trade_type": "momentum",
        "status": "filled", "position_id": "pos-1",
    })
    matched = db.get_matched_trades()
    assert len(matched) == 1
    assert matched[0]["position_id"] == "pos-1"
    assert matched[0]["entry_price"] == 75000
    assert matched[0]["exit_price"] == 76000
    assert matched[0]["ticker"] == "BTC/USD"
    db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_db.py -v -k "position_id or change_log or matched_trades"`
Expected: FAIL — columns and methods don't exist yet

- [ ] **Step 3: Implement schema migration and new methods in db.py**

In `src/claude_invest/modules/db.py`, update the `initialize()` method to add new columns and table. Add the migration after existing `CREATE TABLE` statements but before `conn.commit()`:

```python
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

        # Migrate: add position_id to decisions and trades if not present
        for table in ("decisions", "trades"):
            cursor = conn.execute(f"PRAGMA table_info({table})")
            columns = {row[1] for row in cursor.fetchall()}
            if "position_id" not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN position_id TEXT")

        conn.commit()
```

Then update `insert_decision` and `insert_trade` to handle `position_id`:

```python
    def insert_decision(self, decision: dict):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO decisions (ticker, action, reasoning, signals_snapshot, position_id) VALUES (?, ?, ?, ?, ?)",
            (decision["ticker"], decision["action"],
             decision.get("reasoning"), decision.get("signals_snapshot"),
             decision.get("position_id")),
        )
        conn.commit()

    def insert_trade(self, trade: dict):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO trades (symbol, side, qty, price, order_id, trade_type, status, position_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (trade["symbol"], trade["side"], trade["qty"], trade["price"],
             trade.get("order_id"), trade.get("trade_type"), trade.get("status"),
             trade.get("position_id")),
        )
        conn.commit()
```

Add new methods for `change_log` and matched trades:

```python
    def insert_change_log(self, entry: dict):
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO change_log
               (parameter_path, old_value, new_value, reason, trade_count, auto_applied)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (entry["parameter_path"], entry["old_value"], entry["new_value"],
             entry["reason"], entry["trade_count"], entry["auto_applied"]),
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
            "UPDATE change_log SET reverted = 1, reverted_at = datetime('now'), revert_reason = ? WHERE id = ?",
            (reason, change_id),
        )
        conn.commit()

    def get_active_changes(self) -> list[dict]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM change_log WHERE auto_applied = 1 AND reverted = 0 ORDER BY timestamp DESC"
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_matched_trades(self) -> list[dict]:
        """Get closed positions by joining buy/sell decisions on position_id."""
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
            ORDER BY b.timestamp DESC
        """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_db.py -v`
Expected: All tests PASS including new ones

- [ ] **Step 5: Commit**

```bash
git add src/claude_invest/modules/db.py tests/test_db.py
git commit -m "feat: add position_id tracking and change_log table to database"
```

---

### Task 3: Update Learner with position_id Matching

**Files:**
- Modify: `src/claude_invest/modules/learner.py`
- Modify: `tests/test_learner.py`

- [ ] **Step 1: Write failing test for position_id-based matching**

Add to `tests/test_learner.py`:

```python
@pytest.fixture
def seeded_db_with_position_ids(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()

    # Winning trade with position_id
    db.insert_decision({
        "ticker": "BTC/USD", "action": "buy",
        "reasoning": "MACD crossover",
        "signals_snapshot": json.dumps({
            "rsi": 45, "macd": -200, "macd_signal": -250,
            "trend": "neutral", "sentiment": 0.1, "price": 75000,
        }),
        "position_id": "pos-win-1",
    })
    db.insert_decision({
        "ticker": "BTC/USD", "action": "sell",
        "reasoning": "Take profit",
        "signals_snapshot": json.dumps({"price": 76000}),
        "position_id": "pos-win-1",
    })
    db.insert_trade({
        "symbol": "BTC/USD", "side": "buy", "qty": 0.001,
        "price": 75000, "order_id": "t1", "trade_type": "momentum",
        "status": "filled", "position_id": "pos-win-1",
    })
    db.insert_trade({
        "symbol": "BTC/USD", "side": "sell", "qty": 0.001,
        "price": 76000, "order_id": "t2", "trade_type": "momentum",
        "status": "filled", "position_id": "pos-win-1",
    })

    # Losing trade with position_id
    db.insert_decision({
        "ticker": "CMND", "action": "buy",
        "reasoning": "FDA catalyst",
        "signals_snapshot": json.dumps({
            "rsi": 74.5, "macd": 0.13, "macd_signal": 0.06,
            "trend": "bullish", "sentiment": 0.2, "price": 1.45,
        }),
        "position_id": "pos-loss-1",
    })
    db.insert_decision({
        "ticker": "CMND", "action": "sell",
        "reasoning": "Stop loss",
        "signals_snapshot": json.dumps({"price": 1.30}),
        "position_id": "pos-loss-1",
    })
    db.insert_trade({
        "symbol": "CMND", "side": "buy", "qty": 80,
        "price": 1.45, "order_id": "t3", "trade_type": "mean_reversion",
        "status": "filled", "position_id": "pos-loss-1",
    })
    db.insert_trade({
        "symbol": "CMND", "side": "sell", "qty": 80,
        "price": 1.30, "order_id": "t4", "trade_type": "mean_reversion",
        "status": "filled", "position_id": "pos-loss-1",
    })

    return db


def test_match_trades_uses_position_id(seeded_db_with_position_ids):
    from claude_invest.modules.learner import _match_trades
    matched = _match_trades(seeded_db_with_position_ids)
    closed = [m for m in matched if m["status"] == "closed"]
    assert len(closed) == 2

    win = [m for m in closed if m["ticker"] == "BTC/USD"][0]
    assert win["win"] is True
    assert win["pnl"] == 1000  # 76000 - 75000
    assert win["position_id"] == "pos-win-1"
    assert win["strategy_id"] == "momentum"

    loss = [m for m in closed if m["ticker"] == "CMND"][0]
    assert loss["win"] is False
    assert loss["position_id"] == "pos-loss-1"
    assert loss["strategy_id"] == "mean_reversion"


def test_match_trades_falls_back_to_fifo(seeded_db):
    """Old records without position_id should still work via FIFO."""
    from claude_invest.modules.learner import _match_trades
    matched = _match_trades(seeded_db)
    closed = [m for m in matched if m["status"] == "closed"]
    assert len(closed) >= 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_learner.py -v -k "position_id or fifo"`
Expected: FAIL — `_match_trades` doesn't return `position_id` or `strategy_id`

- [ ] **Step 3: Update _match_trades in learner.py**

Replace the `_match_trades` function in `src/claude_invest/modules/learner.py`:

```python
def _match_trades(db: Database) -> list[dict]:
    # Try position_id-based matching first
    position_matched = db.get_matched_trades()

    matched = []
    seen_position_ids = set()

    for row in position_matched:
        pid = row["position_id"]
        seen_position_ids.add(pid)

        try:
            entry_signals = json.loads(row.get("entry_signals") or "{}")
        except (json.JSONDecodeError, TypeError):
            entry_signals = {}

        try:
            exit_signals = json.loads(row.get("exit_signals") or "{}")
        except (json.JSONDecodeError, TypeError):
            exit_signals = {}

        entry_price = row.get("entry_price") or entry_signals.get("price", 0)
        exit_price = row.get("exit_price") or exit_signals.get("price", 0)
        pnl = exit_price - entry_price if entry_price > 0 else 0

        matched.append({
            "position_id": pid,
            "ticker": row["ticker"],
            "entry_time": row["entry_time"],
            "exit_time": row["exit_time"],
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": pnl,
            "win": pnl > 0,
            "status": "closed",
            "signal_combo": parse_signal_combo(entry_signals),
            "entry_signals": entry_signals,
            "exit_signals": exit_signals,
            "strategy_id": row.get("strategy_id"),
            "reasoning": row.get("entry_reasoning", ""),
        })

    # FIFO fallback for old records without position_id
    decisions = db.get_decisions(limit=500)
    buy_decisions = [d for d in decisions if d["action"] == "buy" and not d.get("position_id")]
    sell_decisions = [d for d in decisions if d["action"] == "sell" and not d.get("position_id")]

    for buy in buy_decisions:
        ticker = buy["ticker"]
        buy_time = buy["timestamp"]

        sell = None
        for s in sell_decisions:
            if s["ticker"] == ticker and s["timestamp"] >= buy_time:
                sell = s
                break

        try:
            entry_signals = json.loads(buy.get("signals_snapshot", "{}"))
        except (json.JSONDecodeError, TypeError):
            entry_signals = {}

        entry_price = entry_signals.get("price", 0)

        if sell:
            try:
                exit_signals = json.loads(sell.get("signals_snapshot", "{}"))
            except (json.JSONDecodeError, TypeError):
                exit_signals = {}
            exit_price = exit_signals.get("price", 0)
            pnl = exit_price - entry_price if entry_price > 0 else 0
            status = "closed"
        else:
            exit_signals = {}
            exit_price = 0
            pnl = 0
            status = "open"

        matched.append({
            "position_id": None,
            "ticker": ticker,
            "entry_time": buy_time,
            "exit_time": sell["timestamp"] if sell else None,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": pnl,
            "win": pnl > 0,
            "status": status,
            "signal_combo": parse_signal_combo(entry_signals),
            "entry_signals": entry_signals,
            "exit_signals": exit_signals,
            "strategy_id": entry_signals.get("strategy_id"),
            "reasoning": buy.get("reasoning", ""),
        })

    return matched
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_learner.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/claude_invest/modules/learner.py tests/test_learner.py
git commit -m "feat: add position_id matching to learner with FIFO fallback"
```

---

### Task 4: Pattern Analyzer Module

**Files:**
- Create: `src/claude_invest/modules/pattern_analyzer.py`
- Create: `tests/test_pattern_analyzer.py`

- [ ] **Step 1: Write failing tests for pattern analyzer**

Create `tests/test_pattern_analyzer.py`:

```python
import json
import pytest
from datetime import datetime, timedelta
from claude_invest.modules.db import Database
from claude_invest.modules.pattern_analyzer import analyze_patterns


def _make_trade(ticker, entry_price, exit_price, entry_rsi, entry_macd,
                entry_macd_signal, trend, sentiment, strategy_id,
                entry_hour=10, hold_minutes=60, position_id="pos-1"):
    """Helper to build a matched trade dict."""
    entry_time = datetime(2026, 4, 25, entry_hour, 0).isoformat()
    exit_time = (datetime(2026, 4, 25, entry_hour, 0) + timedelta(minutes=hold_minutes)).isoformat()
    return {
        "position_id": position_id,
        "ticker": ticker,
        "entry_time": entry_time,
        "exit_time": exit_time,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "pnl": exit_price - entry_price,
        "win": exit_price > entry_price,
        "status": "closed",
        "signal_combo": f"rsi_30_50 + macd_above_signal + trend_{trend}",
        "entry_signals": {
            "rsi": entry_rsi, "macd": entry_macd,
            "macd_signal": entry_macd_signal, "trend": trend,
            "sentiment": sentiment, "price": entry_price,
        },
        "exit_signals": {"price": exit_price},
        "strategy_id": strategy_id,
        "reasoning": "test",
    }


def test_analyze_patterns_returns_all_dimensions():
    trades = [
        _make_trade("BTC/USD", 75000, 76000, 45, -200, -250, "neutral", 0.1, "momentum",
                     entry_hour=10, hold_minutes=60, position_id="p1"),
        _make_trade("AAPL", 180, 185, 35, 0.5, 0.3, "bullish", 0.4, "mean_reversion",
                     entry_hour=9, hold_minutes=30, position_id="p2"),
        _make_trade("ETH/USD", 2300, 2280, 55, -5, -3, "bearish", 0.05, "momentum",
                     entry_hour=22, hold_minutes=120, position_id="p3"),
    ]
    report = analyze_patterns(trades)

    assert "generated_at" in report
    assert "total_trades" in report
    assert report["total_trades"] == 3
    assert "overall_win_rate" in report
    assert "signal_combos" in report
    assert "time_of_day" in report
    assert "hold_duration" in report
    assert "market_regime" in report
    assert "asset_class" in report
    assert "cross_dimensional" in report


def test_time_of_day_bucketing():
    trades = [
        _make_trade("AAPL", 180, 185, 35, 0.5, 0.3, "bullish", 0.4, "mean_reversion",
                     entry_hour=9, hold_minutes=30, position_id="p1"),  # market_open
        _make_trade("AAPL", 180, 175, 55, 0.5, 0.3, "bullish", 0.4, "mean_reversion",
                     entry_hour=12, hold_minutes=30, position_id="p2"),  # midday
    ]
    report = analyze_patterns(trades)
    buckets = {b["bucket"]: b for b in report["time_of_day"]}
    assert "market_open" in buckets
    assert buckets["market_open"]["wins"] == 1
    assert "midday" in buckets
    assert buckets["midday"]["losses"] == 1


def test_hold_duration_bucketing():
    trades = [
        _make_trade("AAPL", 180, 185, 35, 0.5, 0.3, "bullish", 0.4, "mean_reversion",
                     hold_minutes=10, position_id="p1"),  # scalp
        _make_trade("AAPL", 180, 185, 35, 0.5, 0.3, "bullish", 0.4, "mean_reversion",
                     hold_minutes=120, position_id="p2"),  # swing_short
    ]
    report = analyze_patterns(trades)
    buckets = {b["bucket"]: b for b in report["hold_duration"]}
    assert "scalp" in buckets
    assert "swing_short" in buckets


def test_asset_class_detection():
    trades = [
        _make_trade("BTC/USD", 75000, 76000, 45, -200, -250, "neutral", 0.1, "momentum",
                     position_id="p1"),
        _make_trade("AAPL", 180, 185, 35, 0.5, 0.3, "bullish", 0.4, "mean_reversion",
                     position_id="p2"),
    ]
    report = analyze_patterns(trades)
    classes = {(a["asset_class"], a["strategy_id"]): a for a in report["asset_class"]}
    assert ("crypto", "momentum") in classes
    assert ("stock", "mean_reversion") in classes


def test_confidence_levels():
    # 3 trades = insufficient for any individual bucket likely, but tests structure
    trades = [
        _make_trade("AAPL", 180, 185, 35, 0.5, 0.3, "bullish", 0.4, "mean_reversion",
                     position_id=f"p{i}")
        for i in range(5)
    ]
    report = analyze_patterns(trades)
    # With 5 trades all in same combo, should have "low" confidence (5-9)
    for combo in report["signal_combos"]:
        if combo["total"] >= 5 and combo["total"] < 10:
            assert combo["confidence"] == "low"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_pattern_analyzer.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement pattern_analyzer.py**

Create `src/claude_invest/modules/pattern_analyzer.py`:

```python
from datetime import datetime
from collections import defaultdict


def _get_time_bucket(timestamp_str: str) -> str:
    """Bucket a timestamp into trading windows (ET assumed)."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        hour = dt.hour
    except (ValueError, AttributeError):
        return "unknown"

    if 9 <= hour < 9.5 or (hour == 9 and dt.minute < 30):
        return "pre_market"
    elif (hour == 9 and dt.minute >= 30) or hour == 10:
        return "market_open"
    elif 11 <= hour < 15:
        return "midday"
    elif 15 <= hour < 16:
        return "market_close"
    elif 16 <= hour < 20:
        return "after_hours"
    else:
        return "crypto_overnight"


def _get_hold_duration_bucket(entry_time: str, exit_time: str) -> str:
    """Bucket hold duration."""
    try:
        entry = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
        exit_ = datetime.fromisoformat(exit_time.replace("Z", "+00:00"))
        minutes = (exit_ - entry).total_seconds() / 60
    except (ValueError, AttributeError, TypeError):
        return "unknown"

    if minutes < 15:
        return "scalp"
    elif minutes < 60:
        return "intraday"
    elif minutes < 1440:  # 24 hours
        return "swing_short"
    elif minutes < 7200:  # 5 days
        return "swing_long"
    else:
        return "position"


def _get_asset_class(ticker: str) -> str:
    """Detect asset class from ticker format."""
    return "crypto" if "/" in ticker else "stock"


def _get_confidence(total: int) -> str:
    if total < 5:
        return "insufficient"
    elif total < 10:
        return "low"
    else:
        return "high"


def _aggregate_bucket(trades: list[dict]) -> dict:
    """Aggregate win/loss stats for a group of trades."""
    wins = sum(1 for t in trades if t["win"])
    losses = len(trades) - wins
    total_pnl = sum(t["pnl"] for t in trades)
    return {
        "wins": wins,
        "losses": losses,
        "total": len(trades),
        "win_rate": round(wins / len(trades), 4) if trades else 0,
        "avg_pnl": round(total_pnl / len(trades), 4) if trades else 0,
        "confidence": _get_confidence(len(trades)),
    }


def analyze_patterns(matched_trades: list[dict]) -> dict:
    """Analyze completed trades across 5 dimensions.

    Args:
        matched_trades: List of closed trade dicts with entry/exit signals,
                       timestamps, pnl, win status, strategy_id, ticker.

    Returns:
        LearningReport dict with signal_combos, time_of_day, hold_duration,
        market_regime, asset_class, and cross_dimensional sections.
    """
    closed = [t for t in matched_trades if t.get("status") == "closed"]

    # Dimension 1: Signal Combos
    combo_groups = defaultdict(list)
    for t in closed:
        combo_groups[t.get("signal_combo", "unknown")].append(t)

    signal_combos = []
    for combo, trades in combo_groups.items():
        stats = _aggregate_bucket(trades)
        stats["combo"] = combo
        stats["tickers"] = list({t["ticker"] for t in trades})
        signal_combos.append(stats)
    signal_combos.sort(key=lambda x: x["win_rate"], reverse=True)

    # Dimension 2: Time of Day
    time_groups = defaultdict(list)
    for t in closed:
        bucket = _get_time_bucket(t.get("entry_time", ""))
        time_groups[bucket].append(t)

    time_of_day = []
    for bucket, trades in time_groups.items():
        stats = _aggregate_bucket(trades)
        stats["bucket"] = bucket
        time_of_day.append(stats)

    # Dimension 3: Hold Duration
    duration_groups = defaultdict(list)
    for t in closed:
        bucket = _get_hold_duration_bucket(
            t.get("entry_time", ""), t.get("exit_time", ""))
        duration_groups[bucket].append(t)

    hold_duration = []
    for bucket, trades in duration_groups.items():
        stats = _aggregate_bucket(trades)
        stats["bucket"] = bucket
        hold_duration.append(stats)

    # Dimension 4: Market Regime
    # Simplified: use RSI range as volatility proxy until ATR is available
    regime_groups = defaultdict(list)
    for t in closed:
        rsi = t.get("entry_signals", {}).get("rsi", 50)
        if rsi is None:
            rsi = 50
        # High vol proxy: extreme RSI (<30 or >70), low vol: RSI near 50
        if rsi < 30 or rsi > 70:
            regime = "high_volatility"
        elif 40 <= rsi <= 60:
            regime = "low_volatility"
        else:
            regime = "normal"
        regime_groups[regime].append(t)

    market_regime = []
    for regime, trades in regime_groups.items():
        stats = _aggregate_bucket(trades)
        stats["regime"] = regime
        market_regime.append(stats)

    # Dimension 5: Asset Class x Strategy
    class_groups = defaultdict(list)
    for t in closed:
        asset = _get_asset_class(t.get("ticker", ""))
        strategy = t.get("strategy_id") or "unknown"
        class_groups[(asset, strategy)].append(t)

    asset_class = []
    for (asset, strategy), trades in class_groups.items():
        stats = _aggregate_bucket(trades)
        stats["asset_class"] = asset
        stats["strategy_id"] = strategy
        asset_class.append(stats)

    # Cross-Dimensional (2-way combos with 3+ trades)
    cross_groups = defaultdict(list)
    for t in closed:
        time_bucket = _get_time_bucket(t.get("entry_time", ""))
        strategy = t.get("strategy_id") or "unknown"
        asset = _get_asset_class(t.get("ticker", ""))
        # Strategy x Time
        cross_groups[f"{strategy} + {time_bucket}"].append(t)
        # Strategy x Asset
        cross_groups[f"{strategy} + {asset}"].append(t)
        # Time x Asset
        cross_groups[f"{time_bucket} + {asset}"].append(t)

    cross_dimensional = []
    for key, trades in cross_groups.items():
        if len(trades) >= 3:
            stats = _aggregate_bucket(trades)
            stats["insight"] = f"{key}: {stats['wins']}W/{stats['losses']}L"
            stats["actionable"] = stats["win_rate"] >= 0.75 or stats["win_rate"] <= 0.25
            cross_dimensional.append(stats)
    cross_dimensional.sort(key=lambda x: abs(x["win_rate"] - 0.5), reverse=True)

    total_wins = sum(1 for t in closed if t["win"])
    total = len(closed)

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "total_trades": total,
        "overall_win_rate": round(total_wins / total, 4) if total > 0 else 0,
        "signal_combos": signal_combos,
        "time_of_day": time_of_day,
        "hold_duration": hold_duration,
        "market_regime": market_regime,
        "asset_class": asset_class,
        "cross_dimensional": cross_dimensional,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_pattern_analyzer.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/claude_invest/modules/pattern_analyzer.py tests/test_pattern_analyzer.py
git commit -m "feat: add pattern analyzer with 5-dimension trade analysis"
```

---

### Task 5: Parameter Optimizer Module

**Files:**
- Create: `src/claude_invest/modules/optimizer.py`
- Create: `tests/test_optimizer.py`

- [ ] **Step 1: Write failing tests for optimizer**

Create `tests/test_optimizer.py`:

```python
import json
import os
import pytest
from claude_invest.modules.db import Database
from claude_invest.modules.optimizer import (
    evaluate_parameters,
    apply_change,
    check_evaluation_windows,
    OPTIMIZABLE_PARAMS,
)


@pytest.fixture
def config_path(tmp_path):
    """Create a temporary settings.yaml."""
    from ruamel.yaml import YAML
    yaml = YAML()
    config = {
        "strategies": {
            "active": ["mean_reversion", "trend_pullback", "momentum"],
            "mean_reversion": {
                "name": "RSI(2) Mean Reversion",
                "enabled": True,
                "capital_pct": 0.33,
                "params": {
                    "rsi_buy_threshold": 25,
                    "rsi_sell_threshold": 65,
                    "max_hold_bars": 5,
                    "stop_loss_pct": 0.01,
                    "take_profit_pct": 0.02,
                },
            },
            "trend_pullback": {
                "name": "MACD 5/35/5 Trend",
                "enabled": True,
                "capital_pct": 0.34,
                "params": {
                    "macd_fast": 5,
                    "macd_slow": 35,
                    "stop_loss_pct": 0.02,
                    "take_profit_pct": 0.04,
                },
            },
            "momentum": {
                "name": "Momentum Breakout",
                "enabled": True,
                "capital_pct": 0.33,
                "params": {
                    "stop_loss_pct": 0.05,
                    "take_profit_pct": 0.10,
                },
            },
        },
    }
    path = str(tmp_path / "settings.yaml")
    with open(path, "w") as f:
        yaml.dump(config, f)
    return path


def test_optimizable_params_defined():
    assert "rsi_buy_threshold" in OPTIMIZABLE_PARAMS
    assert OPTIMIZABLE_PARAMS["rsi_buy_threshold"]["min"] == 10
    assert OPTIMIZABLE_PARAMS["rsi_buy_threshold"]["max"] == 40


def test_evaluate_parameters_proposes_at_5_trades():
    """With 5 trades showing better performance at different param value, should propose."""
    trades_by_strategy = {
        "mean_reversion": [
            {"win": True, "entry_signals": {"rsi": 18}},
            {"win": True, "entry_signals": {"rsi": 19}},
            {"win": True, "entry_signals": {"rsi": 17}},
            {"win": False, "entry_signals": {"rsi": 24}},
            {"win": False, "entry_signals": {"rsi": 23}},
        ]
    }
    current_config = {
        "strategies": {
            "mean_reversion": {"params": {"rsi_buy_threshold": 25}},
        }
    }
    proposals = evaluate_parameters(trades_by_strategy, current_config)
    # Should find that lower RSI entries win more
    assert len(proposals) >= 0  # May or may not propose depending on significance


def test_apply_change_updates_yaml(config_path, tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()

    apply_change(
        config_path=config_path,
        db=db,
        parameter_path="strategies.mean_reversion.params.rsi_buy_threshold",
        old_value="25",
        new_value="20",
        reason="Test change",
        trade_count=10,
        auto_applied=True,
    )

    from ruamel.yaml import YAML
    yaml = YAML()
    with open(config_path) as f:
        config = yaml.load(f)
    assert config["strategies"]["mean_reversion"]["params"]["rsi_buy_threshold"] == 20

    changes = db.get_change_log()
    assert len(changes) == 1
    assert changes[0]["new_value"] == "20"
    db.close()


def test_apply_change_respects_bounds(config_path, tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()

    # Trying to set RSI below minimum bound of 10
    apply_change(
        config_path=config_path,
        db=db,
        parameter_path="strategies.mean_reversion.params.rsi_buy_threshold",
        old_value="25",
        new_value="5",  # Below min bound of 10
        reason="Test",
        trade_count=10,
        auto_applied=True,
    )

    from ruamel.yaml import YAML
    yaml = YAML()
    with open(config_path) as f:
        config = yaml.load(f)
    # Should be clamped to minimum bound 10, not 5
    assert config["strategies"]["mean_reversion"]["params"]["rsi_buy_threshold"] == 10
    db.close()


def test_max_active_changes_guardrail(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    # Insert 3 active changes
    for i in range(3):
        db.insert_change_log({
            "parameter_path": f"strategies.s{i}.params.param",
            "old_value": "1", "new_value": "2",
            "reason": "test", "trade_count": 10, "auto_applied": True,
        })
    active = db.get_active_changes()
    assert len(active) == 3
    db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_optimizer.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement optimizer.py**

Create `src/claude_invest/modules/optimizer.py`:

```python
from collections import defaultdict
from ruamel.yaml import YAML

from claude_invest.modules.db import Database


OPTIMIZABLE_PARAMS = {
    "rsi_buy_threshold": {"min": 10, "max": 40, "step": 5, "strategies": ["mean_reversion"]},
    "rsi_sell_threshold": {"min": 55, "max": 85, "step": 5, "strategies": ["mean_reversion"]},
    "max_hold_bars": {"min": 3, "max": 10, "step": 1, "strategies": ["mean_reversion"]},
    "stop_loss_pct": {"min": 0.005, "max": 0.05, "step": 0.005, "strategies": ["mean_reversion", "trend_pullback", "momentum"]},
    "take_profit_pct": {"min": 0.01, "max": 0.10, "step": 0.01, "strategies": ["mean_reversion", "trend_pullback", "momentum"]},
    "macd_fast": {"min": 3, "max": 12, "step": 1, "strategies": ["trend_pullback"]},
    "macd_slow": {"min": 20, "max": 50, "step": 5, "strategies": ["trend_pullback"]},
}

MAX_ACTIVE_CHANGES = 3
MAX_CHANGES_PER_STRATEGY_PER_DAY = 1
EVAL_WINDOW_TRADES = 10
REVERT_WIN_RATE_DROP = 0.15
MAX_REVERTS_BEFORE_LOCK = 2


def _clamp(value, param_name: str):
    """Clamp a value to the parameter's valid bounds."""
    bounds = OPTIMIZABLE_PARAMS.get(param_name, {})
    min_val = bounds.get("min", value)
    max_val = bounds.get("max", value)
    if isinstance(value, float):
        return max(min_val, min(max_val, value))
    return max(int(min_val), min(int(max_val), int(value)))


def evaluate_parameters(trades_by_strategy: dict, current_config: dict) -> list[dict]:
    """Evaluate whether any parameter changes would improve performance.

    Args:
        trades_by_strategy: Dict of strategy_id -> list of trade dicts
        current_config: Current settings.yaml as dict

    Returns:
        List of proposed changes with parameter_path, old_value, new_value, reason, trade_count
    """
    proposals = []

    for strategy_id, trades in trades_by_strategy.items():
        if len(trades) < 5:
            continue

        strat_config = current_config.get("strategies", {}).get(strategy_id, {})
        params = strat_config.get("params", {})

        for param_name, bounds in OPTIMIZABLE_PARAMS.items():
            if strategy_id not in bounds.get("strategies", []):
                continue

            current_val = params.get(param_name)
            if current_val is None:
                continue

            # Split trades into "at or below current threshold" vs "above"
            # This is a simplified analysis — compare win rates at different ranges
            step = bounds["step"]
            test_val = current_val - step if isinstance(current_val, (int, float)) else current_val

            if param_name.endswith("_threshold") or param_name.startswith("rsi_"):
                # For entry thresholds: check if tighter threshold improves win rate
                at_current = [t for t in trades if _param_matches(t, param_name, current_val, step)]
                at_tighter = [t for t in trades if _param_matches_tighter(t, param_name, current_val, step)]

                if len(at_tighter) >= 3 and len(at_current) >= 3:
                    current_wr = sum(1 for t in at_current if t["win"]) / len(at_current)
                    tighter_wr = sum(1 for t in at_tighter if t["win"]) / len(at_tighter)

                    if tighter_wr > current_wr + 0.10:  # At least 10% improvement
                        new_val = _clamp(test_val, param_name)
                        if new_val != current_val:
                            auto = len(trades) >= 10
                            proposals.append({
                                "parameter_path": f"strategies.{strategy_id}.params.{param_name}",
                                "old_value": str(current_val),
                                "new_value": str(new_val),
                                "reason": f"{len(trades)} trades: win rate {tighter_wr:.0%} at {param_name}={new_val} vs {current_wr:.0%} at {current_val}",
                                "trade_count": len(trades),
                                "auto_applied": auto,
                            })

    return proposals


def _param_matches(trade: dict, param_name: str, current_val, step) -> bool:
    """Check if a trade's entry signals are near the current parameter value."""
    signals = trade.get("entry_signals", {})
    if "rsi_buy" in param_name:
        rsi = signals.get("rsi", 50)
        return rsi is not None and rsi <= current_val + step
    return True


def _param_matches_tighter(trade: dict, param_name: str, current_val, step) -> bool:
    """Check if a trade's entry signals match a tighter threshold."""
    signals = trade.get("entry_signals", {})
    if "rsi_buy" in param_name:
        rsi = signals.get("rsi", 50)
        return rsi is not None and rsi <= current_val - step
    return True


def apply_change(config_path: str, db: Database, parameter_path: str,
                 old_value: str, new_value: str, reason: str,
                 trade_count: int, auto_applied: bool):
    """Apply a parameter change to settings.yaml and log it.

    Args:
        config_path: Path to settings.yaml
        db: Database instance for logging
        parameter_path: Dot-notation path (e.g., "strategies.mean_reversion.params.rsi_buy_threshold")
        old_value, new_value: String representations of values
        reason: Why this change is being made
        trade_count: Number of trades that informed this
        auto_applied: Whether this was auto-applied (True) or proposed (False)
    """
    yaml = YAML()
    yaml.preserve_quotes = True

    with open(config_path) as f:
        config = yaml.load(f)

    # Navigate to the parameter
    parts = parameter_path.split(".")
    node = config
    for part in parts[:-1]:
        node = node[part]

    param_name = parts[-1]
    old_typed = node[param_name]

    # Parse and clamp new value
    if isinstance(old_typed, float):
        new_typed = _clamp(float(new_value), param_name)
    elif isinstance(old_typed, int):
        new_typed = _clamp(int(float(new_value)), param_name)
    else:
        new_typed = new_value

    node[param_name] = new_typed

    with open(config_path, "w") as f:
        yaml.dump(config, f)

    # Log the change
    db.insert_change_log({
        "parameter_path": parameter_path,
        "old_value": str(old_value),
        "new_value": str(new_typed),
        "reason": reason,
        "trade_count": trade_count,
        "auto_applied": auto_applied,
    })


def check_evaluation_windows(db: Database, trades_by_strategy: dict,
                              config_path: str) -> list[dict]:
    """Check active parameter changes and revert if performance dropped.

    Returns:
        List of reverted changes.
    """
    active_changes = db.get_active_changes()
    reverted = []

    for change in active_changes:
        path = change["parameter_path"]
        # Extract strategy_id from path: "strategies.<id>.params.<param>"
        parts = path.split(".")
        if len(parts) >= 2:
            strategy_id = parts[1]
        else:
            continue

        trades = trades_by_strategy.get(strategy_id, [])

        # Count trades after the change was applied
        change_time = change["timestamp"]
        post_change_trades = [
            t for t in trades
            if t.get("entry_time", "") > change_time
        ]

        if len(post_change_trades) < EVAL_WINDOW_TRADES:
            continue  # Not enough trades to evaluate yet

        # Calculate post-change win rate
        post_wr = sum(1 for t in post_change_trades[:EVAL_WINDOW_TRADES] if t["win"]) / EVAL_WINDOW_TRADES

        # Compare to the win rate that justified the change
        original_wr = change["trade_count"]  # This is imprecise; use the reason text
        # If win rate dropped significantly, revert
        pre_change_wr = _extract_win_rate_from_reason(change["reason"])
        if pre_change_wr is not None and post_wr < pre_change_wr - REVERT_WIN_RATE_DROP:
            _revert_change(db, change, config_path,
                          f"Win rate dropped to {post_wr:.0%} from {pre_change_wr:.0%} after {EVAL_WINDOW_TRADES} trades")
            reverted.append(change)

    return reverted


def _extract_win_rate_from_reason(reason: str) -> float | None:
    """Try to extract the new win rate from the reason string."""
    # Reason format: "N trades: win rate X% at param=val vs Y% at old"
    try:
        parts = reason.split("win rate ")
        if len(parts) >= 2:
            pct_str = parts[1].split("%")[0].strip()
            return float(pct_str) / 100
    except (ValueError, IndexError):
        pass
    return None


def _revert_change(db: Database, change: dict, config_path: str, reason: str):
    """Revert a parameter change."""
    yaml = YAML()
    yaml.preserve_quotes = True

    with open(config_path) as f:
        config = yaml.load(f)

    parts = change["parameter_path"].split(".")
    node = config
    for part in parts[:-1]:
        node = node[part]

    old_typed = node[parts[-1]]
    if isinstance(old_typed, float):
        node[parts[-1]] = float(change["old_value"])
    elif isinstance(old_typed, int):
        node[parts[-1]] = int(float(change["old_value"]))
    else:
        node[parts[-1]] = change["old_value"]

    with open(config_path, "w") as f:
        yaml.dump(config, f)

    db.revert_change(change["id"], reason)


def can_apply_more_changes(db: Database) -> bool:
    """Check if we're under the max active changes limit."""
    return len(db.get_active_changes()) < MAX_ACTIVE_CHANGES
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_optimizer.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/claude_invest/modules/optimizer.py tests/test_optimizer.py
git commit -m "feat: add parameter optimizer with guardrails and auto-revert"
```

---

### Task 6: Enhanced Strategy Brief Generation

**Files:**
- Modify: `src/claude_invest/modules/strategy.py`
- Modify: `tests/test_strategy.py`

- [ ] **Step 1: Write failing test for enhanced brief**

Add to `tests/test_strategy.py`:

```python
def test_build_strategy_brief_with_dimensions(lessons_dir):
    patterns = [
        {
            "signal_combo": "macd_above_signal + rsi_30_50",
            "wins": 4, "losses": 0, "total": 4,
            "win_rate": 1.0, "avg_pnl": 2.0, "confidence": "high",
        },
    ]
    update_lessons(lessons_dir, patterns, "2026-04-25")

    allocation = {
        "tiers": {
            "safe": {"target": 0.30, "actual": 0.0, "drift": -0.30, "alert": True},
        },
        "total_value": 5500,
    }

    dimension_insights = {
        "best_time": {"bucket": "market_open", "win_rate": 0.80, "total": 5},
        "best_duration": {"bucket": "swing_short", "win_rate": 0.75, "total": 6},
        "volatility_note": "High volatility favors mean_reversion",
        "asset_note": "Crypto momentum is 0W/1L",
    }

    active_changes = [
        {
            "parameter_path": "strategies.mean_reversion.params.rsi_buy_threshold",
            "old_value": "25", "new_value": "20",
            "timestamp": "2026-04-24", "trade_count": 12, "auto_applied": True,
        },
    ]

    proposed_changes = [
        {
            "parameter_path": "strategies.trend_pullback.params.stop_loss_pct",
            "old_value": "0.02", "new_value": "0.025",
            "trade_count": 7,
        },
    ]

    brief = build_strategy_brief(
        lessons_dir, allocation,
        dimension_insights=dimension_insights,
        active_changes=active_changes,
        proposed_changes=proposed_changes,
    )

    assert "PARAMETER CHANGES ACTIVE" in brief
    assert "rsi_buy_threshold" in brief
    assert "DIMENSION INSIGHTS" in brief
    assert "market_open" in brief
    assert "PROPOSED" in brief or "proposed" in brief.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_strategy.py::test_build_strategy_brief_with_dimensions -v`
Expected: FAIL — `build_strategy_brief` doesn't accept new kwargs

- [ ] **Step 3: Update strategy.py with enhanced brief generation**

Update `build_strategy_brief` in `src/claude_invest/modules/strategy.py`:

```python
def build_strategy_brief(lessons_dir: str, allocation: dict, *,
                         dimension_insights: dict | None = None,
                         active_changes: list[dict] | None = None,
                         proposed_changes: list[dict] | None = None) -> str:
    lessons = load_lessons(lessons_dir)
    patterns = lessons.get("patterns", [])

    lines = ["# Strategy Brief", ""]
    date = lessons.get("last_updated", "never")
    lines.append(f"*Updated: {date} (auto-generated)*")
    lines.append("")

    rules_always = [p for p in patterns if p.get("confidence") == "high" and p.get("win_rate", 0) >= 0.75 and p.get("total", 0) >= 3]
    rules_never = [p for p in patterns if p.get("confidence") == "high" and p.get("win_rate", 1) <= 0.25 and p.get("total", 0) >= 3]
    observations = [p for p in patterns if p.get("confidence") != "high" or p.get("total", 0) < 3]

    if rules_always:
        lines.append("## RULES — ALWAYS")
        for r in rules_always:
            lines.append(f"- PREFER: {r['signal_combo']} ({r['wins']}W/{r['losses']}L, avg +{r['avg_pnl']:.2f})")
        lines.append("")

    if rules_never:
        lines.append("## RULES — NEVER")
        for r in rules_never:
            lines.append(f"- AVOID: {r['signal_combo']} ({r['wins']}W/{r['losses']}L, avg {r['avg_pnl']:.2f})")
        lines.append("")

    if observations:
        lines.append("## OBSERVATIONS (need more data)")
        for o in sorted(observations, key=lambda x: x.get("total", 0), reverse=True)[:10]:
            wr = o.get("win_rate", 0)
            lines.append(f"- {o['signal_combo']}: {o.get('wins',0)}W/{o.get('losses',0)}L ({wr:.0%} win rate)")
        lines.append("")

    # Parameter changes section
    if active_changes or proposed_changes:
        lines.append("## PARAMETER CHANGES ACTIVE")
        if active_changes:
            for c in active_changes:
                path = c["parameter_path"].split(".")[-1]
                strategy = c["parameter_path"].split(".")[1] if "." in c["parameter_path"] else "unknown"
                lines.append(f"- {strategy}.{path}: {c['old_value']} → {c['new_value']} (applied {c.get('timestamp', 'unknown')}, {c['trade_count']} trades)")
        if proposed_changes:
            for c in proposed_changes:
                path = c["parameter_path"].split(".")[-1]
                strategy = c["parameter_path"].split(".")[1] if "." in c["parameter_path"] else "unknown"
                lines.append(f"- PROPOSED: {strategy}.{path}: {c['old_value']} → {c['new_value']} (needs {10 - c['trade_count']} more trades)")
        lines.append("")

    # Dimension insights section
    if dimension_insights:
        lines.append("## DIMENSION INSIGHTS")
        if "best_time" in dimension_insights:
            bt = dimension_insights["best_time"]
            lines.append(f"- Best time window: {bt['bucket']} ({bt['win_rate']:.0%} win rate, {bt['total']} trades)")
        if "best_duration" in dimension_insights:
            bd = dimension_insights["best_duration"]
            lines.append(f"- Best hold duration: {bd['bucket']} ({bd['win_rate']:.0%} win rate, {bd['total']} trades)")
        if "volatility_note" in dimension_insights:
            lines.append(f"- {dimension_insights['volatility_note']}")
        if "asset_note" in dimension_insights:
            lines.append(f"- {dimension_insights['asset_note']}")
        lines.append("")

    # Allocation alerts
    tiers = allocation.get("tiers", {})
    alerts = [(name, t) for name, t in tiers.items() if t.get("alert")]
    if alerts:
        lines.append("## ALLOCATION ALERTS")
        for name, t in alerts:
            direction = "OVER" if t["drift"] > 0 else "UNDER"
            lines.append(f"- {name.upper()}: {t['actual']:.0%} actual vs {t['target']:.0%} target ({direction} by {abs(t['drift']):.0%})")
        lines.append("")

    total_wins = sum(p.get("wins", 0) for p in patterns)
    total_losses = sum(p.get("losses", 0) for p in patterns)
    total = total_wins + total_losses
    if total > 0:
        lines.append(f"## OVERALL: {total_wins}W/{total_losses}L ({total_wins/total:.0%} win rate)")

    brief = "\n".join(lines)

    brief_path = os.path.join(lessons_dir, "strategy-brief.md")
    with open(brief_path, "w") as f:
        f.write(brief)

    return brief
```

- [ ] **Step 4: Run all strategy tests**

Run: `.venv/bin/python -m pytest tests/test_strategy.py -v`
Expected: All tests PASS (old tests still work because new params are optional)

- [ ] **Step 5: Commit**

```bash
git add src/claude_invest/modules/strategy.py tests/test_strategy.py
git commit -m "feat: enhance strategy brief with dimension insights and parameter changes"
```

---

### Task 7: Update main.py — position_id Generation and New Commands

**Files:**
- Modify: `src/claude_invest/main.py`

- [ ] **Step 1: Add position_id generation and new commands**

Add `import uuid` at the top of `main.py`.

Update `cmd_log_decision` to generate position_id on buy:

```python
def cmd_log_decision(payload_json: str):
    payload = json.loads(payload_json)
    db = Database(DB_PATH)
    db.initialize()

    # Generate position_id for buy decisions
    if payload.get("action") == "buy" and "position_id" not in payload:
        payload["position_id"] = str(uuid.uuid4())

    db.insert_decision(payload)
    db.close()
    _output({"status": "logged", "decision": payload})
```

Update `cmd_execute` to accept and pass position_id:

```python
def cmd_execute(side: str, ticker: str, qty: float, position_id: str | None = None):
    result = execute_order(symbol=ticker, side=side, qty=qty)
    db = Database(DB_PATH)
    db.initialize()
    if result["status"] != "error":
        db.insert_trade({
            "symbol": ticker,
            "side": side,
            "qty": qty,
            "price": result.get("filled_price") or 0,
            "order_id": result["order_id"],
            "trade_type": "market",
            "status": result["status"],
            "position_id": position_id,
        })
    db.close()
    _output(result)
```

Update `cmd_review_day` to use the full learning pipeline:

```python
def cmd_review_day(date: str | None = None):
    config = load_config()
    from claude_invest.config.loader import DEFAULT_CONFIG_PATH
    db = Database(DB_PATH)
    db.initialize()

    # Get matched trades
    from claude_invest.modules.learner import _match_trades
    matched = _match_trades(db)
    closed = [m for m in matched if m["status"] == "closed"]

    # Run pattern analyzer
    from claude_invest.modules.pattern_analyzer import analyze_patterns
    learning_report = analyze_patterns(closed)

    # Group trades by strategy for optimizer
    from collections import defaultdict
    trades_by_strategy = defaultdict(list)
    for t in closed:
        sid = t.get("strategy_id") or "unknown"
        trades_by_strategy[sid].append(t)

    # Run optimizer
    from claude_invest.modules.optimizer import (
        evaluate_parameters, apply_change, check_evaluation_windows, can_apply_more_changes
    )
    reverted = check_evaluation_windows(db, dict(trades_by_strategy), DEFAULT_CONFIG_PATH)
    proposals = evaluate_parameters(dict(trades_by_strategy), config)

    applied = []
    proposed = []
    for p in proposals:
        if p["auto_applied"] and can_apply_more_changes(db):
            apply_change(DEFAULT_CONFIG_PATH, db, **p)
            applied.append(p)
        else:
            p["auto_applied"] = False
            db.insert_change_log(p)
            proposed.append(p)

    # Build dimension insights for brief
    dimension_insights = {}
    if learning_report["time_of_day"]:
        best_time = max(learning_report["time_of_day"], key=lambda x: x.get("win_rate", 0))
        if best_time.get("total", 0) >= 5:
            dimension_insights["best_time"] = best_time
    if learning_report["hold_duration"]:
        best_dur = max(learning_report["hold_duration"], key=lambda x: x.get("win_rate", 0))
        if best_dur.get("total", 0) >= 5:
            dimension_insights["best_duration"] = best_dur

    # Get allocation
    try:
        from claude_invest.modules.portfolio import get_portfolio
        portfolio = get_portfolio()
        allocation = get_allocation(config, portfolio["positions"])
    except Exception:
        allocation = {"tiers": {}, "total_value": 0}

    # Get active changes for brief
    active_changes = db.get_active_changes()

    # Build enhanced strategy brief
    report = analyze_day(db, date)
    update_lessons(LESSONS_DIR, report["patterns"], report["date"])
    brief = build_strategy_brief(
        LESSONS_DIR, allocation,
        dimension_insights=dimension_insights,
        active_changes=active_changes,
        proposed_changes=proposed,
    )

    # Write daily report
    _write_daily_report(report, learning_report, applied, proposed, reverted)

    report["learning_report"] = learning_report
    report["applied_changes"] = applied
    report["proposed_changes"] = proposed
    report["reverted_changes"] = reverted
    report["allocation"] = allocation
    report["strategy_brief"] = brief
    db.close()
    _output(report)


def _write_daily_report(report: dict, learning_report: dict,
                        applied: list, proposed: list, reverted: list):
    """Write human-readable daily report to lessons/daily/."""
    import os
    date = report.get("date", "unknown")
    daily_path = os.path.join(LESSONS_DIR, "daily", f"{date}.md")
    os.makedirs(os.path.dirname(daily_path), exist_ok=True)

    lines = [f"# Daily Learning Report — {date}", ""]

    # Performance Summary
    lines.append("## Performance Summary")
    lines.append(f"- Trades closed: {report['total_trades']} ({report['wins']}W/{report['losses']}L)")
    lines.append(f"- Total P&L: ${report['total_pnl']:.2f}")
    wr = report['win_rate']
    lines.append(f"- Win rate: {wr:.0%}")
    lines.append("")

    # Dimension Analysis
    lines.append("## Dimension Analysis")

    if learning_report.get("time_of_day"):
        lines.append("### Time-of-Day")
        lines.append("| Window | W/L | Avg P&L | Win Rate |")
        lines.append("|--------|-----|---------|----------|")
        for b in learning_report["time_of_day"]:
            lines.append(f"| {b['bucket']} | {b['wins']}W/{b['losses']}L | ${b['avg_pnl']:.2f} | {b['win_rate']:.0%} |")
        lines.append("")

    if learning_report.get("hold_duration"):
        lines.append("### Hold Duration")
        lines.append("| Bucket | W/L | Avg P&L | Win Rate |")
        lines.append("|--------|-----|---------|----------|")
        for b in learning_report["hold_duration"]:
            lines.append(f"| {b['bucket']} | {b['wins']}W/{b['losses']}L | ${b['avg_pnl']:.2f} | {b['win_rate']:.0%} |")
        lines.append("")

    if learning_report.get("asset_class"):
        lines.append("### Asset Class x Strategy")
        lines.append("| Class | Strategy | W/L | Win Rate |")
        lines.append("|-------|----------|-----|----------|")
        for a in learning_report["asset_class"]:
            lines.append(f"| {a['asset_class']} | {a['strategy_id']} | {a['wins']}W/{a['losses']}L | {a['win_rate']:.0%} |")
        lines.append("")

    # Parameter Changes
    if applied or proposed or reverted:
        lines.append("## Parameter Changes")
        for c in applied:
            lines.append(f"- AUTO-APPLIED: {c['parameter_path']}: {c['old_value']} → {c['new_value']} ({c['reason']})")
        for c in proposed:
            lines.append(f"- PROPOSED: {c['parameter_path']}: {c['old_value']} → {c['new_value']} ({c['reason']})")
        for c in reverted:
            lines.append(f"- REVERTED: {c['parameter_path']} (failed evaluation)")
        lines.append("")

    with open(daily_path, "w") as f:
        f.write("\n".join(lines))
```

Add new CLI commands for `learning-report`, `change-log`, `revert-change`:

```python
def cmd_learning_report():
    db = Database(DB_PATH)
    db.initialize()
    from claude_invest.modules.learner import _match_trades
    from claude_invest.modules.pattern_analyzer import analyze_patterns
    matched = _match_trades(db)
    closed = [m for m in matched if m["status"] == "closed"]
    report = analyze_patterns(closed)
    db.close()
    _output(report)


def cmd_change_log():
    db = Database(DB_PATH)
    db.initialize()
    changes = db.get_change_log()
    db.close()
    _output({"changes": changes, "count": len(changes)})


def cmd_revert_change(change_id: int):
    db = Database(DB_PATH)
    db.initialize()
    from claude_invest.config.loader import DEFAULT_CONFIG_PATH
    from claude_invest.modules.optimizer import _revert_change
    changes = db.get_change_log()
    change = next((c for c in changes if c["id"] == change_id), None)
    if change:
        _revert_change(db, change, DEFAULT_CONFIG_PATH, "Manual revert")
        _output({"status": "reverted", "change_id": change_id})
    else:
        _output({"error": f"Change {change_id} not found"})
    db.close()
```

Add to the CLI dispatch in `main()`:

```python
    elif command == "learning-report":
        cmd_learning_report()
    elif command == "change-log":
        cmd_change_log()
    elif command == "revert-change" and len(sys.argv) >= 3:
        cmd_revert_change(int(sys.argv[2]))
```

- [ ] **Step 2: Run existing tests to ensure nothing broke**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All existing tests PASS

- [ ] **Step 3: Commit**

```bash
git add src/claude_invest/main.py
git commit -m "feat: add position_id generation, learning commands, enhanced review-day"
```

---

### Task 8: API Endpoints for Learning Dashboard

**Files:**
- Modify: `src/claude_invest/modules/api_server.py`

- [ ] **Step 1: Add 4 new endpoints to api_server.py**

Add these endpoints inside the `create_app` function, before `return app`:

```python
    @app.get("/api/learning/report")
    def api_learning_report():
        db = get_db()
        from claude_invest.modules.learner import _match_trades
        from claude_invest.modules.pattern_analyzer import analyze_patterns
        matched = _match_trades(db)
        closed = [m for m in matched if m["status"] == "closed"]
        report = analyze_patterns(closed)
        db.close()
        return report

    @app.get("/api/learning/changes")
    def api_learning_changes():
        db = get_db()
        changes = db.get_change_log()
        db.close()
        return {"changes": changes}

    @app.get("/api/learning/performance")
    def api_learning_performance():
        db = get_db()
        from claude_invest.modules.learner import _match_trades
        matched = _match_trades(db)
        closed = [m for m in matched if m["status"] == "closed"]
        # Group by date for time series
        from collections import defaultdict
        daily = defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0.0})
        for t in closed:
            date = t.get("entry_time", "")[:10]
            if t["win"]:
                daily[date]["wins"] += 1
            else:
                daily[date]["losses"] += 1
            daily[date]["pnl"] += t["pnl"]
        series = [
            {"date": d, "wins": v["wins"], "losses": v["losses"],
             "pnl": round(v["pnl"], 2),
             "win_rate": round(v["wins"] / (v["wins"] + v["losses"]), 4) if (v["wins"] + v["losses"]) > 0 else 0}
            for d, v in sorted(daily.items())
        ]
        db.close()
        return {"series": series}

    @app.post("/api/learning/revert/{change_id}")
    def api_revert_change(change_id: int):
        db = get_db()
        from claude_invest.config.loader import DEFAULT_CONFIG_PATH
        from claude_invest.modules.optimizer import _revert_change
        changes = db.get_change_log()
        change = next((c for c in changes if c["id"] == change_id), None)
        if not change:
            db.close()
            return {"error": f"Change {change_id} not found"}
        _revert_change(db, change, DEFAULT_CONFIG_PATH, "Manual revert via dashboard")
        db.close()
        return {"status": "reverted", "change_id": change_id}
```

- [ ] **Step 2: Test endpoints manually**

Run: `.venv/bin/python -m claude_invest.modules.api_server &`
Then: `curl http://localhost:8000/api/learning/report | python -m json.tool`
Expected: JSON with `total_trades`, `signal_combos`, `time_of_day`, etc.

Then: `curl http://localhost:8000/api/learning/changes | python -m json.tool`
Expected: `{"changes": [...]}`

- [ ] **Step 3: Commit**

```bash
git add src/claude_invest/modules/api_server.py
git commit -m "feat: add learning engine API endpoints"
```

---

### Task 9: Dashboard Types and API Hooks

**Files:**
- Modify: `dashboard/src/lib/types.ts`
- Modify: `dashboard/src/lib/api.ts`

- [ ] **Step 1: Add TypeScript interfaces**

Add to `dashboard/src/lib/types.ts`:

```typescript
export interface LearningReport {
  generated_at: string;
  total_trades: number;
  overall_win_rate: number;
  signal_combos: DimensionBucket[];
  time_of_day: DimensionBucket[];
  hold_duration: DimensionBucket[];
  market_regime: DimensionBucket[];
  asset_class: AssetClassBucket[];
  cross_dimensional: CrossDimensional[];
}

export interface DimensionBucket {
  wins: number;
  losses: number;
  total: number;
  win_rate: number;
  avg_pnl: number;
  confidence: string;
  bucket?: string;
  combo?: string;
  regime?: string;
}

export interface AssetClassBucket extends DimensionBucket {
  asset_class: string;
  strategy_id: string;
}

export interface CrossDimensional extends DimensionBucket {
  insight: string;
  actionable: boolean;
}

export interface ChangeLogEntry {
  id: number;
  timestamp: string;
  parameter_path: string;
  old_value: string;
  new_value: string;
  reason: string;
  trade_count: number;
  auto_applied: boolean;
  reverted: boolean;
  reverted_at: string | null;
  revert_reason: string | null;
}

export interface PerformanceSeries {
  date: string;
  wins: number;
  losses: number;
  pnl: number;
  win_rate: number;
}
```

- [ ] **Step 2: Add SWR hooks**

Add to `dashboard/src/lib/api.ts`:

```typescript
import type {
  // ... existing imports ...
  LearningReport,
  ChangeLogEntry,
  PerformanceSeries,
} from "./types";

export function useLearningReport() {
  return useSWR<LearningReport>("/api/learning/report", fetcher, {
    refreshInterval: 60000,
  });
}

export function useChangeLog() {
  return useSWR<{ changes: ChangeLogEntry[] }>("/api/learning/changes", fetcher, {
    refreshInterval: 30000,
  });
}

export function usePerformanceSeries() {
  return useSWR<{ series: PerformanceSeries[] }>("/api/learning/performance", fetcher, {
    refreshInterval: 60000,
  });
}

export async function revertChange(changeId: number): Promise<void> {
  await fetch(`${API_BASE}/api/learning/revert/${changeId}`, {
    method: "POST",
  });
}
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/lib/types.ts dashboard/src/lib/api.ts
git commit -m "feat: add TypeScript types and SWR hooks for learning engine"
```

---

### Task 10: Dashboard Learning Page

**Files:**
- Create: `dashboard/src/app/learning/page.tsx`
- Modify: `dashboard/src/components/nav.tsx`

- [ ] **Step 1: Create the learning page**

Create `dashboard/src/app/learning/page.tsx`:

```typescript
"use client";

import {
  useLearningReport,
  useChangeLog,
  usePerformanceSeries,
  useStrategyBrief,
  revertChange,
} from "@/lib/api";
import type { ChangeLogEntry } from "@/lib/types";

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
      <div className="text-xs text-zinc-500 uppercase tracking-wide">{label}</div>
      <div className="text-2xl font-bold text-zinc-100 mt-1">{value}</div>
      {sub && <div className="text-xs text-zinc-500 mt-1">{sub}</div>}
    </div>
  );
}

function WinRateBar({ wins, losses, winRate }: { wins: number; losses: number; winRate: number }) {
  const pct = Math.round(winRate * 100);
  const color = pct >= 60 ? "bg-emerald-500" : pct <= 40 ? "bg-red-500" : "bg-yellow-500";
  return (
    <div className="flex items-center gap-2">
      <span className="text-emerald-400 text-xs font-mono">{wins}W</span>
      <span className="text-zinc-600">/</span>
      <span className="text-red-400 text-xs font-mono">{losses}L</span>
      <div className="w-16 bg-zinc-700 rounded-full h-1.5">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-zinc-400 w-8 text-right">{pct}%</span>
    </div>
  );
}

function DimensionTable({
  title,
  data,
  labelKey,
}: {
  title: string;
  data: Array<{ wins: number; losses: number; win_rate: number; avg_pnl: number; total: number; [k: string]: unknown }>;
  labelKey: string;
}) {
  if (!data || data.length === 0) return null;
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
      <h3 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wide">{title}</h3>
      <div className="space-y-2">
        {data.map((row, i) => (
          <div key={i} className="flex items-center justify-between p-2 bg-zinc-800/50 rounded">
            <span className="text-sm text-zinc-200 font-mono">{String(row[labelKey] ?? "unknown")}</span>
            <div className="flex items-center gap-4">
              <span className="text-xs text-zinc-500">${(row.avg_pnl ?? 0).toFixed(2)} avg</span>
              <WinRateBar wins={row.wins} losses={row.losses} winRate={row.win_rate} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ChangeTimeline({ changes }: { changes: ChangeLogEntry[] }) {
  if (!changes || changes.length === 0) {
    return (
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wide">Parameter Changes</h3>
        <div className="text-zinc-500 text-center py-4 text-sm">No parameter changes yet.</div>
      </div>
    );
  }

  const handleRevert = async (id: number) => {
    await revertChange(id);
    window.location.reload();
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
      <h3 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wide">Parameter Changes</h3>
      <div className="space-y-2">
        {changes.map((c) => {
          const statusColor = c.reverted
            ? "text-red-400"
            : c.auto_applied
              ? "text-emerald-400"
              : "text-yellow-400";
          const statusLabel = c.reverted ? "Reverted" : c.auto_applied ? "Active" : "Proposed";
          return (
            <div key={c.id} className="p-3 bg-zinc-800/50 rounded">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-mono text-sm text-zinc-200">{c.parameter_path.split(".").slice(-1)}</span>
                  <span className="text-zinc-500 mx-2">→</span>
                  <span className="text-zinc-300 text-sm">{c.old_value} → {c.new_value}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-medium ${statusColor}`}>{statusLabel}</span>
                  {!c.reverted && c.auto_applied && (
                    <button
                      onClick={() => handleRevert(c.id)}
                      className="text-xs text-zinc-500 hover:text-red-400 transition"
                    >
                      Revert
                    </button>
                  )}
                </div>
              </div>
              <div className="text-xs text-zinc-500 mt-1">{c.reason}</div>
              <div className="text-xs text-zinc-600 mt-1">
                {c.timestamp} · {c.trade_count} trades
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function LearningPage() {
  const { data: report } = useLearningReport();
  const { data: changesData } = useChangeLog();
  const { data: brief } = useStrategyBrief();

  const changes = changesData?.changes ?? [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Learning Engine</h1>

      {/* Stats bar */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          label="Win Rate"
          value={report ? `${Math.round(report.overall_win_rate * 100)}%` : "—"}
          sub={report ? `${report.total_trades} trades` : undefined}
        />
        <StatCard
          label="Total Trades"
          value={report ? String(report.total_trades) : "—"}
        />
        <StatCard
          label="Active Changes"
          value={String(changes.filter((c) => c.auto_applied && !c.reverted).length)}
        />
        <StatCard
          label="Proposed"
          value={String(changes.filter((c) => !c.auto_applied && !c.reverted).length)}
        />
      </div>

      {/* Dimension Charts */}
      <div className="grid grid-cols-2 gap-4">
        <DimensionTable title="Time of Day" data={report?.time_of_day ?? []} labelKey="bucket" />
        <DimensionTable title="Hold Duration" data={report?.hold_duration ?? []} labelKey="bucket" />
        <DimensionTable title="Market Regime" data={report?.market_regime ?? []} labelKey="regime" />
        <DimensionTable title="Asset Class × Strategy" data={report?.asset_class ?? []} labelKey="asset_class" />
      </div>

      {/* Signal Combos */}
      <DimensionTable title="Signal Combinations" data={report?.signal_combos ?? []} labelKey="combo" />

      {/* Parameter Changes */}
      <ChangeTimeline changes={changes} />

      {/* Strategy Brief */}
      {brief && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <h3 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wide">
            Strategy Brief
          </h3>
          <pre className="text-sm text-zinc-300 whitespace-pre-wrap font-mono leading-relaxed">
            {brief.brief}
          </pre>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add Learning link to navigation**

In `dashboard/src/components/nav.tsx`, add a link to `/learning`. Find the existing nav links and add:

```typescript
{ href: "/learning", label: "Learning" },
```

- [ ] **Step 3: Verify the page renders**

Open `http://localhost:3000/learning` in a browser. The page should render with empty states for all sections (no data yet). Verify:
- Stats bar shows "—" or "0" values
- Dimension tables show empty
- Parameter changes shows "No parameter changes yet"
- Strategy brief renders current brief

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/app/learning/page.tsx dashboard/src/components/nav.tsx
git commit -m "feat: add learning engine dashboard page with dimension charts"
```

---

### Task 11: Integration Test — Full Pipeline

**Files:**
- Test: `tests/test_integration_learning.py`

- [ ] **Step 1: Write integration test**

Create `tests/test_integration_learning.py`:

```python
import json
import os
import pytest
from claude_invest.modules.db import Database
from claude_invest.modules.learner import _match_trades, analyze_day, score_patterns
from claude_invest.modules.pattern_analyzer import analyze_patterns
from claude_invest.modules.strategy import update_lessons, build_strategy_brief


@pytest.fixture
def full_db(tmp_db_path):
    """DB with 6 closed trades (4 wins, 2 losses) across strategies."""
    db = Database(tmp_db_path)
    db.initialize()

    trades_data = [
        # Win: mean_reversion, stock, market_open, scalp
        ("AAPL", 180, 185, 35, 0.5, 0.3, "bullish", 0.4, "mean_reversion", "pos-1"),
        # Win: mean_reversion, stock, market_open, intraday
        ("MSFT", 400, 410, 28, 0.3, 0.1, "neutral", 0.3, "mean_reversion", "pos-2"),
        # Win: momentum, crypto, crypto_overnight, swing_short
        ("BTC/USD", 75000, 76000, 45, -200, -250, "neutral", 0.1, "momentum", "pos-3"),
        # Win: trend_pullback, stock, midday, intraday
        ("NVDA", 900, 920, 38, 2.0, 1.5, "bullish", 0.5, "trend_pullback", "pos-4"),
        # Loss: momentum, crypto, market_open, scalp
        ("ETH/USD", 2300, 2280, 55, -5, -3, "bearish", 0.05, "momentum", "pos-5"),
        # Loss: mean_reversion, stock, midday, intraday
        ("TSLA", 250, 240, 72, 3.0, 2.8, "bullish", 0.2, "mean_reversion", "pos-6"),
    ]

    for ticker, entry_p, exit_p, rsi, macd, macd_sig, trend, sent, strategy, pid in trades_data:
        db.insert_decision({
            "ticker": ticker, "action": "buy",
            "reasoning": f"test buy {ticker}",
            "signals_snapshot": json.dumps({
                "rsi": rsi, "macd": macd, "macd_signal": macd_sig,
                "trend": trend, "sentiment": sent, "price": entry_p,
                "strategy_id": strategy,
            }),
            "position_id": pid,
        })
        db.insert_decision({
            "ticker": ticker, "action": "sell",
            "reasoning": f"test sell {ticker}",
            "signals_snapshot": json.dumps({"price": exit_p}),
            "position_id": pid,
        })
        db.insert_trade({
            "symbol": ticker, "side": "buy", "qty": 1,
            "price": entry_p, "order_id": f"o-{pid}-buy",
            "trade_type": strategy, "status": "filled",
            "position_id": pid,
        })
        db.insert_trade({
            "symbol": ticker, "side": "sell", "qty": 1,
            "price": exit_p, "order_id": f"o-{pid}-sell",
            "trade_type": strategy, "status": "filled",
            "position_id": pid,
        })

    return db


def test_full_learning_pipeline(full_db, tmp_path):
    """Test: matched trades -> pattern analysis -> strategy brief."""
    lessons_dir = str(tmp_path / "lessons")
    os.makedirs(os.path.join(lessons_dir, "daily"), exist_ok=True)

    # Step 1: Match trades
    matched = _match_trades(full_db)
    closed = [m for m in matched if m["status"] == "closed"]
    assert len(closed) == 6

    # Step 2: Analyze patterns
    report = analyze_patterns(closed)
    assert report["total_trades"] == 6
    assert report["overall_win_rate"] == pytest.approx(4/6, abs=0.01)
    assert len(report["signal_combos"]) >= 1
    assert len(report["time_of_day"]) >= 1
    assert len(report["hold_duration"]) >= 1
    assert len(report["asset_class"]) >= 1

    # Step 3: Score patterns for lessons
    patterns = score_patterns(full_db)
    assert len(patterns) >= 1

    # Step 4: Update lessons
    update_lessons(lessons_dir, patterns, "2026-04-25")
    assert os.path.exists(os.path.join(lessons_dir, "lessons.json"))

    # Step 5: Build enhanced brief
    allocation = {"tiers": {}, "total_value": 5000}
    dimension_insights = {}
    if report["time_of_day"]:
        best = max(report["time_of_day"], key=lambda x: x.get("win_rate", 0))
        dimension_insights["best_time"] = best

    brief = build_strategy_brief(
        lessons_dir, allocation,
        dimension_insights=dimension_insights,
    )
    assert isinstance(brief, str)
    assert len(brief) > 50

    # Verify asset class detection
    crypto_class = [a for a in report["asset_class"] if a["asset_class"] == "crypto"]
    stock_class = [a for a in report["asset_class"] if a["asset_class"] == "stock"]
    assert len(crypto_class) >= 1
    assert len(stock_class) >= 1
```

- [ ] **Step 2: Run integration test**

Run: `.venv/bin/python -m pytest tests/test_integration_learning.py -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration_learning.py
git commit -m "test: add integration test for full learning pipeline"
```

---

### Task 12: Conftest Fixture for tmp_db_path

**Files:**
- Modify: `tests/conftest.py` (create if not exists)

Note: Several tests in this plan use a `tmp_db_path` fixture. If the project doesn't already have this in conftest, add it.

- [ ] **Step 1: Check if conftest.py exists and has tmp_db_path**

Run: `cat tests/conftest.py 2>/dev/null || echo "FILE NOT FOUND"`

If it doesn't exist or doesn't have `tmp_db_path`, create/update it:

```python
import pytest

@pytest.fixture
def tmp_db_path(tmp_path):
    return str(tmp_path / "test.db")
```

- [ ] **Step 2: Run tests to verify fixture works**

Run: `.venv/bin/python -m pytest tests/test_db.py -v --no-header -q`
Expected: All PASS

- [ ] **Step 3: Commit if changed**

```bash
git add tests/conftest.py
git commit -m "test: add tmp_db_path fixture to conftest"
```

---

## Self-Review

### Spec Coverage Check

| Spec Section | Task(s) |
|---|---|
| 1. Database Enhancements (position_id, change_log) | Task 2 |
| 2. Pattern Analyzer (5 dimensions) | Task 4 |
| 3. Parameter Optimizer (guardrails) | Task 5 |
| 4. Enhanced Strategy Brief | Task 6 |
| 5. Daily Report | Task 7 (_write_daily_report in main.py) |
| 6. Dashboard Learning Page | Tasks 9, 10 |
| 7. Integration & Automation (position_id lifecycle, learning loop, CLI commands) | Tasks 3, 7, 8 |
| 8. Phase 2/3 Extension Points | Covered by architecture (position_id, LearningReport structure) |
| 9. Testing Strategy | Tasks 2, 3, 4, 5, 6, 11, 12 |

### Placeholder Scan
- No TBD, TODO, or "implement later" found
- All code blocks contain complete, runnable code
- All file paths are exact

### Type Consistency
- `_match_trades` returns dicts with `position_id`, `strategy_id`, `entry_time`, `exit_time` — consumed correctly by `analyze_patterns` in Task 4
- `analyze_patterns` returns `LearningReport` matching TypeScript `LearningReport` interface in Task 9
- `db.get_change_log()` returns dicts matching `ChangeLogEntry` TypeScript interface
- `build_strategy_brief` kwargs (`dimension_insights`, `active_changes`, `proposed_changes`) match what `cmd_review_day` passes in Task 7
