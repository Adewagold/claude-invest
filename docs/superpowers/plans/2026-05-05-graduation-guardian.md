# Trade Graduation & Core Guardian Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build automatic trade graduation (trading → core) and intelligent core holdings exit protection.

**Architecture:** Two new modules — `graduation.py` (gate logic when RSI > 80) and `core_guardian.py` (peak tracking + drawdown exits). New DB tables for graduations and peak prices. Config-driven thresholds. Integration into trading cron and core-cycle.

**Tech Stack:** Python 3.12, SQLite, ruamel.yaml (settings updates), pytest, existing Alpaca/sentiment/technicals modules.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/claude_invest/modules/graduation.py` | Graduation gate: criteria check, settings.yaml update, DB logging |
| `src/claude_invest/modules/core_guardian.py` | Peak tracking, drawdown calculation, tiered exits, crash override |
| `src/claude_invest/modules/db.py` | Add 2 tables + 6 new methods |
| `src/claude_invest/main.py` | Add `check-graduation` and `core-health` CLI commands |
| `src/claude_invest/config/settings.yaml` | Add graduation + core_guardian config sections |
| `src/claude_invest/modules/core_engine.py` | Call core_guardian after DCA |
| `src/claude_invest/modules/api_server.py` | Add `/api/graduations` and `/api/core/health` endpoints |
| `tests/test_graduation.py` | Unit tests for graduation logic |
| `tests/test_core_guardian.py` | Unit tests for guardian logic |

---

### Task 1: Database Schema & Methods

**Files:**
- Modify: `src/claude_invest/modules/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write failing tests for new DB methods**

```python
# Add to tests/test_db.py

def test_insert_and_get_graduation(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    entry = {
        "symbol": "SNDK",
        "entry_price": 913.86,
        "graduation_price": 1332.0,
        "hold_days": 16,
        "gain_pct": 0.457,
        "sentiment_score": 0.25,
    }
    db.insert_graduation(entry)
    results = db.get_graduations()
    assert len(results) == 1
    assert results[0]["symbol"] == "SNDK"
    assert results[0]["status"] == "probation"


def test_update_graduation_status(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    db.insert_graduation({
        "symbol": "MU",
        "entry_price": 565.0,
        "graduation_price": 645.0,
        "hold_days": 10,
        "gain_pct": 0.14,
        "sentiment_score": 0.20,
    })
    grads = db.get_graduations()
    db.update_graduation_status(grads[0]["id"], "promoted")
    updated = db.get_graduations()
    assert updated[0]["status"] == "promoted"
    assert updated[0]["promoted_at"] is not None


def test_upsert_and_get_core_peak(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    db.upsert_core_peak("NVDA", 200.0, "2026-05-01")
    peak = db.get_core_peak("NVDA")
    assert peak["peak_price"] == 200.0

    # Update to higher price
    db.upsert_core_peak("NVDA", 210.0, "2026-05-05")
    peak = db.get_core_peak("NVDA")
    assert peak["peak_price"] == 210.0


def test_get_all_core_peaks(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    db.upsert_core_peak("NVDA", 200.0, "2026-05-01")
    db.upsert_core_peak("AAPL", 285.0, "2026-05-01")
    peaks = db.get_all_core_peaks()
    assert len(peaks) == 2


def test_get_graduation_by_symbol(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    db.insert_graduation({
        "symbol": "SNDK",
        "entry_price": 913.86,
        "graduation_price": 1332.0,
        "hold_days": 16,
        "gain_pct": 0.457,
        "sentiment_score": 0.25,
    })
    result = db.get_graduation_by_symbol("SNDK")
    assert result is not None
    assert result["symbol"] == "SNDK"
    assert db.get_graduation_by_symbol("FAKE") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_db.py::test_insert_and_get_graduation tests/test_db.py::test_update_graduation_status tests/test_db.py::test_upsert_and_get_core_peak tests/test_db.py::test_get_all_core_peaks tests/test_db.py::test_get_graduation_by_symbol -v`
Expected: FAIL with AttributeError (methods don't exist)

- [ ] **Step 3: Add tables to db.py initialize()**

In `db.py`, add these tables to the `executescript` block in `initialize()`:

```python
            CREATE TABLE IF NOT EXISTS graduations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                symbol TEXT NOT NULL,
                entry_price REAL NOT NULL,
                graduation_price REAL NOT NULL,
                hold_days INTEGER NOT NULL,
                gain_pct REAL NOT NULL,
                sentiment_score REAL,
                status TEXT DEFAULT 'probation',
                promoted_at TEXT,
                demoted_at TEXT
            );

            CREATE TABLE IF NOT EXISTS core_peaks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                peak_price REAL NOT NULL,
                peak_date TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
```

- [ ] **Step 4: Add DB methods to db.py**

```python
    def insert_graduation(self, entry: dict):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO graduations (symbol, entry_price, graduation_price, hold_days, gain_pct, sentiment_score) VALUES (?, ?, ?, ?, ?, ?)",
            (entry["symbol"], entry["entry_price"], entry["graduation_price"],
             entry["hold_days"], entry["gain_pct"], entry.get("sentiment_score")),
        )
        conn.commit()

    def get_graduations(self, status: str | None = None) -> list[dict]:
        conn = self._get_conn()
        if status:
            cursor = conn.execute(
                "SELECT * FROM graduations WHERE status = ? ORDER BY timestamp DESC", (status,)
            )
        else:
            cursor = conn.execute("SELECT * FROM graduations ORDER BY timestamp DESC")
        return [dict(row) for row in cursor.fetchall()]

    def get_graduation_by_symbol(self, symbol: str) -> dict | None:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM graduations WHERE symbol = ? AND status IN ('probation', 'promoted') ORDER BY timestamp DESC LIMIT 1",
            (symbol,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_graduation_status(self, graduation_id: int, status: str):
        conn = self._get_conn()
        if status == "promoted":
            conn.execute(
                "UPDATE graduations SET status=?, promoted_at=datetime('now') WHERE id=?",
                (status, graduation_id),
            )
        elif status == "demoted":
            conn.execute(
                "UPDATE graduations SET status=?, demoted_at=datetime('now') WHERE id=?",
                (status, graduation_id),
            )
        else:
            conn.execute("UPDATE graduations SET status=? WHERE id=?", (status, graduation_id))
        conn.commit()

    def upsert_core_peak(self, symbol: str, price: float, date: str):
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO core_peaks (symbol, peak_price, peak_date, updated_at)
               VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT(symbol) DO UPDATE SET
                 peak_price = excluded.peak_price,
                 peak_date = excluded.peak_date,
                 updated_at = datetime('now')
               WHERE excluded.peak_price > core_peaks.peak_price""",
            (symbol, price, date),
        )
        conn.commit()

    def get_core_peak(self, symbol: str) -> dict | None:
        conn = self._get_conn()
        cursor = conn.execute("SELECT * FROM core_peaks WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_core_peaks(self) -> list[dict]:
        conn = self._get_conn()
        cursor = conn.execute("SELECT * FROM core_peaks ORDER BY symbol")
        return [dict(row) for row in cursor.fetchall()]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_db.py::test_insert_and_get_graduation tests/test_db.py::test_update_graduation_status tests/test_db.py::test_upsert_and_get_core_peak tests/test_db.py::test_get_all_core_peaks tests/test_db.py::test_get_graduation_by_symbol -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/claude_invest/modules/db.py tests/test_db.py
git commit -m "feat: add graduations and core_peaks DB tables and methods"
```

---

### Task 2: Configuration

**Files:**
- Modify: `src/claude_invest/config/settings.yaml`

- [ ] **Step 1: Add graduation and core_guardian config sections**

Append to end of `settings.yaml`:

```yaml
graduation:
  min_hold_days: 5
  min_gain_pct: 0.10
  min_sentiment: 0.15
  min_articles: 3
  probation_days: 30
  probation_weight: 0.035

core_guardian:
  warning_drawdown: -0.15
  reduce_drawdown: -0.25
  exit_drawdown: -0.35
  warning_days: 5
  reduce_days: 10
  crash_override_threshold: -0.10
  probation_tighter_factor: 0.67
```

- [ ] **Step 2: Commit**

```bash
git add src/claude_invest/config/settings.yaml
git commit -m "feat: add graduation and core_guardian config"
```

---

### Task 3: Graduation Module

**Files:**
- Create: `src/claude_invest/modules/graduation.py`
- Test: `tests/test_graduation.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_graduation.py
import pytest
from unittest.mock import patch, MagicMock
from claude_invest.modules.db import Database
from claude_invest.modules.graduation import check_graduation


@pytest.fixture
def grad_config():
    return {
        "capital": 5000,
        "capital_split": {"core": 0.5, "trading": 0.5},
        "core_holdings": {
            "buy_list": [
                {"symbol": "NVDA", "sector": "tech", "weight": 0.071},
                {"symbol": "AAPL", "sector": "tech", "weight": 0.071},
            ],
            "entry": {"dca_interval_days": 7, "max_per_buy": 0.02},
            "max_positions": 15,
        },
        "graduation": {
            "min_hold_days": 5,
            "min_gain_pct": 0.10,
            "min_sentiment": 0.15,
            "min_articles": 3,
            "probation_days": 30,
            "probation_weight": 0.035,
        },
    }


@pytest.fixture
def grad_db(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    return db


def test_graduation_all_criteria_pass(grad_config, grad_db):
    """Stock held 10 days, +15% gain, good sentiment, above SMA20 -> graduate."""
    portfolio = {
        "positions": [
            {"symbol": "MU", "qty": 4, "avg_entry_price": 565.0,
             "current_price": 650.0, "market_value": 2600.0, "unrealized_pl": 340.0}
        ]
    }
    # Mock: position entered 10 days ago
    grad_db.insert_trade({
        "symbol": "MU", "side": "buy", "qty": 4, "price": 565.0,
        "order_id": "test1", "trade_type": "momentum", "status": "filled",
    })

    with patch("claude_invest.modules.graduation.analyze_sentiment") as mock_sent, \
         patch("claude_invest.modules.graduation.analyze_technicals") as mock_tech, \
         patch("claude_invest.modules.graduation._get_hold_days", return_value=10):
        mock_sent.return_value = {"score": 0.25, "article_count": 5}
        mock_tech.return_value = {"current_price": 650.0, "sma_20": 620.0}

        result = check_graduation("MU", grad_config, grad_db, portfolio)

    assert result["decision"] == "graduate"


def test_graduation_insufficient_hold_days(grad_config, grad_db):
    """Stock held only 2 days -> sell."""
    portfolio = {
        "positions": [
            {"symbol": "MU", "qty": 4, "avg_entry_price": 565.0,
             "current_price": 650.0, "market_value": 2600.0, "unrealized_pl": 340.0}
        ]
    }

    with patch("claude_invest.modules.graduation.analyze_sentiment") as mock_sent, \
         patch("claude_invest.modules.graduation.analyze_technicals") as mock_tech, \
         patch("claude_invest.modules.graduation._get_hold_days", return_value=2):
        mock_sent.return_value = {"score": 0.25, "article_count": 5}
        mock_tech.return_value = {"current_price": 650.0, "sma_20": 620.0}

        result = check_graduation("MU", grad_config, grad_db, portfolio)

    assert result["decision"] == "sell"
    assert "hold" in result["reason"].lower()


def test_graduation_low_sentiment(grad_config, grad_db):
    """Good gain but sentiment below threshold -> sell."""
    portfolio = {
        "positions": [
            {"symbol": "MU", "qty": 4, "avg_entry_price": 565.0,
             "current_price": 650.0, "market_value": 2600.0, "unrealized_pl": 340.0}
        ]
    }

    with patch("claude_invest.modules.graduation.analyze_sentiment") as mock_sent, \
         patch("claude_invest.modules.graduation.analyze_technicals") as mock_tech, \
         patch("claude_invest.modules.graduation._get_hold_days", return_value=10):
        mock_sent.return_value = {"score": 0.05, "article_count": 1}
        mock_tech.return_value = {"current_price": 650.0, "sma_20": 620.0}

        result = check_graduation("MU", grad_config, grad_db, portfolio)

    assert result["decision"] == "sell"
    assert "sentiment" in result["reason"].lower()


def test_graduation_below_sma20(grad_config, grad_db):
    """Price below SMA20 -> sell (crashing after spike)."""
    portfolio = {
        "positions": [
            {"symbol": "MU", "qty": 4, "avg_entry_price": 565.0,
             "current_price": 610.0, "market_value": 2440.0, "unrealized_pl": 180.0}
        ]
    }

    with patch("claude_invest.modules.graduation.analyze_sentiment") as mock_sent, \
         patch("claude_invest.modules.graduation.analyze_technicals") as mock_tech, \
         patch("claude_invest.modules.graduation._get_hold_days", return_value=10):
        mock_sent.return_value = {"score": 0.25, "article_count": 5}
        mock_tech.return_value = {"current_price": 610.0, "sma_20": 630.0}

        result = check_graduation("MU", grad_config, grad_db, portfolio)

    assert result["decision"] == "sell"
    assert "sma" in result["reason"].lower() or "trend" in result["reason"].lower()


def test_graduation_insufficient_gain(grad_config, grad_db):
    """Held long enough but only 5% gain -> sell."""
    portfolio = {
        "positions": [
            {"symbol": "MU", "qty": 4, "avg_entry_price": 620.0,
             "current_price": 651.0, "market_value": 2604.0, "unrealized_pl": 124.0}
        ]
    }

    with patch("claude_invest.modules.graduation.analyze_sentiment") as mock_sent, \
         patch("claude_invest.modules.graduation.analyze_technicals") as mock_tech, \
         patch("claude_invest.modules.graduation._get_hold_days", return_value=10):
        mock_sent.return_value = {"score": 0.25, "article_count": 5}
        mock_tech.return_value = {"current_price": 651.0, "sma_20": 620.0}

        result = check_graduation("MU", grad_config, grad_db, portfolio)

    assert result["decision"] == "sell"
    assert "gain" in result["reason"].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_graduation.py -v`
Expected: FAIL (module doesn't exist)

- [ ] **Step 3: Implement graduation.py**

```python
# src/claude_invest/modules/graduation.py
"""
Trade Graduation Engine
=======================
When a trading position hits RSI > 80 (sell trigger), checks if the stock
should graduate to core holdings instead of being sold.

Criteria: hold_days >= 5, gain >= 10%, sentiment > 0.15 with 3+ articles,
price above 20-day SMA.
"""
import logging
from datetime import datetime, timezone

from ruamel.yaml import YAML

from claude_invest.modules.db import Database
from claude_invest.modules.sentiment import analyze_sentiment
from claude_invest.modules.technicals import analyze_technicals

logger = logging.getLogger(__name__)


def _get_hold_days(symbol: str, db: Database) -> int:
    """Get days since first buy of this symbol in current position."""
    trades = db.get_trades(symbol=symbol, limit=100)
    buys = [t for t in trades if t["side"] == "buy"]
    if not buys:
        return 0
    # Oldest buy (last in list since ordered DESC)
    oldest_buy = buys[-1]
    buy_dt = datetime.fromisoformat(oldest_buy["timestamp"])
    if buy_dt.tzinfo is None:
        buy_dt = buy_dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - buy_dt).days


def check_graduation(symbol: str, config: dict, db: Database, portfolio: dict) -> dict:
    """Check if a trading position should graduate to core holdings.

    Args:
        symbol: Ticker symbol to evaluate
        config: Full settings config
        db: Database instance
        portfolio: Current portfolio state

    Returns:
        {"decision": "graduate"|"sell", "reason": str, "criteria": dict}
    """
    grad_cfg = config.get("graduation", {})
    min_hold_days = grad_cfg.get("min_hold_days", 5)
    min_gain_pct = grad_cfg.get("min_gain_pct", 0.10)
    min_sentiment = grad_cfg.get("min_sentiment", 0.15)
    min_articles = grad_cfg.get("min_articles", 3)

    # Find position in portfolio
    position = None
    for p in portfolio.get("positions", []):
        if p["symbol"] == symbol:
            position = p
            break

    if not position:
        return {"decision": "sell", "reason": "Position not found in portfolio", "criteria": {}}

    # Criterion 1: Hold duration
    hold_days = _get_hold_days(symbol, db)
    if hold_days < min_hold_days:
        return {
            "decision": "sell",
            "reason": f"Insufficient hold days: {hold_days} < {min_hold_days}",
            "criteria": {"hold_days": hold_days, "min_required": min_hold_days},
        }

    # Criterion 2: Profit threshold
    gain_pct = position["unrealized_pl"] / (position["qty"] * position["avg_entry_price"])
    if gain_pct < min_gain_pct:
        return {
            "decision": "sell",
            "reason": f"Insufficient gain: {gain_pct:.1%} < {min_gain_pct:.0%}",
            "criteria": {"gain_pct": gain_pct, "min_required": min_gain_pct},
        }

    # Criterion 3: Sentiment
    try:
        sentiment = analyze_sentiment(symbol)
    except Exception as e:
        logger.warning("Sentiment check failed for %s: %s", symbol, e)
        return {"decision": "sell", "reason": f"Sentiment check failed: {e}", "criteria": {}}

    score = sentiment.get("score", 0)
    articles = sentiment.get("article_count", 0)
    if score < min_sentiment or articles < min_articles:
        return {
            "decision": "sell",
            "reason": f"Low sentiment: score={score:.2f} (need {min_sentiment}), articles={articles} (need {min_articles})",
            "criteria": {"sentiment_score": score, "article_count": articles},
        }

    # Criterion 4: Price above SMA20
    try:
        tech = analyze_technicals(symbol)
    except Exception as e:
        logger.warning("Technicals check failed for %s: %s", symbol, e)
        return {"decision": "sell", "reason": f"Technicals check failed: {e}", "criteria": {}}

    current_price = tech.get("current_price", 0)
    sma_20 = tech.get("sma_20", 0)
    if sma_20 and current_price < sma_20:
        return {
            "decision": "sell",
            "reason": f"Price below SMA20: ${current_price:.2f} < ${sma_20:.2f} (trend weakening)",
            "criteria": {"price": current_price, "sma_20": sma_20},
        }

    # ALL CRITERIA PASS -> Graduate
    criteria = {
        "hold_days": hold_days,
        "gain_pct": gain_pct,
        "sentiment_score": score,
        "article_count": articles,
        "price": current_price,
        "sma_20": sma_20,
    }

    return {"decision": "graduate", "reason": "All graduation criteria met", "criteria": criteria}


def execute_graduation(symbol: str, config: dict, db: Database, portfolio: dict, config_path: str) -> dict:
    """Execute the graduation: add to buy_list, record in DB.

    Args:
        symbol: Ticker to graduate
        config: Full settings config
        db: Database instance
        portfolio: Current portfolio state
        config_path: Path to settings.yaml for updating

    Returns:
        dict with graduation details
    """
    grad_cfg = config.get("graduation", {})
    probation_weight = grad_cfg.get("probation_weight", 0.035)

    # Find position details
    position = None
    for p in portfolio.get("positions", []):
        if p["symbol"] == symbol:
            position = p
            break

    if not position:
        return {"error": "Position not found"}

    entry_price = position["avg_entry_price"]
    graduation_price = position["current_price"]
    hold_days = _get_hold_days(symbol, db)
    gain_pct = position["unrealized_pl"] / (position["qty"] * entry_price)

    # Get sentiment for record
    try:
        sentiment = analyze_sentiment(symbol)
        sentiment_score = sentiment.get("score", 0)
    except Exception:
        sentiment_score = None

    # Determine sector (default to "general" if unknown)
    sector = "general"

    # Record in DB
    db.insert_graduation({
        "symbol": symbol,
        "entry_price": entry_price,
        "graduation_price": graduation_price,
        "hold_days": hold_days,
        "gain_pct": gain_pct,
        "sentiment_score": sentiment_score,
    })

    # Update settings.yaml - add to buy_list at probation weight
    _add_to_buy_list(config_path, symbol, sector, probation_weight)

    logger.info(
        "GRADUATED %s: held %d days, +%.1f%%, sentiment %.2f. Added to core at %.1f%% weight.",
        symbol, hold_days, gain_pct * 100, sentiment_score or 0, probation_weight * 100,
    )

    return {
        "symbol": symbol,
        "entry_price": entry_price,
        "graduation_price": graduation_price,
        "hold_days": hold_days,
        "gain_pct": gain_pct,
        "sentiment_score": sentiment_score,
        "status": "probation",
        "weight": probation_weight,
    }


def _add_to_buy_list(config_path: str, symbol: str, sector: str, weight: float):
    """Add a symbol to core_holdings.buy_list in settings.yaml."""
    yaml = YAML()
    yaml.preserve_quotes = True

    with open(config_path, "r") as f:
        data = yaml.load(f)

    buy_list = data.get("core_holdings", {}).get("buy_list", [])

    # Check if already in list
    existing_symbols = {item["symbol"] for item in buy_list}
    if symbol in existing_symbols:
        return

    # Add new entry
    buy_list.append({"symbol": symbol, "sector": sector, "weight": weight})
    data["core_holdings"]["buy_list"] = buy_list

    with open(config_path, "w") as f:
        yaml.dump(data, f)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_graduation.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/claude_invest/modules/graduation.py tests/test_graduation.py
git commit -m "feat: add graduation module with criteria gate"
```

---

### Task 4: Core Guardian Module

**Files:**
- Create: `src/claude_invest/modules/core_guardian.py`
- Test: `tests/test_core_guardian.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_core_guardian.py
import pytest
from unittest.mock import patch
from claude_invest.modules.db import Database
from claude_invest.modules.core_guardian import (
    update_peaks,
    check_core_health,
    check_probation_promotions,
)


@pytest.fixture
def guardian_config():
    return {
        "capital": 5000,
        "capital_split": {"core": 0.5, "trading": 0.5},
        "core_holdings": {
            "buy_list": [
                {"symbol": "NVDA", "sector": "tech", "weight": 0.071},
                {"symbol": "SPY", "sector": "etf", "weight": 0.071},
            ],
        },
        "core_guardian": {
            "warning_drawdown": -0.15,
            "reduce_drawdown": -0.25,
            "exit_drawdown": -0.35,
            "warning_days": 5,
            "reduce_days": 10,
            "crash_override_threshold": -0.10,
            "probation_tighter_factor": 0.67,
        },
        "graduation": {
            "probation_days": 30,
        },
    }


@pytest.fixture
def guardian_db(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    return db


def test_update_peaks_sets_new_peak(guardian_config, guardian_db):
    """First time seeing a symbol sets the peak."""
    portfolio = {
        "positions": [
            {"symbol": "NVDA", "current_price": 200.0, "market_value": 200.0, "qty": 1, "avg_entry_price": 180.0, "unrealized_pl": 20.0},
        ]
    }
    update_peaks(guardian_db, portfolio, {"NVDA"})
    peak = guardian_db.get_core_peak("NVDA")
    assert peak["peak_price"] == 200.0


def test_update_peaks_only_increases(guardian_config, guardian_db):
    """Peak should not decrease."""
    guardian_db.upsert_core_peak("NVDA", 210.0, "2026-05-01")
    portfolio = {
        "positions": [
            {"symbol": "NVDA", "current_price": 195.0, "market_value": 195.0, "qty": 1, "avg_entry_price": 180.0, "unrealized_pl": 15.0},
        ]
    }
    update_peaks(guardian_db, portfolio, {"NVDA"})
    peak = guardian_db.get_core_peak("NVDA")
    assert peak["peak_price"] == 210.0  # Unchanged


def test_no_action_within_thresholds(guardian_config, guardian_db):
    """No drawdown -> no action."""
    guardian_db.upsert_core_peak("NVDA", 200.0, "2026-05-01")
    portfolio = {
        "positions": [
            {"symbol": "NVDA", "current_price": 195.0, "market_value": 195.0, "qty": 1, "avg_entry_price": 180.0, "unrealized_pl": 15.0},
            {"symbol": "SPY", "current_price": 720.0, "market_value": 720.0, "qty": 1, "avg_entry_price": 700.0, "unrealized_pl": 20.0},
        ]
    }
    guardian_db.upsert_core_peak("SPY", 725.0, "2026-05-01")

    result = check_core_health(guardian_config, guardian_db, portfolio)
    assert result["warnings"] == []
    assert result["trims"] == []
    assert result["exits"] == []
    assert result["crash_override"] is False


def test_warning_at_15pct_drawdown(guardian_config, guardian_db):
    """15% drawdown for 5+ days triggers warning."""
    guardian_db.upsert_core_peak("NVDA", 200.0, "2026-04-25")  # Peak set 10 days ago
    guardian_db.upsert_core_peak("SPY", 725.0, "2026-05-01")
    portfolio = {
        "positions": [
            {"symbol": "NVDA", "current_price": 168.0, "market_value": 168.0, "qty": 1, "avg_entry_price": 180.0, "unrealized_pl": -12.0},
            {"symbol": "SPY", "current_price": 720.0, "market_value": 720.0, "qty": 1, "avg_entry_price": 700.0, "unrealized_pl": 20.0},
        ]
    }

    with patch("claude_invest.modules.core_guardian._days_since_peak", return_value=6):
        result = check_core_health(guardian_config, guardian_db, portfolio)

    assert len(result["warnings"]) == 1
    assert result["warnings"][0]["symbol"] == "NVDA"


def test_crash_override_suspends_exits(guardian_config, guardian_db):
    """When SPY is down >10%, suspend all individual exits."""
    guardian_db.upsert_core_peak("NVDA", 200.0, "2026-04-25")
    guardian_db.upsert_core_peak("SPY", 800.0, "2026-04-01")  # SPY peak at 800
    portfolio = {
        "positions": [
            {"symbol": "NVDA", "current_price": 130.0, "market_value": 130.0, "qty": 1, "avg_entry_price": 180.0, "unrealized_pl": -50.0},
            {"symbol": "SPY", "current_price": 700.0, "market_value": 700.0, "qty": 1, "avg_entry_price": 700.0, "unrealized_pl": 0.0},
        ]
    }

    with patch("claude_invest.modules.core_guardian._days_since_peak", return_value=15):
        result = check_core_health(guardian_config, guardian_db, portfolio)

    assert result["crash_override"] is True
    assert result["exits"] == []
    assert result["trims"] == []


def test_probation_promotion_after_30_days(guardian_config, guardian_db):
    """Stock in probation for 30+ days without hitting -15% gets promoted."""
    guardian_db.insert_graduation({
        "symbol": "MU",
        "entry_price": 565.0,
        "graduation_price": 645.0,
        "hold_days": 10,
        "gain_pct": 0.14,
        "sentiment_score": 0.20,
    })
    # Manually set timestamp to 35 days ago
    conn = guardian_db._get_conn()
    conn.execute(
        "UPDATE graduations SET timestamp = datetime('now', '-35 days') WHERE symbol = 'MU'"
    )
    conn.commit()

    guardian_db.upsert_core_peak("MU", 660.0, "2026-04-10")

    portfolio = {
        "positions": [
            {"symbol": "MU", "current_price": 650.0, "market_value": 650.0, "qty": 1, "avg_entry_price": 565.0, "unrealized_pl": 85.0},
        ]
    }

    promotions = check_probation_promotions(guardian_config, guardian_db, portfolio)
    assert len(promotions) == 1
    assert promotions[0]["symbol"] == "MU"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_core_guardian.py -v`
Expected: FAIL (module doesn't exist)

- [ ] **Step 3: Implement core_guardian.py**

```python
# src/claude_invest/modules/core_guardian.py
"""
Core Guardian
=============
Intelligent exit logic for core holdings. Tracks peak prices, monitors
sustained drawdowns, and protects against losses without panic selling.

Uses market crash override (SPY > -10%) to suspend exits during corrections.
"""
import logging
from datetime import datetime, timezone

from claude_invest.modules.db import Database
from claude_invest.modules.executor import execute_order

logger = logging.getLogger(__name__)


def _days_since_peak(db: Database, symbol: str) -> int:
    """Days since the peak price was recorded."""
    peak = db.get_core_peak(symbol)
    if not peak:
        return 0
    peak_dt = datetime.fromisoformat(peak["peak_date"])
    if peak_dt.tzinfo is None:
        peak_dt = peak_dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - peak_dt).days


def update_peaks(db: Database, portfolio: dict, core_symbols: set):
    """Update peak prices for all core holdings.

    Only increases peak — never decreases.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for pos in portfolio.get("positions", []):
        if pos["symbol"] in core_symbols:
            db.upsert_core_peak(pos["symbol"], pos["current_price"], today)


def check_core_health(config: dict, db: Database, portfolio: dict) -> dict:
    """Run smart exit checks for all core holdings.

    Returns:
        {"warnings": [...], "trims": [...], "exits": [...], "crash_override": bool}
    """
    guardian_cfg = config.get("core_guardian", {})
    warning_drawdown = guardian_cfg.get("warning_drawdown", -0.15)
    reduce_drawdown = guardian_cfg.get("reduce_drawdown", -0.25)
    exit_drawdown = guardian_cfg.get("exit_drawdown", -0.35)
    warning_days = guardian_cfg.get("warning_days", 5)
    reduce_days = guardian_cfg.get("reduce_days", 10)
    crash_threshold = guardian_cfg.get("crash_override_threshold", -0.10)
    probation_factor = guardian_cfg.get("probation_tighter_factor", 0.67)

    core_cfg = config.get("core_holdings", {})
    buy_list_symbols = {item["symbol"] for item in core_cfg.get("buy_list", [])}

    warnings = []
    trims = []
    exits = []

    # Check SPY for market crash override
    spy_peak = db.get_core_peak("SPY")
    spy_pos = None
    for p in portfolio.get("positions", []):
        if p["symbol"] == "SPY":
            spy_pos = p
            break

    crash_override = False
    if spy_peak and spy_pos:
        spy_drawdown = (spy_pos["current_price"] - spy_peak["peak_price"]) / spy_peak["peak_price"]
        if spy_drawdown < crash_threshold:
            crash_override = True
            logger.info("CRASH OVERRIDE: SPY drawdown %.1f%% > %.1f%% threshold. Suspending exits.",
                       spy_drawdown * 100, crash_threshold * 100)

    if crash_override:
        return {"warnings": [], "trims": [], "exits": [], "crash_override": True}

    # Check each core holding
    for pos in portfolio.get("positions", []):
        symbol = pos["symbol"]
        if symbol not in buy_list_symbols or symbol == "SPY":
            continue

        peak = db.get_core_peak(symbol)
        if not peak:
            continue

        drawdown = (pos["current_price"] - peak["peak_price"]) / peak["peak_price"]
        days_since = _days_since_peak(db, symbol)

        # Check if this is a probationary stock (tighter thresholds)
        graduation = db.get_graduation_by_symbol(symbol)
        is_probation = graduation is not None and graduation["status"] == "probation"

        effective_warning = warning_drawdown * probation_factor if is_probation else warning_drawdown
        effective_reduce = reduce_drawdown * probation_factor if is_probation else reduce_drawdown
        effective_exit = exit_drawdown * probation_factor if is_probation else exit_drawdown

        # Tier 3: Full exit (-35% or -23% for probation)
        if drawdown <= effective_exit:
            qty = pos["qty"]
            order = execute_order(symbol, "sell", qty)
            exits.append({
                "symbol": symbol,
                "drawdown": drawdown,
                "days_since_peak": days_since,
                "qty": qty,
                "order": order,
                "probation": is_probation,
            })
            logger.info("CORE EXIT: %s drawdown %.1f%% (threshold %.1f%%). Full sell.",
                       symbol, drawdown * 100, effective_exit * 100)

            # If probation, demote
            if is_probation and graduation:
                db.update_graduation_status(graduation["id"], "demoted")
            continue

        # Tier 2: Reduce 50% (-25% sustained 10+ days, or -17% for probation)
        if drawdown <= effective_reduce and days_since >= reduce_days:
            qty_to_sell = pos["qty"] * 0.5
            order = execute_order(symbol, "sell", qty_to_sell)
            trims.append({
                "symbol": symbol,
                "drawdown": drawdown,
                "days_since_peak": days_since,
                "qty_sold": qty_to_sell,
                "order": order,
                "probation": is_probation,
            })
            logger.info("CORE REDUCE: %s drawdown %.1f%% for %d days. Selling 50%%.",
                       symbol, drawdown * 100, days_since)

            # If probation, demote
            if is_probation and graduation:
                db.update_graduation_status(graduation["id"], "demoted")
            continue

        # Tier 1: Warning (-15% sustained 5+ days, or -10% for probation)
        if drawdown <= effective_warning and days_since >= warning_days:
            warnings.append({
                "symbol": symbol,
                "drawdown": drawdown,
                "days_since_peak": days_since,
                "probation": is_probation,
            })
            logger.info("CORE WARNING: %s drawdown %.1f%% for %d days.",
                       symbol, drawdown * 100, days_since)

    return {
        "warnings": warnings,
        "trims": trims,
        "exits": exits,
        "crash_override": crash_override,
    }


def check_probation_promotions(config: dict, db: Database, portfolio: dict) -> list[dict]:
    """Check if any probationary stocks should be promoted to full weight.

    Criteria: 30+ days in probation without hitting -15% from graduation price.
    """
    grad_cfg = config.get("graduation", {})
    probation_days = grad_cfg.get("probation_days", 30)

    graduations = db.get_graduations(status="probation")
    promotions = []

    for grad in graduations:
        grad_dt = datetime.fromisoformat(grad["timestamp"])
        if grad_dt.tzinfo is None:
            grad_dt = grad_dt.replace(tzinfo=timezone.utc)

        days_in_probation = (datetime.now(timezone.utc) - grad_dt).days
        if days_in_probation < probation_days:
            continue

        # Check if position still exists and hasn't crashed
        symbol = grad["symbol"]
        peak = db.get_core_peak(symbol)
        pos = None
        for p in portfolio.get("positions", []):
            if p["symbol"] == symbol:
                pos = p
                break

        if not pos or not peak:
            continue

        drawdown = (pos["current_price"] - peak["peak_price"]) / peak["peak_price"]
        if drawdown > -0.15:  # Hasn't hit -15% from peak
            db.update_graduation_status(grad["id"], "promoted")
            promotions.append({
                "symbol": symbol,
                "days_in_probation": days_in_probation,
                "current_drawdown": drawdown,
            })
            logger.info("PROMOTED %s: %d days in probation, drawdown %.1f%%.",
                       symbol, days_in_probation, drawdown * 100)

    return promotions
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_core_guardian.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/claude_invest/modules/core_guardian.py tests/test_core_guardian.py
git commit -m "feat: add core guardian with peak tracking and tiered exits"
```

---

### Task 5: CLI Commands & Integration

**Files:**
- Modify: `src/claude_invest/main.py`
- Modify: `src/claude_invest/modules/core_engine.py`

- [ ] **Step 1: Add CLI commands to main.py**

Add these command handlers in the elif chain in `main()`:

```python
    elif command == "check-graduation" and len(sys.argv) >= 3:
        cmd_check_graduation(sys.argv[2])
    elif command == "core-health":
        cmd_core_health()
```

Add the command functions:

```python
def cmd_check_graduation(symbol: str):
    from claude_invest.modules.graduation import check_graduation, execute_graduation
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    portfolio = get_portfolio()

    result = check_graduation(symbol, config, db, portfolio)
    if result["decision"] == "graduate":
        config_path = str(Path(__file__).parent / "config" / "settings.yaml")
        grad_result = execute_graduation(symbol, config, db, portfolio, config_path)
        result["graduation"] = grad_result

    print(json.dumps(result, indent=2, default=str))
    db.close()


def cmd_core_health():
    from claude_invest.modules.core_guardian import check_core_health, update_peaks, check_probation_promotions
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    portfolio = get_portfolio()

    core_symbols = {item["symbol"] for item in config.get("core_holdings", {}).get("buy_list", [])}
    update_peaks(db, portfolio, core_symbols)
    health = check_core_health(config, db, portfolio)
    promotions = check_probation_promotions(config, db, portfolio)
    health["promotions"] = promotions

    print(json.dumps(health, indent=2, default=str))
    db.close()
```

- [ ] **Step 2: Integrate core_guardian into core-cycle**

In `core_engine.py`, at the end of `run_core_cycle()`, before the return statement, add:

```python
    # Run core guardian health checks
    from claude_invest.modules.core_guardian import check_core_health, update_peaks, check_probation_promotions

    core_symbols = {item["symbol"] for item in buy_list}
    update_peaks(db, portfolio, core_symbols)
    health = check_core_health(config, db, portfolio)
    promotions = check_probation_promotions(config, db, portfolio)
```

Update the return dict to include:

```python
    return {
        "buys_executed": buys_executed,
        "buys_skipped": buys_skipped,
        "exits": exits,
        "core_capital": core_capital,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "guardian": health,
        "promotions": promotions,
    }
```

- [ ] **Step 3: Run existing tests to verify no regressions**

Run: `python3 -m pytest tests/ -v --timeout=30`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add src/claude_invest/main.py src/claude_invest/modules/core_engine.py
git commit -m "feat: add check-graduation and core-health CLI commands, integrate guardian into core-cycle"
```

---

### Task 6: API Endpoints

**Files:**
- Modify: `src/claude_invest/modules/api_server.py`

- [ ] **Step 1: Add graduation and health endpoints**

```python
@app.get("/api/graduations")
def get_graduations():
    db = Database(DB_PATH)
    db.initialize()
    graduations = db.get_graduations()
    db.close()
    return {"graduations": graduations}


@app.get("/api/core/health")
def get_core_health():
    from claude_invest.modules.core_guardian import check_core_health, update_peaks
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    portfolio = get_portfolio()

    core_symbols = {item["symbol"] for item in config.get("core_holdings", {}).get("buy_list", [])}
    update_peaks(db, portfolio, core_symbols)
    health = check_core_health(config, db, portfolio)

    # Add drawdown info per symbol
    peaks = db.get_all_core_peaks()
    positions_by_symbol = {p["symbol"]: p for p in portfolio.get("positions", [])}
    drawdowns = []
    for peak in peaks:
        pos = positions_by_symbol.get(peak["symbol"])
        if pos:
            dd = (pos["current_price"] - peak["peak_price"]) / peak["peak_price"]
            drawdowns.append({
                "symbol": peak["symbol"],
                "peak_price": peak["peak_price"],
                "peak_date": peak["peak_date"],
                "current_price": pos["current_price"],
                "drawdown": dd,
            })
    health["drawdowns"] = drawdowns
    db.close()
    return health
```

- [ ] **Step 2: Commit**

```bash
git add src/claude_invest/modules/api_server.py
git commit -m "feat: add /api/graduations and /api/core/health endpoints"
```

---

### Task 7: Update Trading Cron Prompt

**Files:**
- This is a documentation/config change to the cron prompt used in CronCreate

- [ ] **Step 1: Document the updated trading cron flow**

The trading cron prompt's POSITION MANAGEMENT section should be updated to include:

```
### 2. POSITION MANAGEMENT
For each trading position, analyze. 

**When RSI > 80 (sell trigger):**
1. First run: python3 -m claude_invest.main check-graduation SYMBOL
2. If result shows "decision": "graduate" → DO NOT SELL. The stock has graduated to core holdings.
3. If result shows "decision": "sell" → proceed with normal sell.

SELL if bearish + negative sentiment, or 5% stop-loss hit.
**Do NOT sell core holdings.** Those are managed by core-cycle only.
```

- [ ] **Step 2: Commit cron documentation**

This change is applied when the cron is recreated at session start. No file commit needed — the cron prompt is passed at CronCreate time.

---

### Task 8: Run Full Test Suite

- [ ] **Step 1: Run all tests**

Run: `python3 -m pytest tests/ -v --timeout=30`
Expected: ALL PASS (including new graduation and guardian tests)

- [ ] **Step 2: Manual integration check**

Run: `python3 -m claude_invest.main check-graduation PLTR`
Expected: JSON output with decision (likely "sell" since PLTR is only -0.8% gain)

Run: `python3 -m claude_invest.main core-health`
Expected: JSON output with drawdowns for all core holdings, empty warnings/trims/exits

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address test failures from integration"
```
