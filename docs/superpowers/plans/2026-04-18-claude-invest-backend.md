# Claude Invest Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python trading engine with CLI interface that Claude Code cron can call to scan markets, analyze signals, manage risk, and execute trades via Alpaca.

**Architecture:** Modular Python package with separate modules for scanning, sentiment, technicals, risk, execution, and portfolio management. SQLite for persistence. CLI entry point returns structured JSON. FastAPI server exposes data for the dashboard.

**Tech Stack:** Python 3.12+, alpaca-py, pandas, ta (technical analysis), textblob, FastAPI, uvicorn, SQLite, PyYAML, pytest

---

## File Structure

```
claude-invest/
├── pyproject.toml                    # Project config, dependencies
├── .env.example                      # Template for API keys
├── src/
│   └── claude_invest/
│       ├── __init__.py
│       ├── main.py                   # CLI entry point
│       ├── config/
│       │   ├── __init__.py
│       │   ├── settings.yaml         # Default config values
│       │   └── loader.py             # Config loading + validation
│       └── modules/
│           ├── __init__.py
│           ├── db.py                 # SQLite schema + read/write
│           ├── scanner.py            # Market scanner + discovery
│           ├── sentiment.py          # News sentiment scoring
│           ├── technicals.py         # RSI, MACD, MA indicators
│           ├── risk_manager.py       # Position sizing, PDT, limits
│           ├── executor.py           # Alpaca order execution
│           ├── portfolio.py          # Portfolio state + P&L
│           └── api_server.py         # FastAPI server for dashboard
├── tests/
│   ├── conftest.py                   # Shared fixtures
│   ├── test_config.py
│   ├── test_db.py
│   ├── test_scanner.py
│   ├── test_sentiment.py
│   ├── test_technicals.py
│   ├── test_risk_manager.py
│   ├── test_executor.py
│   ├── test_portfolio.py
│   └── test_api_server.py
└── tasks/
    └── todo.md
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `src/claude_invest/__init__.py`
- Create: `src/claude_invest/config/__init__.py`
- Create: `src/claude_invest/modules/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "claude-invest"
version = "0.1.0"
description = "AI-powered algorithmic trading system"
requires-python = ">=3.12"
dependencies = [
    "alpaca-py>=0.31.0",
    "pandas>=2.2.0",
    "ta>=0.11.0",
    "textblob>=0.18.0",
    "fastapi>=0.115.0",
    "uvicorn>=0.34.0",
    "pyyaml>=6.0",
    "aiosqlite>=0.20.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
]

[project.scripts]
claude-invest = "claude_invest.main:main"
```

- [ ] **Step 2: Create .env.example**

```
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

- [ ] **Step 3: Create .gitignore**

```
__pycache__/
*.py[cod]
.env
*.db
*.sqlite
.venv/
dist/
*.egg-info/
.pytest_cache/
```

- [ ] **Step 4: Create package init files**

`src/claude_invest/__init__.py`:
```python
"""Claude Invest — AI-powered algorithmic trading system."""
```

`src/claude_invest/config/__init__.py`:
```python
```

`src/claude_invest/modules/__init__.py`:
```python
```

`tests/__init__.py`:
```python
```

- [ ] **Step 5: Create tests/conftest.py with shared fixtures**

```python
import os
import tempfile
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def tmp_db_path(tmp_path):
    """Provide a temporary SQLite database path."""
    return str(tmp_path / "test.db")


@pytest.fixture
def sample_config(tmp_path):
    """Provide a sample config dict matching settings.yaml structure."""
    config = {
        "mode": "paper",
        "capital": 5000,
        "max_positions": 8,
        "max_per_ticker": 0.10,
        "position_size_pct": 0.02,
        "daily_loss_limit": -150,
        "pdt_tracking": True,
        "exit_strategy": {
            "stop_loss_pct": 0.05,
            "trailing_stop_pct": 0.03,
            "signal_exit": True,
        },
        "polling": {
            "market_open_interval": 5,
            "market_close_interval": 5,
            "midday_interval": 15,
            "crypto_interval": 60,
        },
        "discovery": {
            "min_relative_volume": 2.0,
            "min_news_count": 2,
            "sentiment_threshold": 0.3,
        },
        "trading_style": "mixed",
    }
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(yaml.dump(config))
    return config, str(config_path)
```

- [ ] **Step 6: Create virtual environment and install**

Run:
```bash
cd /Users/adewaleadeleye/projects/claude-invest
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Expected: Clean install, no errors.

- [ ] **Step 7: Verify pytest runs**

Run: `pytest --co`
Expected: "no tests ran" (collection works, no tests yet)

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .env.example .gitignore src/ tests/
git commit -m "feat: scaffold project structure with dependencies"
```

---

### Task 2: Config Loader

**Files:**
- Create: `src/claude_invest/config/settings.yaml`
- Create: `src/claude_invest/config/loader.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

`tests/test_config.py`:
```python
import pytest
from claude_invest.config.loader import load_config, ConfigError


def test_load_config_from_file(sample_config):
    config_dict, config_path = sample_config
    config = load_config(config_path)
    assert config["mode"] == "paper"
    assert config["capital"] == 5000
    assert config["max_positions"] == 8
    assert config["exit_strategy"]["stop_loss_pct"] == 0.05


def test_load_config_default():
    """Loading without a path uses the bundled default settings.yaml."""
    config = load_config()
    assert config["mode"] == "paper"
    assert "capital" in config
    assert "exit_strategy" in config
    assert "discovery" in config


def test_load_config_missing_file():
    with pytest.raises(ConfigError):
        load_config("/nonexistent/path/settings.yaml")


def test_config_validates_required_keys(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text("mode: paper\n")
    with pytest.raises(ConfigError, match="capital"):
        load_config(str(bad_config))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'claude_invest.config.loader'`

- [ ] **Step 3: Create default settings.yaml**

`src/claude_invest/config/settings.yaml`:
```yaml
mode: paper
capital: 5000
max_positions: 8
max_per_ticker: 0.10
position_size_pct: 0.02
daily_loss_limit: -150
pdt_tracking: true

exit_strategy:
  stop_loss_pct: 0.05
  trailing_stop_pct: 0.03
  signal_exit: true

polling:
  market_open_interval: 5
  market_close_interval: 5
  midday_interval: 15
  crypto_interval: 60

discovery:
  min_relative_volume: 2.0
  min_news_count: 2
  sentiment_threshold: 0.3

trading_style: mixed
```

- [ ] **Step 4: Implement config loader**

`src/claude_invest/config/loader.py`:
```python
from pathlib import Path

import yaml


class ConfigError(Exception):
    pass


REQUIRED_KEYS = [
    "mode", "capital", "max_positions", "max_per_ticker",
    "position_size_pct", "daily_loss_limit", "pdt_tracking",
    "exit_strategy", "polling", "discovery", "trading_style",
]

DEFAULT_CONFIG_PATH = Path(__file__).parent / "settings.yaml"


def load_config(path: str | None = None) -> dict:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH

    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ConfigError("Config file must contain a YAML mapping")

    for key in REQUIRED_KEYS:
        if key not in config:
            raise ConfigError(f"Missing required config key: {key}")

    return config
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/claude_invest/config/ tests/test_config.py
git commit -m "feat: add config loader with validation and defaults"
```

---

### Task 3: Database Layer

**Files:**
- Create: `src/claude_invest/modules/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write failing tests**

`tests/test_db.py`:
```python
import pytest
from claude_invest.modules.db import Database


@pytest.fixture
def db(tmp_db_path):
    database = Database(tmp_db_path)
    database.initialize()
    return database


def test_initialize_creates_tables(db):
    tables = db.list_tables()
    expected = {"trades", "positions", "signals", "decisions", "portfolio_snapshots", "discovery_log", "pdt_tracker"}
    assert expected == set(tables)


def test_insert_and_query_trade(db):
    trade = {
        "symbol": "AAPL",
        "side": "buy",
        "qty": 5,
        "price": 150.0,
        "order_id": "test-order-1",
        "trade_type": "swing",
        "status": "filled",
    }
    db.insert_trade(trade)
    trades = db.get_trades(symbol="AAPL")
    assert len(trades) == 1
    assert trades[0]["symbol"] == "AAPL"
    assert trades[0]["qty"] == 5


def test_insert_and_query_decision(db):
    decision = {
        "ticker": "TSLA",
        "action": "buy",
        "reasoning": "Strong momentum with positive sentiment",
        "signals_snapshot": '{"rsi": 45, "sentiment": 0.7}',
    }
    db.insert_decision(decision)
    decisions = db.get_decisions(limit=10)
    assert len(decisions) == 1
    assert decisions[0]["ticker"] == "TSLA"
    assert decisions[0]["action"] == "buy"


def test_insert_portfolio_snapshot(db):
    snapshot = {
        "total_value": 5200.0,
        "cash": 4100.0,
        "positions_value": 1100.0,
        "daily_pnl": 45.50,
    }
    db.insert_portfolio_snapshot(snapshot)
    snapshots = db.get_portfolio_snapshots(limit=1)
    assert len(snapshots) == 1
    assert snapshots[0]["total_value"] == 5200.0


def test_insert_and_query_signal(db):
    signal = {
        "ticker": "NVDA",
        "sentiment_score": 0.65,
        "rsi": 42.0,
        "macd": 1.5,
        "volume_ratio": 2.3,
        "trend": "bullish",
    }
    db.insert_signal(signal)
    signals = db.get_signals(ticker="NVDA")
    assert len(signals) == 1
    assert signals[0]["rsi"] == 42.0


def test_insert_discovery_log(db):
    entry = {
        "ticker": "AMD",
        "volume_score": 3.2,
        "news_score": 0.6,
        "sentiment": 0.45,
        "action_taken": "flagged",
    }
    db.insert_discovery(entry)
    logs = db.get_discovery_log(limit=10)
    assert len(logs) == 1
    assert logs[0]["ticker"] == "AMD"


def test_pdt_tracker(db):
    db.record_day_trade("trade-1")
    db.record_day_trade("trade-2")
    count = db.get_day_trade_count(days=5)
    assert count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement database module**

`src/claude_invest/modules/db.py`:
```python
import json
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
        """)
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
            "INSERT INTO trades (symbol, side, qty, price, order_id, trade_type, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (trade["symbol"], trade["side"], trade["qty"], trade["price"],
             trade.get("order_id"), trade.get("trade_type"), trade.get("status")),
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
            "INSERT INTO decisions (ticker, action, reasoning, signals_snapshot) VALUES (?, ?, ?, ?)",
            (decision["ticker"], decision["action"],
             decision.get("reasoning"), decision.get("signals_snapshot")),
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

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_db.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/claude_invest/modules/db.py tests/test_db.py
git commit -m "feat: add SQLite database layer with schema and CRUD operations"
```

---

### Task 4: Portfolio Module

**Files:**
- Create: `src/claude_invest/modules/portfolio.py`
- Create: `tests/test_portfolio.py`

- [ ] **Step 1: Write failing tests**

`tests/test_portfolio.py`:
```python
import pytest
from unittest.mock import MagicMock, patch
from claude_invest.modules.portfolio import get_portfolio


def _mock_account():
    account = MagicMock()
    account.equity = "5200.00"
    account.cash = "4100.00"
    account.buying_power = "8200.00"
    account.portfolio_value = "5200.00"
    account.last_equity = "5150.00"
    return account


def _mock_position(symbol, qty, avg_price, current_price, unrealized_pl):
    pos = MagicMock()
    pos.symbol = symbol
    pos.qty = qty
    pos.avg_entry_price = avg_price
    pos.current_price = current_price
    pos.unrealized_pl = unrealized_pl
    pos.market_value = str(float(qty) * float(current_price))
    return pos


@patch("claude_invest.modules.portfolio._get_trading_client")
def test_get_portfolio_returns_state(mock_client_fn):
    client = MagicMock()
    client.get_account.return_value = _mock_account()
    client.get_all_positions.return_value = [
        _mock_position("AAPL", "5", "150.00", "155.00", "25.00"),
        _mock_position("BTC/USD", "0.01", "60000.00", "62000.00", "20.00"),
    ]
    mock_client_fn.return_value = client

    result = get_portfolio()

    assert result["equity"] == 5200.00
    assert result["cash"] == 4100.00
    assert result["daily_pnl"] == 50.00
    assert len(result["positions"]) == 2
    assert result["positions"][0]["symbol"] == "AAPL"
    assert result["positions"][1]["symbol"] == "BTC/USD"


@patch("claude_invest.modules.portfolio._get_trading_client")
def test_get_portfolio_empty_positions(mock_client_fn):
    client = MagicMock()
    client.get_account.return_value = _mock_account()
    client.get_all_positions.return_value = []
    mock_client_fn.return_value = client

    result = get_portfolio()

    assert result["positions"] == []
    assert result["position_count"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_portfolio.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement portfolio module**

`src/claude_invest/modules/portfolio.py`:
```python
import os

from alpaca.trading.client import TradingClient
from dotenv import load_dotenv

load_dotenv()


def _get_trading_client() -> TradingClient:
    return TradingClient(
        api_key=os.environ["ALPACA_API_KEY"],
        secret_key=os.environ["ALPACA_SECRET_KEY"],
        paper=os.environ.get("ALPACA_BASE_URL", "").startswith("https://paper"),
    )


def get_portfolio() -> dict:
    client = _get_trading_client()
    account = client.get_account()
    positions_raw = client.get_all_positions()

    equity = float(account.equity)
    last_equity = float(account.last_equity)

    positions = []
    for p in positions_raw:
        positions.append({
            "symbol": p.symbol,
            "qty": float(p.qty),
            "avg_entry_price": float(p.avg_entry_price),
            "current_price": float(p.current_price),
            "unrealized_pl": float(p.unrealized_pl),
            "market_value": float(p.market_value),
        })

    return {
        "equity": equity,
        "cash": float(account.cash),
        "buying_power": float(account.buying_power),
        "daily_pnl": round(equity - last_equity, 2),
        "positions": positions,
        "position_count": len(positions),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_portfolio.py -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/claude_invest/modules/portfolio.py tests/test_portfolio.py
git commit -m "feat: add portfolio module for account state and positions"
```

---

### Task 5: Sentiment Analysis Module

**Files:**
- Create: `src/claude_invest/modules/sentiment.py`
- Create: `tests/test_sentiment.py`

- [ ] **Step 1: Write failing tests**

`tests/test_sentiment.py`:
```python
import pytest
from unittest.mock import MagicMock, patch
from claude_invest.modules.sentiment import analyze_sentiment, score_headline


def test_score_headline_positive():
    score = score_headline("Apple reports record revenue beating all expectations")
    assert score > 0


def test_score_headline_negative():
    score = score_headline("Company faces massive lawsuit and regulatory investigation")
    assert score < 0


def test_score_headline_neutral():
    score = score_headline("Company schedules quarterly earnings call")
    assert -0.2 <= score <= 0.2


def _mock_news(headlines):
    articles = []
    for h in headlines:
        article = MagicMock()
        article.headline = h
        article.summary = h
        articles.append(article)
    return articles


@patch("claude_invest.modules.sentiment._get_news_client")
def test_analyze_sentiment_aggregates_scores(mock_client_fn):
    client = MagicMock()
    client.get_news.return_value = _mock_news([
        "Stock surges on incredible earnings beat",
        "Record profits drive shares higher",
        "Analysts raise price targets after strong quarter",
    ])
    mock_client_fn.return_value = client

    result = analyze_sentiment("AAPL")

    assert result["ticker"] == "AAPL"
    assert result["score"] > 0
    assert result["article_count"] == 3
    assert -1 <= result["score"] <= 1


@patch("claude_invest.modules.sentiment._get_news_client")
def test_analyze_sentiment_no_news(mock_client_fn):
    client = MagicMock()
    client.get_news.return_value = []
    mock_client_fn.return_value = client

    result = analyze_sentiment("XYZ")

    assert result["score"] == 0.0
    assert result["article_count"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sentiment.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement sentiment module**

`src/claude_invest/modules/sentiment.py`:
```python
import os
from datetime import datetime, timedelta, timezone

from alpaca.data.historical.news import NewsClient
from alpaca.data.requests import NewsRequest
from dotenv import load_dotenv
from textblob import TextBlob

load_dotenv()


def _get_news_client() -> NewsClient:
    return NewsClient(
        api_key=os.environ["ALPACA_API_KEY"],
        secret_key=os.environ["ALPACA_SECRET_KEY"],
    )


def score_headline(text: str) -> float:
    blob = TextBlob(text)
    return round(blob.sentiment.polarity, 4)


def analyze_sentiment(ticker: str, lookback_hours: int = 24) -> dict:
    client = _get_news_client()
    start = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    request = NewsRequest(
        symbols=ticker,
        start=start,
        limit=20,
        sort="desc",
    )
    articles = client.get_news(request)

    if not articles:
        return {
            "ticker": ticker,
            "score": 0.0,
            "article_count": 0,
            "headlines": [],
        }

    scores = []
    headlines = []
    for article in articles:
        text = f"{article.headline}. {article.summary}" if article.summary else article.headline
        s = score_headline(text)
        scores.append(s)
        headlines.append({"headline": article.headline, "score": s})

    avg_score = round(sum(scores) / len(scores), 4)

    return {
        "ticker": ticker,
        "score": max(-1.0, min(1.0, avg_score)),
        "article_count": len(articles),
        "headlines": headlines,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sentiment.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/claude_invest/modules/sentiment.py tests/test_sentiment.py
git commit -m "feat: add sentiment analysis module with TextBlob NLP scoring"
```

---

### Task 6: Technical Analysis Module

**Files:**
- Create: `src/claude_invest/modules/technicals.py`
- Create: `tests/test_technicals.py`

- [ ] **Step 1: Write failing tests**

`tests/test_technicals.py`:
```python
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from claude_invest.modules.technicals import analyze_technicals, compute_indicators


def _make_price_df(prices: list[float]) -> pd.DataFrame:
    """Create a DataFrame mimicking OHLCV bar data."""
    n = len(prices)
    return pd.DataFrame({
        "open": prices,
        "high": [p * 1.02 for p in prices],
        "low": [p * 0.98 for p in prices],
        "close": prices,
        "volume": [1000000] * n,
    })


def test_compute_indicators_returns_all_fields():
    # Need at least 26 bars for MACD, 14 for RSI
    np.random.seed(42)
    prices = list(np.cumsum(np.random.randn(50)) + 100)
    df = _make_price_df(prices)

    result = compute_indicators(df)

    assert "rsi" in result
    assert "macd" in result
    assert "macd_signal" in result
    assert "sma_20" in result
    assert "sma_50" in result
    assert "trend" in result
    assert result["rsi"] is not None


def test_compute_indicators_uptrend():
    # Steadily rising prices
    prices = [100 + i * 0.5 for i in range(50)]
    df = _make_price_df(prices)

    result = compute_indicators(df)

    assert result["trend"] == "bullish"


def test_compute_indicators_downtrend():
    # Steadily falling prices
    prices = [150 - i * 0.5 for i in range(50)]
    df = _make_price_df(prices)

    result = compute_indicators(df)

    assert result["trend"] == "bearish"


@patch("claude_invest.modules.technicals._get_bars")
def test_analyze_technicals_returns_full_signal(mock_get_bars):
    np.random.seed(42)
    prices = list(np.cumsum(np.random.randn(50)) + 100)
    mock_get_bars.return_value = _make_price_df(prices)

    result = analyze_technicals("AAPL")

    assert result["ticker"] == "AAPL"
    assert "rsi" in result
    assert "macd" in result
    assert "trend" in result
    assert "current_price" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_technicals.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement technicals module**

`src/claude_invest/modules/technicals.py`:
```python
import os

import pandas as pd
import ta
from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()


def _get_bars(ticker: str, days: int = 60) -> pd.DataFrame:
    api_key = os.environ["ALPACA_API_KEY"]
    secret_key = os.environ["ALPACA_SECRET_KEY"]
    start = datetime.now(timezone.utc) - timedelta(days=days)

    if "/" in ticker:
        client = CryptoHistoricalDataClient(api_key, secret_key)
        request = CryptoBarsRequest(
            symbol_or_symbols=ticker, timeframe=TimeFrame.Hour, start=start
        )
        bars = client.get_crypto_bars(request)
    else:
        client = StockHistoricalDataClient(api_key, secret_key)
        request = StockBarsRequest(
            symbol_or_symbols=ticker, timeframe=TimeFrame.Hour, start=start
        )
        bars = client.get_stock_bars(request)

    df = bars.df.reset_index()
    df.columns = [c.lower() for c in df.columns]
    return df


def compute_indicators(df: pd.DataFrame) -> dict:
    close = df["close"]
    high = df["high"]
    low = df["low"]

    rsi = ta.momentum.rsi(close, window=14)
    macd_line = ta.trend.macd(close)
    macd_signal = ta.trend.macd_signal(close)
    sma_20 = ta.trend.sma_indicator(close, window=20)
    sma_50 = ta.trend.sma_indicator(close, window=50)

    current_price = float(close.iloc[-1])
    current_sma_20 = float(sma_20.iloc[-1]) if pd.notna(sma_20.iloc[-1]) else None
    current_sma_50 = float(sma_50.iloc[-1]) if pd.notna(sma_50.iloc[-1]) else None

    # Determine trend
    if current_sma_20 and current_sma_50:
        if current_price > current_sma_20 > current_sma_50:
            trend = "bullish"
        elif current_price < current_sma_20 < current_sma_50:
            trend = "bearish"
        else:
            trend = "neutral"
    else:
        trend = "neutral"

    return {
        "current_price": current_price,
        "rsi": round(float(rsi.iloc[-1]), 2) if pd.notna(rsi.iloc[-1]) else None,
        "macd": round(float(macd_line.iloc[-1]), 4) if pd.notna(macd_line.iloc[-1]) else None,
        "macd_signal": round(float(macd_signal.iloc[-1]), 4) if pd.notna(macd_signal.iloc[-1]) else None,
        "sma_20": round(current_sma_20, 2) if current_sma_20 else None,
        "sma_50": round(current_sma_50, 2) if current_sma_50 else None,
        "trend": trend,
    }


def analyze_technicals(ticker: str) -> dict:
    df = _get_bars(ticker)
    indicators = compute_indicators(df)
    indicators["ticker"] = ticker
    return indicators
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_technicals.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/claude_invest/modules/technicals.py tests/test_technicals.py
git commit -m "feat: add technical analysis module with RSI, MACD, SMA indicators"
```

---

### Task 7: Market Scanner Module

**Files:**
- Create: `src/claude_invest/modules/scanner.py`
- Create: `tests/test_scanner.py`

- [ ] **Step 1: Write failing tests**

`tests/test_scanner.py`:
```python
import pytest
from unittest.mock import MagicMock, patch
from claude_invest.modules.scanner import scan_market, score_ticker


def test_score_ticker_both_signals():
    result = score_ticker(volume_ratio=3.0, sentiment_score=0.5, news_count=3)
    assert result["flagged"] is True
    assert result["combined_score"] > 0


def test_score_ticker_volume_only():
    """Volume spike alone should not flag — needs two-signal confirmation."""
    result = score_ticker(volume_ratio=3.0, sentiment_score=0.1, news_count=1)
    assert result["flagged"] is False


def test_score_ticker_sentiment_only():
    """Sentiment alone should not flag — needs volume confirmation."""
    result = score_ticker(volume_ratio=1.0, sentiment_score=0.6, news_count=5)
    assert result["flagged"] is False


def test_score_ticker_below_thresholds():
    result = score_ticker(volume_ratio=1.2, sentiment_score=0.1, news_count=0)
    assert result["flagged"] is False


@patch("claude_invest.modules.scanner._get_most_active_tickers")
@patch("claude_invest.modules.scanner._get_snapshot")
@patch("claude_invest.modules.scanner.analyze_sentiment")
def test_scan_market_returns_ranked_candidates(mock_sentiment, mock_snapshot, mock_active):
    mock_active.return_value = ["AAPL", "TSLA", "NVDA"]

    mock_snapshot.side_effect = lambda t: {"volume_ratio": 3.0 if t != "TSLA" else 1.0}
    mock_sentiment.side_effect = lambda t: {
        "ticker": t,
        "score": 0.6 if t != "TSLA" else 0.1,
        "article_count": 3 if t != "TSLA" else 0,
    }

    config = {
        "discovery": {
            "min_relative_volume": 2.0,
            "min_news_count": 2,
            "sentiment_threshold": 0.3,
        }
    }

    results = scan_market(config)

    flagged = [r for r in results if r["flagged"]]
    assert len(flagged) == 2  # AAPL and NVDA pass, TSLA doesn't
    assert all(r["ticker"] in ("AAPL", "NVDA") for r in flagged)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scanner.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement scanner module**

`src/claude_invest/modules/scanner.py`:
```python
import os

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockSnapshotRequest, MostActivesRequest
from alpaca.data.historical.screener import ScreenerClient
from dotenv import load_dotenv

from claude_invest.modules.sentiment import analyze_sentiment

load_dotenv()

# Default thresholds — overridden by config
DEFAULT_MIN_VOLUME = 2.0
DEFAULT_MIN_NEWS = 2
DEFAULT_MIN_SENTIMENT = 0.3


def _get_most_active_tickers(top_n: int = 20) -> list[str]:
    api_key = os.environ["ALPACA_API_KEY"]
    secret_key = os.environ["ALPACA_SECRET_KEY"]
    client = ScreenerClient(api_key, secret_key)
    request = MostActivesRequest(top=top_n)
    response = client.get_most_actives(request)
    return [item.symbol for item in response.most_actives]


def _get_snapshot(ticker: str) -> dict:
    api_key = os.environ["ALPACA_API_KEY"]
    secret_key = os.environ["ALPACA_SECRET_KEY"]
    client = StockHistoricalDataClient(api_key, secret_key)
    snapshot = client.get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=ticker))

    if ticker not in snapshot:
        return {"volume_ratio": 0.0}

    snap = snapshot[ticker]
    daily_vol = float(snap.daily_bar.volume) if snap.daily_bar else 0
    prev_vol = float(snap.previous_daily_bar.volume) if snap.previous_daily_bar else 1

    volume_ratio = daily_vol / prev_vol if prev_vol > 0 else 0.0

    return {"volume_ratio": round(volume_ratio, 2)}


def score_ticker(
    volume_ratio: float,
    sentiment_score: float,
    news_count: int,
    min_volume: float = DEFAULT_MIN_VOLUME,
    min_news: int = DEFAULT_MIN_NEWS,
    min_sentiment: float = DEFAULT_MIN_SENTIMENT,
) -> dict:
    volume_pass = volume_ratio >= min_volume
    sentiment_pass = sentiment_score >= min_sentiment and news_count >= min_news

    flagged = volume_pass and sentiment_pass
    combined_score = (volume_ratio * 0.4) + (sentiment_score * 0.6) if flagged else 0.0

    return {
        "flagged": flagged,
        "combined_score": round(combined_score, 4),
        "volume_ratio": volume_ratio,
        "sentiment_score": sentiment_score,
        "news_count": news_count,
    }


def scan_market(config: dict) -> list[dict]:
    disc = config.get("discovery", {})
    min_vol = disc.get("min_relative_volume", DEFAULT_MIN_VOLUME)
    min_news = disc.get("min_news_count", DEFAULT_MIN_NEWS)
    min_sent = disc.get("sentiment_threshold", DEFAULT_MIN_SENTIMENT)

    tickers = _get_most_active_tickers()
    results = []

    for ticker in tickers:
        snapshot = _get_snapshot(ticker)
        sentiment = analyze_sentiment(ticker)

        scored = score_ticker(
            volume_ratio=snapshot["volume_ratio"],
            sentiment_score=sentiment["score"],
            news_count=sentiment["article_count"],
            min_volume=min_vol,
            min_news=min_news,
            min_sentiment=min_sent,
        )
        scored["ticker"] = ticker
        results.append(scored)

    results.sort(key=lambda x: x["combined_score"], reverse=True)
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scanner.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/claude_invest/modules/scanner.py tests/test_scanner.py
git commit -m "feat: add market scanner with two-signal discovery (volume + sentiment)"
```

---

### Task 8: Risk Manager Module

**Files:**
- Create: `src/claude_invest/modules/risk_manager.py`
- Create: `tests/test_risk_manager.py`

- [ ] **Step 1: Write failing tests**

`tests/test_risk_manager.py`:
```python
import pytest
from claude_invest.modules.risk_manager import RiskManager


@pytest.fixture
def risk_mgr(sample_config, tmp_db_path):
    config, _ = sample_config
    from claude_invest.modules.db import Database
    db = Database(tmp_db_path)
    db.initialize()
    return RiskManager(config, db)


def test_position_size_calculation(risk_mgr):
    size = risk_mgr.calculate_position_size(price=150.0)
    # 2% of $5000 = $100 -> 100/150 = 0 shares (rounds down), need at least 1
    assert size >= 0
    expected_dollars = 5000 * 0.02  # $100
    expected_shares = int(expected_dollars / 150.0)
    assert size == expected_shares


def test_max_per_ticker_limit(risk_mgr):
    # Max 10% of $5000 = $500 at $50/share = 10 shares
    size = risk_mgr.calculate_position_size(price=50.0)
    max_shares = int(5000 * 0.10 / 50.0)
    assert size <= max_shares


def test_check_trade_approved(risk_mgr):
    portfolio = {
        "equity": 5000,
        "daily_pnl": 0,
        "position_count": 2,
        "positions": [],
    }
    result = risk_mgr.check_trade("AAPL", 2, 150.0, portfolio)
    assert result["approved"] is True


def test_check_trade_rejected_max_positions(risk_mgr):
    portfolio = {
        "equity": 5000,
        "daily_pnl": 0,
        "position_count": 8,  # at max
        "positions": [],
    }
    result = risk_mgr.check_trade("AAPL", 2, 150.0, portfolio)
    assert result["approved"] is False
    assert "max positions" in result["reason"].lower()


def test_check_trade_rejected_daily_loss(risk_mgr):
    portfolio = {
        "equity": 5000,
        "daily_pnl": -160,  # exceeds -150 limit
        "position_count": 2,
        "positions": [],
    }
    result = risk_mgr.check_trade("AAPL", 2, 150.0, portfolio)
    assert result["approved"] is False
    assert "daily loss" in result["reason"].lower()


def test_check_trade_rejected_ticker_exposure(risk_mgr):
    portfolio = {
        "equity": 5000,
        "daily_pnl": 0,
        "position_count": 2,
        "positions": [
            {"symbol": "AAPL", "market_value": 450.0},  # already near 10% cap
        ],
    }
    # Trying to add more AAPL would exceed 10% of $5000 = $500
    result = risk_mgr.check_trade("AAPL", 2, 150.0, portfolio)
    assert result["approved"] is False
    assert "exposure" in result["reason"].lower()


def test_pdt_check_blocks_fourth_day_trade(risk_mgr):
    # Record 3 day trades
    risk_mgr.db.record_day_trade("t1")
    risk_mgr.db.record_day_trade("t2")
    risk_mgr.db.record_day_trade("t3")

    result = risk_mgr.check_pdt_allowed()
    assert result is False


def test_pdt_check_allows_under_limit(risk_mgr):
    risk_mgr.db.record_day_trade("t1")
    risk_mgr.db.record_day_trade("t2")

    result = risk_mgr.check_pdt_allowed()
    assert result is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_risk_manager.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement risk manager**

`src/claude_invest/modules/risk_manager.py`:
```python
from claude_invest.modules.db import Database


class RiskManager:
    def __init__(self, config: dict, db: Database):
        self.config = config
        self.db = db
        self.capital = config["capital"]
        self.max_positions = config["max_positions"]
        self.max_per_ticker = config["max_per_ticker"]
        self.position_size_pct = config["position_size_pct"]
        self.daily_loss_limit = config["daily_loss_limit"]
        self.pdt_tracking = config["pdt_tracking"]

    def calculate_position_size(self, price: float) -> int:
        target_dollars = self.capital * self.position_size_pct
        max_dollars = self.capital * self.max_per_ticker
        dollars = min(target_dollars, max_dollars)
        return int(dollars / price)

    def check_trade(self, symbol: str, qty: int, price: float, portfolio: dict) -> dict:
        # Check daily loss limit
        if portfolio["daily_pnl"] <= self.daily_loss_limit:
            return {"approved": False, "reason": "Daily loss limit reached"}

        # Check max positions
        if portfolio["position_count"] >= self.max_positions:
            return {"approved": False, "reason": "Max positions reached"}

        # Check per-ticker exposure
        existing_exposure = sum(
            p["market_value"]
            for p in portfolio["positions"]
            if p["symbol"] == symbol
        )
        new_exposure = existing_exposure + (qty * price)
        max_exposure = self.capital * self.max_per_ticker

        if new_exposure > max_exposure:
            return {
                "approved": False,
                "reason": f"Ticker exposure would be ${new_exposure:.0f}, max is ${max_exposure:.0f}",
            }

        return {"approved": True, "reason": "Trade within risk limits"}

    def check_pdt_allowed(self) -> bool:
        if not self.pdt_tracking:
            return True
        count = self.db.get_day_trade_count(days=5)
        return count < 3
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_risk_manager.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/claude_invest/modules/risk_manager.py tests/test_risk_manager.py
git commit -m "feat: add risk manager with position sizing, PDT tracking, and exposure limits"
```

---

### Task 9: Trade Executor Module

**Files:**
- Create: `src/claude_invest/modules/executor.py`
- Create: `tests/test_executor.py`

- [ ] **Step 1: Write failing tests**

`tests/test_executor.py`:
```python
import pytest
from unittest.mock import MagicMock, patch
from claude_invest.modules.executor import execute_order


def _mock_order(order_id, symbol, side, qty, status):
    order = MagicMock()
    order.id = order_id
    order.symbol = symbol
    order.side = side
    order.qty = str(qty)
    order.filled_avg_price = "150.00"
    order.status = status
    order.submitted_at = "2026-04-18T10:00:00Z"
    return order


@patch("claude_invest.modules.executor._get_trading_client")
def test_execute_buy_order(mock_client_fn):
    client = MagicMock()
    client.submit_order.return_value = _mock_order(
        "order-1", "AAPL", "buy", 5, "accepted"
    )
    mock_client_fn.return_value = client

    result = execute_order(symbol="AAPL", side="buy", qty=5)

    assert result["order_id"] == "order-1"
    assert result["symbol"] == "AAPL"
    assert result["side"] == "buy"
    assert result["status"] == "accepted"
    client.submit_order.assert_called_once()


@patch("claude_invest.modules.executor._get_trading_client")
def test_execute_sell_order(mock_client_fn):
    client = MagicMock()
    client.submit_order.return_value = _mock_order(
        "order-2", "TSLA", "sell", 3, "accepted"
    )
    mock_client_fn.return_value = client

    result = execute_order(symbol="TSLA", side="sell", qty=3)

    assert result["order_id"] == "order-2"
    assert result["side"] == "sell"


@patch("claude_invest.modules.executor._get_trading_client")
def test_execute_order_crypto(mock_client_fn):
    client = MagicMock()
    client.submit_order.return_value = _mock_order(
        "order-3", "BTC/USD", "buy", 0.001, "accepted"
    )
    mock_client_fn.return_value = client

    result = execute_order(symbol="BTC/USD", side="buy", qty=0.001)

    assert result["symbol"] == "BTC/USD"
    assert result["status"] == "accepted"


@patch("claude_invest.modules.executor._get_trading_client")
def test_execute_order_failure(mock_client_fn):
    client = MagicMock()
    client.submit_order.side_effect = Exception("Insufficient buying power")
    mock_client_fn.return_value = client

    result = execute_order(symbol="AAPL", side="buy", qty=5)

    assert result["status"] == "error"
    assert "Insufficient buying power" in result["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_executor.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement executor module**

`src/claude_invest/modules/executor.py`:
```python
import os

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from dotenv import load_dotenv

load_dotenv()


def _get_trading_client() -> TradingClient:
    return TradingClient(
        api_key=os.environ["ALPACA_API_KEY"],
        secret_key=os.environ["ALPACA_SECRET_KEY"],
        paper=os.environ.get("ALPACA_BASE_URL", "").startswith("https://paper"),
    )


def execute_order(symbol: str, side: str, qty: float) -> dict:
    try:
        client = _get_trading_client()

        order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL
        time_in_force = TimeInForce.GTC if "/" in symbol else TimeInForce.DAY

        request = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=order_side,
            time_in_force=time_in_force,
        )

        order = client.submit_order(request)

        return {
            "order_id": str(order.id),
            "symbol": order.symbol,
            "side": side,
            "qty": float(order.qty),
            "filled_price": float(order.filled_avg_price) if order.filled_avg_price else None,
            "status": str(order.status),
            "submitted_at": str(order.submitted_at),
        }

    except Exception as e:
        return {
            "order_id": None,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "status": "error",
            "error": str(e),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_executor.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/claude_invest/modules/executor.py tests/test_executor.py
git commit -m "feat: add trade executor module for Alpaca order submission"
```

---

### Task 10: CLI Entry Point

**Files:**
- Create: `src/claude_invest/main.py`

- [ ] **Step 1: Implement the CLI**

`src/claude_invest/main.py`:
```python
import json
import sys

from claude_invest.config.loader import load_config
from claude_invest.modules.db import Database
from claude_invest.modules.portfolio import get_portfolio
from claude_invest.modules.scanner import scan_market
from claude_invest.modules.sentiment import analyze_sentiment
from claude_invest.modules.technicals import analyze_technicals
from claude_invest.modules.risk_manager import RiskManager
from claude_invest.modules.executor import execute_order

DB_PATH = "claude_invest.db"


def _output(data: dict):
    print(json.dumps(data, indent=2, default=str))


def cmd_portfolio():
    result = get_portfolio()
    db = Database(DB_PATH)
    db.initialize()
    db.insert_portfolio_snapshot({
        "total_value": result["equity"],
        "cash": result["cash"],
        "positions_value": result["equity"] - result["cash"],
        "daily_pnl": result["daily_pnl"],
    })
    db.close()
    _output(result)


def cmd_scan():
    config = load_config()
    results = scan_market(config)
    db = Database(DB_PATH)
    db.initialize()
    for r in results:
        db.insert_discovery({
            "ticker": r["ticker"],
            "volume_score": r["volume_ratio"],
            "news_score": r.get("sentiment_score", 0),
            "sentiment": r.get("sentiment_score", 0),
            "action_taken": "flagged" if r["flagged"] else "skipped",
        })
    db.close()
    _output({"candidates": results})


def cmd_analyze(ticker: str):
    sentiment = analyze_sentiment(ticker)
    technicals = analyze_technicals(ticker)
    db = Database(DB_PATH)
    db.initialize()
    db.insert_signal({
        "ticker": ticker,
        "sentiment_score": sentiment["score"],
        "rsi": technicals.get("rsi"),
        "macd": technicals.get("macd"),
        "volume_ratio": None,
        "trend": technicals.get("trend"),
    })
    db.close()
    _output({
        "ticker": ticker,
        "sentiment": sentiment,
        "technicals": technicals,
    })


def cmd_risk_check(ticker: str, qty: int, price: float):
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    risk_mgr = RiskManager(config, db)
    portfolio = get_portfolio()
    result = risk_mgr.check_trade(ticker, qty, price, portfolio)
    result["position_size_suggested"] = risk_mgr.calculate_position_size(price)
    result["pdt_allowed"] = risk_mgr.check_pdt_allowed()
    db.close()
    _output(result)


def cmd_execute(side: str, ticker: str, qty: float):
    result = execute_order(symbol=ticker, side=side, qty=qty)
    db = Database(DB_PATH)
    db.initialize()
    if result["status"] != "error":
        db.insert_trade({
            "symbol": ticker,
            "side": side,
            "qty": qty,
            "price": result.get("filled_price", 0),
            "order_id": result["order_id"],
            "trade_type": "market",
            "status": result["status"],
        })
    db.close()
    _output(result)


def cmd_log_decision(payload_json: str):
    payload = json.loads(payload_json)
    db = Database(DB_PATH)
    db.initialize()
    db.insert_decision(payload)
    db.close()
    _output({"status": "logged", "decision": payload})


def main():
    if len(sys.argv) < 2:
        _output({"error": "Usage: claude-invest <command> [args]", "commands": [
            "portfolio", "scan", "analyze <ticker>", "risk-check <ticker> <qty> <price>",
            "execute <buy|sell> <ticker> <qty>", "log-decision <json>",
        ]})
        sys.exit(1)

    command = sys.argv[1]

    if command == "portfolio":
        cmd_portfolio()
    elif command == "scan":
        cmd_scan()
    elif command == "analyze" and len(sys.argv) >= 3:
        cmd_analyze(sys.argv[2])
    elif command == "risk-check" and len(sys.argv) >= 5:
        cmd_risk_check(sys.argv[2], int(sys.argv[3]), float(sys.argv[4]))
    elif command == "execute" and len(sys.argv) >= 5:
        cmd_execute(sys.argv[2], sys.argv[3], float(sys.argv[4]))
    elif command == "log-decision" and len(sys.argv) >= 3:
        cmd_log_decision(sys.argv[2])
    else:
        _output({"error": f"Unknown command or missing args: {command}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test CLI manually**

Run:
```bash
cd /Users/adewaleadeleye/projects/claude-invest
source .venv/bin/activate
python -m claude_invest.main
```
Expected: JSON output showing usage/commands list.

- [ ] **Step 3: Commit**

```bash
git add src/claude_invest/main.py
git commit -m "feat: add CLI entry point for all trading commands"
```

---

### Task 11: FastAPI Server for Dashboard

**Files:**
- Create: `src/claude_invest/modules/api_server.py`
- Create: `tests/test_api_server.py`

- [ ] **Step 1: Write failing tests**

`tests/test_api_server.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from claude_invest.modules.api_server import create_app
from claude_invest.modules.db import Database


@pytest.fixture
def app(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    # Seed some test data
    db.insert_trade({
        "symbol": "AAPL", "side": "buy", "qty": 5, "price": 150.0,
        "order_id": "t1", "trade_type": "swing", "status": "filled",
    })
    db.insert_decision({
        "ticker": "AAPL", "action": "buy",
        "reasoning": "Strong momentum", "signals_snapshot": "{}",
    })
    db.insert_portfolio_snapshot({
        "total_value": 5200, "cash": 4100, "positions_value": 1100, "daily_pnl": 50,
    })
    db.insert_discovery({
        "ticker": "NVDA", "volume_score": 3.0, "news_score": 0.7,
        "sentiment": 0.6, "action_taken": "flagged",
    })
    db.close()
    return create_app(tmp_db_path)


@pytest.mark.asyncio
async def test_get_trades(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/trades")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "AAPL"


@pytest.mark.asyncio
async def test_get_decisions(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/decisions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["action"] == "buy"


@pytest.mark.asyncio
async def test_get_portfolio(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/portfolio")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["total_value"] == 5200


@pytest.mark.asyncio
async def test_get_discovery(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/discovery")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "NVDA"


@pytest.mark.asyncio
async def test_get_config(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "mode" in data
    assert "capital" in data
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api_server.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement FastAPI server**

`src/claude_invest/modules/api_server.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from claude_invest.config.loader import load_config
from claude_invest.modules.db import Database

DEFAULT_DB_PATH = "claude_invest.db"


def create_app(db_path: str = DEFAULT_DB_PATH) -> FastAPI:
    app = FastAPI(title="Claude Invest API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_db() -> Database:
        db = Database(db_path)
        db.initialize()
        return db

    @app.get("/api/trades")
    def get_trades(limit: int = 100):
        db = get_db()
        result = db.get_trades(limit=limit)
        db.close()
        return result

    @app.get("/api/decisions")
    def get_decisions(limit: int = 50):
        db = get_db()
        result = db.get_decisions(limit=limit)
        db.close()
        return result

    @app.get("/api/portfolio")
    def get_portfolio_snapshots(limit: int = 100):
        db = get_db()
        result = db.get_portfolio_snapshots(limit=limit)
        db.close()
        return result

    @app.get("/api/discovery")
    def get_discovery(limit: int = 50):
        db = get_db()
        result = db.get_discovery_log(limit=limit)
        db.close()
        return result

    @app.get("/api/signals/{ticker}")
    def get_signals(ticker: str, limit: int = 50):
        db = get_db()
        result = db.get_signals(ticker=ticker, limit=limit)
        db.close()
        return result

    @app.get("/api/config")
    def get_config():
        return load_config()

    @app.put("/api/config")
    def update_config(new_config: dict):
        import yaml
        from claude_invest.config.loader import DEFAULT_CONFIG_PATH
        with open(DEFAULT_CONFIG_PATH, "w") as f:
            yaml.dump(new_config, f, default_flow_style=False)
        return {"status": "updated"}

    @app.get("/api/stats")
    def get_stats():
        db = get_db()
        snapshots = db.get_portfolio_snapshots(limit=30)
        db.close()
        if not snapshots:
            return {"daily_pnl": 0, "total_snapshots": 0}
        return {
            "latest_value": snapshots[0]["total_value"],
            "latest_daily_pnl": snapshots[0]["daily_pnl"],
            "total_snapshots": len(snapshots),
        }

    return app


if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api_server.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/claude_invest/modules/api_server.py tests/test_api_server.py
git commit -m "feat: add FastAPI server with REST endpoints for dashboard"
```

---

### Task 12: Integration Test — Full Pipeline

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

`tests/test_integration.py`:
```python
import json
import subprocess
import sys

import pytest
from unittest.mock import patch, MagicMock
from claude_invest.config.loader import load_config
from claude_invest.modules.db import Database
from claude_invest.modules.risk_manager import RiskManager


def test_full_decision_pipeline(tmp_db_path, sample_config):
    """Simulate a full poll cycle: portfolio -> scan -> analyze -> risk check -> execute."""
    config, _ = sample_config
    db = Database(tmp_db_path)
    db.initialize()

    # 1. Portfolio state
    portfolio = {
        "equity": 5000, "cash": 4800, "buying_power": 9600,
        "daily_pnl": 25.0, "positions": [], "position_count": 0,
    }
    db.insert_portfolio_snapshot({
        "total_value": portfolio["equity"], "cash": portfolio["cash"],
        "positions_value": 200, "daily_pnl": portfolio["daily_pnl"],
    })

    # 2. Simulate scanner finding a candidate
    db.insert_discovery({
        "ticker": "AAPL", "volume_score": 3.5, "news_score": 0.7,
        "sentiment": 0.65, "action_taken": "flagged",
    })

    # 3. Simulate signal analysis
    db.insert_signal({
        "ticker": "AAPL", "sentiment_score": 0.65, "rsi": 42.0,
        "macd": 1.5, "volume_ratio": 3.5, "trend": "bullish",
    })

    # 4. Risk check
    risk_mgr = RiskManager(config, db)
    trade_check = risk_mgr.check_trade("AAPL", 1, 150.0, portfolio)
    assert trade_check["approved"] is True

    # 5. Simulate trade execution
    db.insert_trade({
        "symbol": "AAPL", "side": "buy", "qty": 1, "price": 150.0,
        "order_id": "int-test-1", "trade_type": "swing", "status": "filled",
    })

    # 6. Log decision
    db.insert_decision({
        "ticker": "AAPL", "action": "buy",
        "reasoning": "Strong bullish signals: RSI 42, positive sentiment 0.65, volume 3.5x",
        "signals_snapshot": json.dumps({"rsi": 42, "sentiment": 0.65, "trend": "bullish"}),
    })

    # Verify full state
    trades = db.get_trades(symbol="AAPL")
    assert len(trades) == 1
    decisions = db.get_decisions()
    assert len(decisions) == 1
    assert "bullish" in decisions[0]["reasoning"]
    signals = db.get_signals(ticker="AAPL")
    assert signals[0]["trend"] == "bullish"

    db.close()


def test_risk_blocks_when_limits_exceeded(tmp_db_path, sample_config):
    """Verify the system stops trading when risk limits are hit."""
    config, _ = sample_config
    db = Database(tmp_db_path)
    db.initialize()
    risk_mgr = RiskManager(config, db)

    # Daily loss exceeded
    portfolio_loss = {
        "equity": 4800, "daily_pnl": -200,
        "position_count": 2, "positions": [],
    }
    result = risk_mgr.check_trade("AAPL", 1, 150.0, portfolio_loss)
    assert result["approved"] is False

    # Max positions hit
    portfolio_full = {
        "equity": 5000, "daily_pnl": 0,
        "position_count": 8, "positions": [],
    }
    result = risk_mgr.check_trade("AAPL", 1, 150.0, portfolio_full)
    assert result["approved"] is False

    # PDT limit
    db.record_day_trade("dt1")
    db.record_day_trade("dt2")
    db.record_day_trade("dt3")
    assert risk_mgr.check_pdt_allowed() is False

    db.close()
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/test_integration.py -v`
Expected: All 2 tests PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS (should be ~36 tests total across all files)

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "feat: add integration tests for full trading pipeline"
```

---

### Task 13: Environment Setup and First Run

**Files:**
- Create: `.env` (from `.env.example`, user fills in real keys)

- [ ] **Step 1: Set up .env with Alpaca paper trading keys**

Copy `.env.example` to `.env` and fill in real API keys:
```bash
cp .env.example .env
```

Edit `.env` with your Alpaca paper trading API key and secret. Get these from https://app.alpaca.markets/paper/dashboard/overview (Paper Trading > API Keys).

- [ ] **Step 2: Verify Alpaca connection**

Run:
```bash
source .venv/bin/activate
python -c "
from claude_invest.modules.portfolio import get_portfolio
import json
print(json.dumps(get_portfolio(), indent=2))
"
```

Expected: JSON output showing paper account equity, cash, positions.

- [ ] **Step 3: Run the scanner live**

Run:
```bash
python -m claude_invest.main scan
```

Expected: JSON output with a list of candidates, each with `flagged`, `volume_ratio`, `sentiment_score` fields.

- [ ] **Step 4: Start the API server**

Run:
```bash
python -m claude_invest.modules.api_server
```

Expected: Server starts on `http://0.0.0.0:8000`. Visit `http://localhost:8000/api/config` in browser to verify.

- [ ] **Step 5: Commit .env.example only (never .env)**

```bash
git status  # verify .env is in .gitignore
git commit --allow-empty -m "chore: verified Alpaca connection and first run"
```
