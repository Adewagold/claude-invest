# Core Holdings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a long-term buy-and-hold portfolio tier with DCA entries, sentiment-only exits, and quarterly rebalancing alongside the existing trading system.

**Architecture:** New `core_engine.py` module handles core holdings logic. Capital split between trading and core pools via settings.yaml. New DB tables for core_buys and rebalance_log. Dashboard gets /core page. Risk manager updated for dual capital pools.

**Tech Stack:** Python 3.12, SQLite3, FastAPI, Next.js 16, SWR, Alpaca API

**Spec:** `docs/superpowers/specs/2026-04-27-core-holdings-design.md`

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `src/claude_invest/modules/core_engine.py` | Core holdings logic: DCA entries, exits, rebalance, status |
| `tests/test_core_engine.py` | Unit tests for core engine |
| `tests/test_core_db.py` | Unit tests for new DB tables and query methods |
| `tests/test_capital_split.py` | Unit tests for capital pool isolation |

### Modified Files
| File | Changes |
|------|---------|
| `src/claude_invest/config/settings.yaml` | Add `capital_split` and `core_holdings` sections |
| `src/claude_invest/modules/db.py` | Add `core_buys` table, `rebalance_log` table, 5 new query methods |
| `src/claude_invest/modules/strategy_engine.py` | `get_strategy_capital()` uses trading pool, not total capital |
| `src/claude_invest/modules/risk_manager.py` | Dual capital pool: `trading_capital`, `core_capital`, pool-aware `check_trade()` |
| `src/claude_invest/main.py` | 6 new CLI commands: `core-status`, `core-buy`, `core-add`, `core-remove`, `core-rebalance`, `core-cycle` |

---

## Task 1: Update settings.yaml

**Files:**
- Modify: `src/claude_invest/config/settings.yaml`

- [ ] **Step 1: Write failing test for capital_split config validation**

Create `tests/test_capital_split.py`:

```python
import pytest
import yaml
from pathlib import Path


def test_capital_split_present(sample_config_with_core):
    config, _ = sample_config_with_core
    assert "capital_split" in config
    assert "trading" in config["capital_split"]
    assert "core" in config["capital_split"]


def test_capital_split_sums_to_one(sample_config_with_core):
    config, _ = sample_config_with_core
    total = config["capital_split"]["trading"] + config["capital_split"]["core"]
    assert abs(total - 1.0) < 1e-9


def test_core_holdings_section_present(sample_config_with_core):
    config, _ = sample_config_with_core
    ch = config["core_holdings"]
    assert ch["enabled"] is True
    assert "buy_list" in ch
    assert "entry" in ch
    assert "exit" in ch
    assert "rebalance" in ch


def test_buy_list_weights_sum_to_one(sample_config_with_core):
    config, _ = sample_config_with_core
    total = sum(item["weight"] for item in config["core_holdings"]["buy_list"])
    assert abs(total - 1.0) < 1e-9


def test_trading_capital_calculation(sample_config_with_core):
    config, _ = sample_config_with_core
    total = config["capital"]
    trading = total * config["capital_split"]["trading"]
    core = total * config["capital_split"]["core"]
    assert trading == 2500.0
    assert core == 2500.0


def test_strategy_capital_uses_trading_pool(sample_config_with_core):
    from claude_invest.modules.strategy_engine import get_strategy_capital
    config, _ = sample_config_with_core
    # mean_reversion: 0.33 of trading pool (2500), not total (5000)
    capital = get_strategy_capital(config, "mean_reversion")
    assert capital == pytest.approx(2500 * 0.33, rel=1e-3)
    assert capital < 1000  # Must be less than 1000 (not 1650 from full capital)
```

Add a `sample_config_with_core` fixture to `tests/conftest.py`:

```python
@pytest.fixture
def sample_config_with_core(tmp_path):
    """Config with capital_split and core_holdings sections."""
    config = {
        "mode": "paper",
        "capital": 5000,
        "max_positions": 8,
        "max_per_ticker": 0.10,
        "position_size_pct": 0.02,
        "daily_loss_limit": -150,
        "pdt_tracking": True,
        "capital_split": {
            "trading": 0.50,
            "core": 0.50,
        },
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
        "portfolio": {
            "allocation": {"safe": 0.30, "neutral": 0.40, "risk": 0.30},
            "drift_threshold": 0.10,
            "sectors": {"overrides": {"TRUMP/USD": "meme"}},
            "time_horizon": {"short_term_max_days": 30, "long_term_min_days": 30},
        },
        "risk_tiers": {
            "safe": ["bonds", "reits", "dividend", "utilities", "consumer_staples"],
            "neutral": ["large_cap", "technology", "healthcare", "financial", "industrial", "energy"],
            "risk": ["small_cap", "biotech", "meme", "crypto", "penny", "speculative"],
        },
        "strategies": {
            "active": ["mean_reversion", "trend_pullback", "momentum"],
            "mean_reversion": {
                "name": "RSI(2) Mean Reversion",
                "enabled": True,
                "capital_pct": 0.33,
                "params": {
                    "rsi_period": 2,
                    "rsi_buy_threshold": 25,
                    "rsi_sell_threshold": 65,
                    "max_hold_bars": 5,
                    "require_above_ma200": True,
                    "stop_loss_pct": 0.01,
                    "take_profit_pct": 0.02,
                },
            },
            "trend_pullback": {
                "name": "MACD 5/35/5 Trend",
                "enabled": True,
                "capital_pct": 0.34,
                "params": {},
            },
            "momentum": {
                "name": "Momentum Breakout",
                "enabled": True,
                "capital_pct": 0.33,
                "params": {},
            },
        },
        "core_holdings": {
            "enabled": True,
            "max_positions": 15,
            "buy_list": [
                {"symbol": "NVDA", "sector": "tech", "weight": 0.10},
                {"symbol": "MSFT", "sector": "tech", "weight": 0.10},
                {"symbol": "GOOGL", "sector": "tech", "weight": 0.10},
                {"symbol": "AAPL", "sector": "tech", "weight": 0.10},
                {"symbol": "AMZN", "sector": "tech", "weight": 0.10},
                {"symbol": "META", "sector": "tech", "weight": 0.10},
                {"symbol": "AMD", "sector": "semiconductors", "weight": 0.10},
                {"symbol": "JPM", "sector": "finance", "weight": 0.10},
                {"symbol": "JNJ", "sector": "healthcare", "weight": 0.10},
                {"symbol": "SPY", "sector": "etf", "weight": 0.10},
            ],
            "entry": {
                "mode": "dca_on_dip",
                "sma_period": 50,
                "dca_interval_days": 7,
                "max_per_buy": 0.02,
            },
            "exit": {
                "sell_on_signals": False,
                "sell_on_removal": True,
                "sentiment_exit_threshold": -0.3,
                "sentiment_exit_days": 5,
                "max_position_pct": 0.20,
            },
            "rebalance": {
                "interval_days": 90,
                "drift_threshold": 0.05,
            },
        },
    }
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(yaml.dump(config))
    return config, str(config_path)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest tests/test_capital_split.py -v 2>&1 | head -40
```
Expected: Multiple failures (config doesn't have these keys yet, `get_strategy_capital` uses total capital).

- [ ] **Step 3: Update settings.yaml**

In `src/claude_invest/config/settings.yaml`, add after the `capital: 5000` line:

```yaml
capital_split:
  trading: 0.50    # $2,500 for active strategies (mean_reversion, trend_pullback, momentum)
  core: 0.50       # $2,500 for core holdings
```

Then add the full `core_holdings` block at the end of the file:

```yaml
core_holdings:
  enabled: true
  max_positions: 15
  buy_list:
    - {symbol: NVDA, sector: tech, weight: 0.10}
    - {symbol: MSFT, sector: tech, weight: 0.10}
    - {symbol: GOOGL, sector: tech, weight: 0.10}
    - {symbol: AAPL, sector: tech, weight: 0.10}
    - {symbol: AMZN, sector: tech, weight: 0.10}
    - {symbol: META, sector: tech, weight: 0.10}
    - {symbol: AMD, sector: semiconductors, weight: 0.10}
    - {symbol: JPM, sector: finance, weight: 0.10}
    - {symbol: JNJ, sector: healthcare, weight: 0.10}
    - {symbol: SPY, sector: etf, weight: 0.10}
  entry:
    mode: dca_on_dip
    sma_period: 50
    dca_interval_days: 7
    max_per_buy: 0.02
  exit:
    sell_on_signals: false
    sell_on_removal: true
    sentiment_exit_threshold: -0.3
    sentiment_exit_days: 5
    max_position_pct: 0.20
  rebalance:
    interval_days: 90
    drift_threshold: 0.05
```

- [ ] **Step 4: Verify config loads cleanly**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/python -c "
from claude_invest.config.loader import load_config
c = load_config()
assert 'capital_split' in c
assert 'core_holdings' in c
weights = sum(x['weight'] for x in c['core_holdings']['buy_list'])
assert abs(weights - 1.0) < 1e-9, f'Weights sum to {weights}'
print('capital_split:', c['capital_split'])
print('buy_list count:', len(c['core_holdings']['buy_list']))
print('weights sum:', weights)
print('OK')
"
```
Expected: Prints config values, `OK`.

- [ ] **Step 5: Commit**

```bash
git add src/claude_invest/config/settings.yaml tests/conftest.py tests/test_capital_split.py
git commit -m "feat: add capital_split and core_holdings config sections"
```

---

## Task 2: Database Tables

**Files:**
- Modify: `src/claude_invest/modules/db.py`
- Create: `tests/test_core_db.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_core_db.py`:

```python
import pytest
from claude_invest.modules.db import Database


def test_core_buys_table_exists(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    tables = db.list_tables()
    assert "core_buys" in tables
    db.close()


def test_rebalance_log_table_exists(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    tables = db.list_tables()
    assert "rebalance_log" in tables
    db.close()


def test_insert_core_buy(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    db.insert_core_buy({
        "symbol": "NVDA",
        "qty": 0.5,
        "price": 500.00,
        "cost_basis": 250.00,
        "position_id": "core-pos-001",
        "order_id": "ord-abc",
    })
    buys = db.get_core_buys("NVDA")
    assert len(buys) == 1
    assert buys[0]["symbol"] == "NVDA"
    assert buys[0]["qty"] == 0.5
    assert buys[0]["price"] == 500.00
    assert buys[0]["cost_basis"] == 250.00
    assert buys[0]["position_id"] == "core-pos-001"
    db.close()


def test_get_core_buys_by_symbol(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    db.insert_core_buy({"symbol": "NVDA", "qty": 0.5, "price": 500.0, "cost_basis": 250.0})
    db.insert_core_buy({"symbol": "MSFT", "qty": 1.0, "price": 400.0, "cost_basis": 400.0})
    db.insert_core_buy({"symbol": "NVDA", "qty": 0.3, "price": 490.0, "cost_basis": 147.0})
    nvda = db.get_core_buys("NVDA")
    assert len(nvda) == 2
    msft = db.get_core_buys("MSFT")
    assert len(msft) == 1
    db.close()


def test_get_last_core_buy_date(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    db.insert_core_buy({"symbol": "NVDA", "qty": 0.5, "price": 500.0, "cost_basis": 250.0})
    result = db.get_last_core_buy_date("NVDA")
    assert result is not None
    # Never bought MSFT — should return None
    assert db.get_last_core_buy_date("MSFT") is None
    db.close()


def test_insert_rebalance_log(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    db.insert_rebalance_log({
        "symbol": "NVDA",
        "action": "sell",
        "qty": 0.2,
        "price": 520.0,
        "reason": "overweight",
        "old_weight": 0.15,
        "new_weight": 0.10,
    })
    logs = db.get_rebalance_log()
    assert len(logs) == 1
    assert logs[0]["symbol"] == "NVDA"
    assert logs[0]["action"] == "sell"
    assert logs[0]["reason"] == "overweight"
    assert logs[0]["old_weight"] == 0.15
    assert logs[0]["new_weight"] == 0.10
    db.close()


def test_get_rebalance_log_limit(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    for i in range(5):
        db.insert_rebalance_log({
            "symbol": f"SYM{i}",
            "action": "buy",
            "qty": 1.0,
            "price": 100.0,
            "reason": "underweight",
        })
    logs = db.get_rebalance_log(limit=3)
    assert len(logs) == 3
    db.close()


def test_get_all_core_buys_no_symbol_filter(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    db.insert_core_buy({"symbol": "NVDA", "qty": 0.5, "price": 500.0, "cost_basis": 250.0})
    db.insert_core_buy({"symbol": "MSFT", "qty": 1.0, "price": 400.0, "cost_basis": 400.0})
    all_buys = db.get_core_buys()
    assert len(all_buys) == 2
    db.close()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest tests/test_core_db.py -v 2>&1 | head -40
```
Expected: All tests fail with `AttributeError` (methods don't exist yet).

- [ ] **Step 3: Add core_buys and rebalance_log tables to db.py initialize()**

In `src/claude_invest/modules/db.py`, inside the `initialize()` method's `conn.executescript("""...""")` block, append these two `CREATE TABLE` statements before the closing `""")`:

```python
            CREATE TABLE IF NOT EXISTS core_buys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                symbol TEXT NOT NULL,
                qty REAL NOT NULL,
                price REAL NOT NULL,
                cost_basis REAL NOT NULL,
                position_id TEXT,
                order_id TEXT
            );

            CREATE TABLE IF NOT EXISTS rebalance_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                qty REAL NOT NULL,
                price REAL NOT NULL,
                reason TEXT NOT NULL,
                old_weight REAL,
                new_weight REAL
            );
```

- [ ] **Step 4: Add insert_core_buy() method to Database class**

After the `get_discovery_log()` method in `src/claude_invest/modules/db.py`, add:

```python
    def insert_core_buy(self, buy: dict):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO core_buys (symbol, qty, price, cost_basis, position_id, order_id) VALUES (?, ?, ?, ?, ?, ?)",
            (buy["symbol"], buy["qty"], buy["price"], buy["cost_basis"],
             buy.get("position_id"), buy.get("order_id")),
        )
        conn.commit()

    def get_core_buys(self, symbol: str | None = None, limit: int = 200) -> list[dict]:
        conn = self._get_conn()
        if symbol:
            cursor = conn.execute(
                "SELECT * FROM core_buys WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?",
                (symbol, limit),
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM core_buys ORDER BY timestamp DESC LIMIT ?", (limit,)
            )
        return [dict(row) for row in cursor.fetchall()]

    def get_last_core_buy_date(self, symbol: str) -> str | None:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT timestamp FROM core_buys WHERE symbol = ? ORDER BY timestamp DESC LIMIT 1",
            (symbol,),
        )
        row = cursor.fetchone()
        return row["timestamp"] if row else None

    def insert_rebalance_log(self, entry: dict):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO rebalance_log (symbol, action, qty, price, reason, old_weight, new_weight) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (entry["symbol"], entry["action"], entry["qty"], entry["price"],
             entry["reason"], entry.get("old_weight"), entry.get("new_weight")),
        )
        conn.commit()

    def get_rebalance_log(self, limit: int = 100) -> list[dict]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM rebalance_log ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]
```

- [ ] **Step 5: Run tests — all should pass**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest tests/test_core_db.py -v
```
Expected: 8/8 tests pass.

- [ ] **Step 6: Run full test suite to ensure no regressions**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest --tb=short -q
```
Expected: All pre-existing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add src/claude_invest/modules/db.py tests/test_core_db.py
git commit -m "feat: add core_buys and rebalance_log tables with query methods"
```

---

## Task 3: Update strategy_engine

**Files:**
- Modify: `src/claude_invest/modules/strategy_engine.py`
- Update: `tests/test_capital_split.py` (add strategy engine tests)

- [ ] **Step 1: Write failing test for trading pool capital**

Add to `tests/test_capital_split.py`:

```python
def test_get_strategy_capital_uses_trading_pool(sample_config_with_core):
    from claude_invest.modules.strategy_engine import get_strategy_capital
    config, _ = sample_config_with_core
    # capital=5000, capital_split.trading=0.50 → trading_capital=2500
    # mean_reversion capital_pct=0.33 → 2500 * 0.33 = 825
    capital = get_strategy_capital(config, "mean_reversion")
    assert capital == pytest.approx(825.0, rel=1e-3)


def test_get_strategy_capital_falls_back_without_split(sample_config):
    from claude_invest.modules.strategy_engine import get_strategy_capital
    config, _ = sample_config
    # No capital_split in sample_config → falls back to total capital
    # But strategies block is also absent from sample_config — returns 0.33 of 5000
    # This test ensures backward compat: no capital_split = use total capital
    config["strategies"] = {
        "mean_reversion": {"capital_pct": 0.33, "enabled": True}
    }
    capital = get_strategy_capital(config, "mean_reversion")
    assert capital == pytest.approx(5000 * 0.33, rel=1e-3)


def test_all_trading_strategies_use_trading_pool(sample_config_with_core):
    from claude_invest.modules.strategy_engine import get_strategy_capital, get_active_strategies
    config, _ = sample_config_with_core
    strategies = get_active_strategies(config)
    trading_capital = config["capital"] * config["capital_split"]["trading"]
    for strat in strategies:
        cap = get_strategy_capital(config, strat["id"])
        expected = trading_capital * strat["capital_pct"]
        assert cap == pytest.approx(expected, rel=1e-3), (
            f"{strat['id']}: expected {expected}, got {cap}"
        )
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest tests/test_capital_split.py::test_get_strategy_capital_uses_trading_pool -v
```
Expected: `AssertionError` — `get_strategy_capital` returns `5000 * 0.33 = 1650`, not `2500 * 0.33 = 825`.

- [ ] **Step 3: Update get_strategy_capital() in strategy_engine.py**

Replace the existing `get_strategy_capital()` function in `src/claude_invest/modules/strategy_engine.py`:

```python
def get_strategy_capital(config: dict, strategy_id: str) -> float:
    """Calculate capital allocated to a trading strategy.

    When capital_split is configured, strategy capital is a fraction of the
    trading pool only (not total capital). Falls back to total capital when
    capital_split is absent for backward compatibility.
    """
    total_capital = config.get("capital", 5000)
    capital_split = config.get("capital_split", {})
    trading_fraction = capital_split.get("trading", 1.0)
    trading_capital = total_capital * trading_fraction

    strategies_config = config.get("strategies", {})
    strat = strategies_config.get(strategy_id, {})
    return trading_capital * strat.get("capital_pct", 0.33)
```

- [ ] **Step 4: Run all capital split tests — all should pass**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest tests/test_capital_split.py -v
```
Expected: All tests pass.

- [ ] **Step 5: Verify the strategies command output reflects new capital**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/python -c "
from claude_invest.config.loader import load_config
from claude_invest.modules.strategy_engine import get_strategy_capital
c = load_config()
for name in ['mean_reversion', 'trend_pullback', 'momentum']:
    print(f'{name}: \${get_strategy_capital(c, name):.2f}')
"
```
Expected: Each strategy shows ~$825 (not ~$1650).

- [ ] **Step 6: Run full test suite**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest --tb=short -q
```
Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/claude_invest/modules/strategy_engine.py tests/test_capital_split.py
git commit -m "feat: strategy_engine uses trading pool capital when capital_split is configured"
```

---

## Task 4: Update risk_manager

**Files:**
- Modify: `src/claude_invest/modules/risk_manager.py`
- Create: `tests/test_risk_manager_core.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_risk_manager_core.py`:

```python
import pytest
from claude_invest.modules.db import Database
from claude_invest.modules.risk_manager import RiskManager


@pytest.fixture
def risk_manager_with_split(tmp_db_path, sample_config_with_core):
    config, _ = sample_config_with_core
    db = Database(tmp_db_path)
    db.initialize()
    rm = RiskManager(config, db)
    yield rm
    db.close()


@pytest.fixture
def mock_portfolio():
    return {
        "daily_pnl": 0.0,
        "position_count": 2,
        "positions": [],
    }


def test_risk_manager_has_trading_capital(risk_manager_with_split):
    # capital=5000, trading split=0.50 → trading_capital=2500
    assert risk_manager_with_split.trading_capital == 2500.0


def test_risk_manager_has_core_capital(risk_manager_with_split):
    # capital=5000, core split=0.50 → core_capital=2500
    assert risk_manager_with_split.core_capital == 2500.0


def test_risk_manager_backward_compat_no_split(tmp_db_path, sample_config):
    """Without capital_split, trading_capital == total capital."""
    config, _ = sample_config
    db = Database(tmp_db_path)
    db.initialize()
    rm = RiskManager(config, db)
    assert rm.trading_capital == 5000.0
    assert rm.core_capital == 0.0
    db.close()


def test_check_trade_trading_uses_trading_capital(risk_manager_with_split, mock_portfolio):
    # trading capital=2500, max_per_ticker=0.10 → max_exposure=250
    result = risk_manager_with_split.check_trade("AAPL", qty=1, price=300.0, portfolio=mock_portfolio, strategy_type="trading")
    assert result["approved"] is False
    assert "250" in result["reason"]  # max is $250 from trading pool


def test_check_trade_core_uses_core_capital(risk_manager_with_split, mock_portfolio):
    # core capital=2500, max_per_buy=0.02 → max $50 per core buy
    # qty=1, price=30.0 → $30, within $50 → approved
    result = risk_manager_with_split.check_trade("NVDA", qty=1, price=30.0, portfolio=mock_portfolio, strategy_type="core_holdings")
    assert result["approved"] is True


def test_check_trade_core_rejects_over_max_per_buy(risk_manager_with_split, mock_portfolio):
    # core max_per_buy=0.02 of 2500 = $50
    # qty=1, price=100.0 → $100 > $50 → rejected
    result = risk_manager_with_split.check_trade("NVDA", qty=1, price=100.0, portfolio=mock_portfolio, strategy_type="core_holdings")
    assert result["approved"] is False
    assert "50" in result["reason"]


def test_daily_loss_limit_applies_to_both_pools(risk_manager_with_split, mock_portfolio):
    mock_portfolio["daily_pnl"] = -200.0  # below -150 limit
    result_trading = risk_manager_with_split.check_trade("AAPL", qty=1, price=10.0, portfolio=mock_portfolio, strategy_type="trading")
    result_core = risk_manager_with_split.check_trade("NVDA", qty=1, price=10.0, portfolio=mock_portfolio, strategy_type="core_holdings")
    assert result_trading["approved"] is False
    assert result_core["approved"] is False
    assert "Daily loss limit" in result_trading["reason"]
    assert "Daily loss limit" in result_core["reason"]


def test_calculate_position_size_uses_trading_capital(risk_manager_with_split):
    # trading_capital=2500, position_size_pct=0.02 → $50 target
    # price=25 → qty=2
    qty = risk_manager_with_split.calculate_position_size(price=25.0)
    assert qty == 2


def test_calculate_core_position_size(risk_manager_with_split):
    # core_capital=2500, max_per_buy=0.02 → $50
    # price=25 → qty=2
    qty = risk_manager_with_split.calculate_core_position_size(price=25.0)
    assert qty == 2
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest tests/test_risk_manager_core.py -v 2>&1 | head -50
```
Expected: Multiple failures — `trading_capital`, `core_capital`, `calculate_core_position_size` attributes don't exist; `check_trade` has no `strategy_type` param.

- [ ] **Step 3: Rewrite risk_manager.py with dual pool support**

Replace the full contents of `src/claude_invest/modules/risk_manager.py`:

```python
from claude_invest.modules.db import Database


class RiskManager:
    def __init__(self, config: dict, db: Database):
        self.config = config
        self.db = db

        total_capital = config["capital"]
        capital_split = config.get("capital_split", {})
        trading_fraction = capital_split.get("trading", 1.0)
        core_fraction = capital_split.get("core", 0.0)

        self.capital = total_capital  # kept for backward compat
        self.trading_capital = total_capital * trading_fraction
        self.core_capital = total_capital * core_fraction

        self.max_positions = config["max_positions"]
        self.max_per_ticker = config["max_per_ticker"]
        self.position_size_pct = config["position_size_pct"]
        self.daily_loss_limit = config["daily_loss_limit"]
        self.pdt_tracking = config["pdt_tracking"]

    def calculate_position_size(self, price: float) -> int:
        """Calculate trade qty for a trading strategy using trading pool."""
        target_dollars = self.trading_capital * self.position_size_pct
        max_dollars = self.trading_capital * self.max_per_ticker
        dollars = min(target_dollars, max_dollars)
        return int(dollars / price)

    def calculate_core_position_size(self, price: float) -> int:
        """Calculate trade qty for a core holdings buy using core pool."""
        max_per_buy_pct = self.config.get("core_holdings", {}).get("entry", {}).get("max_per_buy", 0.02)
        dollars = self.core_capital * max_per_buy_pct
        return int(dollars / price)

    def check_trade(
        self,
        symbol: str,
        qty: int,
        price: float,
        portfolio: dict,
        strategy_type: str = "trading",
    ) -> dict:
        # Daily loss limit applies to both pools combined
        if portfolio["daily_pnl"] <= self.daily_loss_limit:
            return {"approved": False, "reason": "Daily loss limit reached"}

        if strategy_type == "core_holdings":
            return self._check_core_trade(symbol, qty, price, portfolio)
        else:
            return self._check_trading_trade(symbol, qty, price, portfolio)

    def _check_trading_trade(self, symbol: str, qty: int, price: float, portfolio: dict) -> dict:
        # Check max positions
        if portfolio["position_count"] >= self.max_positions:
            return {"approved": False, "reason": "Max positions reached"}

        # Check per-ticker exposure against trading pool
        existing_exposure = sum(
            p["market_value"]
            for p in portfolio["positions"]
            if p["symbol"] == symbol
        )
        new_exposure = existing_exposure + (qty * price)
        max_exposure = self.trading_capital * self.max_per_ticker

        if new_exposure > max_exposure:
            return {
                "approved": False,
                "reason": f"Ticker exposure would be ${new_exposure:.0f}, max is ${max_exposure:.0f}",
            }

        return {"approved": True, "reason": "Trade within risk limits"}

    def _check_core_trade(self, symbol: str, qty: int, price: float, portfolio: dict) -> dict:
        # Core trades use max_per_buy from core_holdings config
        max_per_buy_pct = self.config.get("core_holdings", {}).get("entry", {}).get("max_per_buy", 0.02)
        max_dollars = self.core_capital * max_per_buy_pct
        trade_value = qty * price

        if trade_value > max_dollars:
            return {
                "approved": False,
                "reason": f"Core buy ${trade_value:.0f} exceeds max_per_buy ${max_dollars:.0f}",
            }

        return {"approved": True, "reason": "Core trade within limits"}

    def check_pdt_allowed(self) -> bool:
        if not self.pdt_tracking:
            return True
        count = self.db.get_day_trade_count(days=5)
        return count < 3
```

- [ ] **Step 4: Run risk manager tests — all should pass**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest tests/test_risk_manager_core.py -v
```
Expected: All 9 tests pass.

- [ ] **Step 5: Run full test suite**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest --tb=short -q
```
Expected: All tests pass. The existing `check_trade()` callers in `main.py` use default `strategy_type="trading"` so they work unchanged.

- [ ] **Step 6: Commit**

```bash
git add src/claude_invest/modules/risk_manager.py tests/test_risk_manager_core.py
git commit -m "feat: add dual capital pool support to risk_manager (trading vs core)"
```

---

## Task 5: Core Engine Module

**Files:**
- Create: `src/claude_invest/modules/core_engine.py`
- Create: `tests/test_core_engine.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_core_engine.py`:

```python
import json
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from claude_invest.modules.db import Database
from claude_invest.modules.core_engine import (
    run_core_cycle,
    check_core_exits,
    rebalance_core,
    get_core_status,
)


@pytest.fixture
def db(tmp_db_path):
    d = Database(tmp_db_path)
    d.initialize()
    yield d
    d.close()


@pytest.fixture
def core_config(sample_config_with_core):
    config, _ = sample_config_with_core
    return config


# --- get_core_status ---

def test_get_core_status_structure(core_config, db):
    mock_portfolio = {"positions": [], "equity": 5000.0, "cash": 5000.0}
    with patch("claude_invest.modules.core_engine.get_portfolio", return_value=mock_portfolio):
        status = get_core_status(core_config, db)
    assert "core_capital" in status
    assert "invested" in status
    assert "cash_remaining" in status
    assert "holdings" in status
    assert "next_rebalance_date" in status
    assert "days_until_rebalance" in status


def test_get_core_status_capital_values(core_config, db):
    mock_portfolio = {"positions": [], "equity": 5000.0, "cash": 5000.0}
    with patch("claude_invest.modules.core_engine.get_portfolio", return_value=mock_portfolio):
        status = get_core_status(core_config, db)
    # core_capital = 5000 * 0.50 = 2500
    assert status["core_capital"] == 2500.0
    assert status["invested"] == 0.0
    assert status["cash_remaining"] == 2500.0


def test_get_core_status_with_holdings(core_config, db):
    db.insert_core_buy({"symbol": "NVDA", "qty": 0.5, "price": 500.0, "cost_basis": 250.0})
    mock_position = {
        "symbol": "NVDA",
        "qty": 0.5,
        "market_value": 275.0,
        "avg_entry_price": 500.0,
        "unrealized_pl": 25.0,
        "trade_type": "core_holdings",
    }
    mock_portfolio = {
        "positions": [mock_position],
        "equity": 5275.0,
        "cash": 5000.0,
    }
    with patch("claude_invest.modules.core_engine.get_portfolio", return_value=mock_portfolio):
        status = get_core_status(core_config, db)
    assert len(status["holdings"]) == 1
    holding = status["holdings"][0]
    assert holding["symbol"] == "NVDA"
    assert holding["current_value"] == 275.0
    assert "weight_actual" in holding
    assert "weight_target" in holding
    assert "drift" in holding
    assert "days_since_buy" in holding


# --- run_core_cycle ---

def test_run_core_cycle_returns_structure(core_config, db):
    mock_portfolio = {"positions": [], "equity": 5000.0, "cash": 5000.0}
    mock_bar = {"close": 490.0, "sma50": 510.0}  # price below SMA50 → dip
    with patch("claude_invest.modules.core_engine.get_portfolio", return_value=mock_portfolio), \
         patch("claude_invest.modules.core_engine._get_price_and_sma", return_value=mock_bar), \
         patch("claude_invest.modules.core_engine.execute_order") as mock_exec:
        mock_exec.return_value = {"status": "filled", "filled_price": 490.0, "order_id": "ord-1"}
        result = run_core_cycle(core_config, db)
    assert "buys" in result
    assert "skips" in result
    assert "exits" in result
    assert "rebalances" in result


def test_run_core_cycle_skips_when_disabled(core_config, db):
    core_config["core_holdings"]["enabled"] = False
    mock_portfolio = {"positions": [], "equity": 5000.0, "cash": 5000.0}
    with patch("claude_invest.modules.core_engine.get_portfolio", return_value=mock_portfolio):
        result = run_core_cycle(core_config, db)
    assert result["buys"] == []
    assert result["skips"] == []


def test_run_core_cycle_dip_entry_triggers_buy(core_config, db):
    mock_portfolio = {"positions": [], "equity": 5000.0, "cash": 5000.0}
    # price < SMA50 → dip entry
    mock_bar = {"close": 490.0, "sma50": 510.0}
    with patch("claude_invest.modules.core_engine.get_portfolio", return_value=mock_portfolio), \
         patch("claude_invest.modules.core_engine._get_price_and_sma", return_value=mock_bar), \
         patch("claude_invest.modules.core_engine.execute_order") as mock_exec:
        mock_exec.return_value = {"status": "filled", "filled_price": 490.0, "order_id": "ord-1"}
        result = run_core_cycle(core_config, db)
    # At least one buy should trigger (NVDA or others on dip)
    assert len(result["buys"]) > 0
    # Verify core_buy was logged to DB
    all_buys = db.get_core_buys()
    assert len(all_buys) > 0


def test_run_core_cycle_dca_fallback_triggers_buy(core_config, db):
    """Even above SMA50, buys if last buy was > dca_interval_days ago."""
    # Insert old buy (10 days ago, > dca_interval_days=7)
    old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
    db._get_conn().execute(
        "INSERT INTO core_buys (timestamp, symbol, qty, price, cost_basis) VALUES (?, ?, ?, ?, ?)",
        (old_ts, "NVDA", 0.1, 500.0, 50.0),
    )
    db._get_conn().commit()

    mock_portfolio = {"positions": [], "equity": 5000.0, "cash": 5000.0}
    # price > SMA50 (not a dip), but DCA fallback should trigger for NVDA
    mock_bar = {"close": 530.0, "sma50": 510.0}
    with patch("claude_invest.modules.core_engine.get_portfolio", return_value=mock_portfolio), \
         patch("claude_invest.modules.core_engine._get_price_and_sma", return_value=mock_bar), \
         patch("claude_invest.modules.core_engine.execute_order") as mock_exec:
        mock_exec.return_value = {"status": "filled", "filled_price": 530.0, "order_id": "ord-2"}
        result = run_core_cycle(core_config, db)
    nvda_buys = [b for b in result["buys"] if b["symbol"] == "NVDA"]
    assert len(nvda_buys) == 1
    assert nvda_buys[0]["reason"] == "dca_fallback"


def test_run_core_cycle_skips_recent_buy_above_sma(core_config, db):
    """Skip if price > SMA50 AND last buy was < dca_interval_days ago."""
    recent_ts = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    db._get_conn().execute(
        "INSERT INTO core_buys (timestamp, symbol, qty, price, cost_basis) VALUES (?, ?, ?, ?, ?)",
        (recent_ts, "NVDA", 0.1, 500.0, 50.0),
    )
    db._get_conn().commit()

    mock_portfolio = {"positions": [], "equity": 5000.0, "cash": 5000.0}
    mock_bar = {"close": 530.0, "sma50": 510.0}  # above SMA, no dip
    with patch("claude_invest.modules.core_engine.get_portfolio", return_value=mock_portfolio), \
         patch("claude_invest.modules.core_engine._get_price_and_sma", return_value=mock_bar), \
         patch("claude_invest.modules.core_engine.execute_order"):
        result = run_core_cycle(core_config, db)
    nvda_skips = [s for s in result["skips"] if s["symbol"] == "NVDA"]
    assert len(nvda_skips) == 1


# --- check_core_exits ---

def test_check_core_exits_removal(core_config, db):
    """Stock removed from buy_list triggers sell."""
    # SPY is in buy_list; create a holding for a symbol NOT in buy_list
    mock_position = {
        "symbol": "TSLA",  # not in buy_list
        "qty": 1.0,
        "market_value": 200.0,
        "trade_type": "core_holdings",
    }
    mock_portfolio = {"positions": [mock_position], "equity": 5200.0, "cash": 5000.0}
    with patch("claude_invest.modules.core_engine.get_portfolio", return_value=mock_portfolio), \
         patch("claude_invest.modules.core_engine.execute_order") as mock_exec:
        mock_exec.return_value = {"status": "filled", "filled_price": 200.0, "order_id": "ord-3"}
        exits = check_core_exits(core_config, db)
    assert len(exits) == 1
    assert exits[0]["symbol"] == "TSLA"
    assert exits[0]["reason"] == "removal"


def test_check_core_exits_sentiment(core_config, db):
    """Sustained negative sentiment triggers sell."""
    # Insert 5 consecutive negative sentiment signals for NVDA
    for _ in range(5):
        db.insert_signal({
            "ticker": "NVDA",
            "sentiment_score": -0.5,
            "rsi": None, "macd": None, "volume_ratio": None, "trend": None,
        })
    mock_position = {
        "symbol": "NVDA",
        "qty": 0.5,
        "market_value": 250.0,
        "trade_type": "core_holdings",
    }
    mock_portfolio = {"positions": [mock_position], "equity": 5250.0, "cash": 5000.0}
    with patch("claude_invest.modules.core_engine.get_portfolio", return_value=mock_portfolio), \
         patch("claude_invest.modules.core_engine.execute_order") as mock_exec:
        mock_exec.return_value = {"status": "filled", "filled_price": 500.0, "order_id": "ord-4"}
        exits = check_core_exits(core_config, db)
    nvda_exits = [e for e in exits if e["symbol"] == "NVDA"]
    assert len(nvda_exits) == 1
    assert nvda_exits[0]["reason"] == "sentiment"


def test_check_core_exits_no_technical_sells(core_config, db):
    """sell_on_signals=False means RSI/MACD don't trigger exits."""
    # High RSI scenario — should NOT trigger sell
    db.insert_signal({
        "ticker": "NVDA",
        "sentiment_score": 0.5,  # positive sentiment
        "rsi": 80.0,  # overbought RSI
        "macd": 5.0,
        "volume_ratio": None,
        "trend": "up",
    })
    mock_position = {
        "symbol": "NVDA",
        "qty": 0.5,
        "market_value": 250.0,
        "trade_type": "core_holdings",
    }
    mock_portfolio = {"positions": [mock_position], "equity": 5250.0, "cash": 5000.0}
    with patch("claude_invest.modules.core_engine.get_portfolio", return_value=mock_portfolio), \
         patch("claude_invest.modules.core_engine.execute_order"):
        exits = check_core_exits(core_config, db)
    nvda_exits = [e for e in exits if e["symbol"] == "NVDA"]
    assert len(nvda_exits) == 0  # No exit on technical signals


# --- rebalance_core ---

def test_rebalance_core_overweight_sells(core_config, db):
    """Position above target weight + drift_threshold triggers a sell."""
    # NVDA target=0.10, current=0.20 → overweight by 0.10 > drift_threshold(0.05)
    mock_positions = [
        {"symbol": "NVDA", "qty": 2.0, "market_value": 500.0, "trade_type": "core_holdings"},
        {"symbol": "MSFT", "qty": 1.0, "market_value": 400.0, "trade_type": "core_holdings"},
        {"symbol": "SPY", "qty": 2.0, "market_value": 600.0, "trade_type": "core_holdings"},
    ]
    # total core value = 1500; NVDA weight = 500/1500 = 0.333, target=0.10
    mock_portfolio = {"positions": mock_positions, "equity": 6500.0, "cash": 5000.0}
    with patch("claude_invest.modules.core_engine.get_portfolio", return_value=mock_portfolio), \
         patch("claude_invest.modules.core_engine._get_price_and_sma", return_value={"close": 250.0, "sma50": 240.0}), \
         patch("claude_invest.modules.core_engine.execute_order") as mock_exec:
        mock_exec.return_value = {"status": "filled", "filled_price": 250.0, "order_id": "ord-5"}
        rebalances = rebalance_core(core_config, db)
    nvda_sells = [r for r in rebalances if r["symbol"] == "NVDA" and r["action"] == "sell"]
    assert len(nvda_sells) == 1
    assert nvda_sells[0]["reason"] == "overweight"


def test_rebalance_core_underweight_buys(core_config, db):
    """Position below target weight - drift_threshold triggers a buy."""
    # MSFT target=0.10, current=0.02 → underweight
    mock_positions = [
        {"symbol": "NVDA", "qty": 2.0, "market_value": 900.0, "trade_type": "core_holdings"},
        {"symbol": "MSFT", "qty": 0.1, "market_value": 40.0, "trade_type": "core_holdings"},
    ]
    # total=940; MSFT weight=40/940=0.042, target=0.10, drift=0.058 > 0.05 → underweight
    mock_portfolio = {"positions": mock_positions, "equity": 5940.0, "cash": 5000.0}
    with patch("claude_invest.modules.core_engine.get_portfolio", return_value=mock_portfolio), \
         patch("claude_invest.modules.core_engine._get_price_and_sma", return_value={"close": 400.0, "sma50": 410.0}), \
         patch("claude_invest.modules.core_engine.execute_order") as mock_exec:
        mock_exec.return_value = {"status": "filled", "filled_price": 400.0, "order_id": "ord-6"}
        rebalances = rebalance_core(core_config, db)
    msft_buys = [r for r in rebalances if r["symbol"] == "MSFT" and r["action"] == "buy"]
    assert len(msft_buys) == 1
    assert msft_buys[0]["reason"] == "underweight"


def test_rebalance_core_logs_to_db(core_config, db):
    mock_positions = [
        {"symbol": "NVDA", "qty": 2.0, "market_value": 500.0, "trade_type": "core_holdings"},
        {"symbol": "MSFT", "qty": 0.1, "market_value": 40.0, "trade_type": "core_holdings"},
    ]
    mock_portfolio = {"positions": mock_positions, "equity": 5540.0, "cash": 5000.0}
    with patch("claude_invest.modules.core_engine.get_portfolio", return_value=mock_portfolio), \
         patch("claude_invest.modules.core_engine._get_price_and_sma", return_value={"close": 250.0, "sma50": 240.0}), \
         patch("claude_invest.modules.core_engine.execute_order") as mock_exec:
        mock_exec.return_value = {"status": "filled", "filled_price": 250.0, "order_id": "ord-7"}
        rebalance_core(core_config, db)
    logs = db.get_rebalance_log()
    assert len(logs) > 0
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest tests/test_core_engine.py -v 2>&1 | head -30
```
Expected: `ModuleNotFoundError: No module named 'claude_invest.modules.core_engine'`.

- [ ] **Step 3: Create core_engine.py**

Create `src/claude_invest/modules/core_engine.py`:

```python
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from claude_invest.modules.db import Database
from claude_invest.modules.executor import execute_order
from claude_invest.modules.portfolio import get_portfolio
from claude_invest.modules.technicals import analyze_technicals


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_price_and_sma(symbol: str, sma_period: int = 50) -> dict:
    """Fetch current price and SMA from technicals module."""
    data = analyze_technicals(symbol)
    return {
        "close": data.get("price") or data.get("close", 0.0),
        "sma50": data.get("sma50") or data.get(f"sma{sma_period}", 0.0),
    }


def _get_core_positions(portfolio: dict) -> list[dict]:
    """Extract positions tagged as core_holdings from portfolio."""
    return [
        p for p in portfolio.get("positions", [])
        if p.get("trade_type") == "core_holdings"
    ]


def _days_since(timestamp_str: str) -> int:
    """Return days elapsed since a timestamp string (UTC)."""
    try:
        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).days
    except (ValueError, AttributeError):
        return 9999


def _get_buy_list(config: dict) -> list[dict]:
    return config.get("core_holdings", {}).get("buy_list", [])


def _get_symbol_target_weight(config: dict, symbol: str) -> float:
    for item in _get_buy_list(config):
        if item["symbol"] == symbol:
            return item["weight"]
    return 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_core_status(config: dict, db: Database) -> dict:
    """Read-only status: holdings, capital, weights, next rebalance date."""
    portfolio = get_portfolio()
    core_positions = _get_core_positions(portfolio)

    total_capital = config.get("capital", 5000)
    core_fraction = config.get("capital_split", {}).get("core", 0.0)
    core_capital = total_capital * core_fraction

    invested = sum(p["market_value"] for p in core_positions)
    cash_remaining = max(core_capital - invested, 0.0)
    total_core_value = invested or 1.0  # avoid div-by-zero

    holdings = []
    for pos in core_positions:
        symbol = pos["symbol"]
        last_buy_ts = db.get_last_core_buy_date(symbol)
        days_since_buy = _days_since(last_buy_ts) if last_buy_ts else None

        target_weight = _get_symbol_target_weight(config, symbol)
        actual_weight = pos["market_value"] / total_core_value
        drift = round(actual_weight - target_weight, 4)

        holdings.append({
            "symbol": symbol,
            "sector": next(
                (item.get("sector") for item in _get_buy_list(config) if item["symbol"] == symbol),
                "unknown",
            ),
            "qty": pos.get("qty", 0),
            "cost_basis": pos.get("avg_entry_price", 0) * pos.get("qty", 0),
            "current_value": pos["market_value"],
            "unrealized_pnl": pos.get("unrealized_pl", 0.0),
            "weight_actual": round(actual_weight, 4),
            "weight_target": target_weight,
            "drift": drift,
            "last_buy_date": last_buy_ts[:10] if last_buy_ts else None,
            "days_since_buy": days_since_buy,
        })

    # Calculate next rebalance date from last rebalance log entry
    rebalance_logs = db.get_rebalance_log(limit=1)
    interval_days = config.get("core_holdings", {}).get("rebalance", {}).get("interval_days", 90)
    if rebalance_logs:
        last_rebalance = datetime.fromisoformat(rebalance_logs[0]["timestamp"])
    else:
        last_rebalance = datetime.now(timezone.utc) - timedelta(days=interval_days)

    next_rebalance = last_rebalance + timedelta(days=interval_days)
    days_until_rebalance = max((next_rebalance.date() - datetime.now(timezone.utc).date()).days, 0)

    return {
        "core_capital": core_capital,
        "invested": round(invested, 2),
        "cash_remaining": round(cash_remaining, 2),
        "holdings": holdings,
        "next_rebalance_date": next_rebalance.strftime("%Y-%m-%d"),
        "days_until_rebalance": days_until_rebalance,
    }


def run_core_cycle(config: dict, db: Database) -> dict:
    """Daily core holdings cycle: check entries for all buy_list stocks.

    Returns dict with keys: buys, skips, exits, rebalances.
    """
    core_cfg = config.get("core_holdings", {})
    if not core_cfg.get("enabled", False):
        return {"buys": [], "skips": [], "exits": [], "rebalances": []}

    entry_cfg = core_cfg.get("entry", {})
    sma_period = entry_cfg.get("sma_period", 50)
    dca_interval_days = entry_cfg.get("dca_interval_days", 7)

    total_capital = config.get("capital", 5000)
    core_fraction = config.get("capital_split", {}).get("core", 0.0)
    core_capital = total_capital * core_fraction
    max_per_buy_pct = entry_cfg.get("max_per_buy", 0.02)

    portfolio = get_portfolio()
    core_positions = _get_core_positions(portfolio)
    position_map = {p["symbol"]: p for p in core_positions}

    buy_list = _get_buy_list(config)
    rebalance_cfg = core_cfg.get("rebalance", {})
    drift_threshold = rebalance_cfg.get("drift_threshold", 0.05)

    buys = []
    skips = []

    total_core_value = sum(p["market_value"] for p in core_positions) or 1.0

    for item in buy_list:
        symbol = item["symbol"]
        target_weight = item["weight"]
        current_pos = position_map.get(symbol)

        # If held and at/above target weight (within drift), skip
        if current_pos:
            actual_weight = current_pos["market_value"] / total_core_value
            if actual_weight >= target_weight - drift_threshold:
                skips.append({"symbol": symbol, "reason": "at_target_weight"})
                continue

        # Check last buy date
        last_buy_ts = db.get_last_core_buy_date(symbol)
        days_since_last = _days_since(last_buy_ts) if last_buy_ts else 9999

        # Get price data
        bar = _get_price_and_sma(symbol, sma_period)
        price = bar["close"]
        sma = bar["sma50"]

        is_dip = price > 0 and sma > 0 and price < sma
        is_dca_due = days_since_last >= dca_interval_days

        if not is_dip and not is_dca_due:
            skips.append({
                "symbol": symbol,
                "reason": "no_entry_criteria",
                "price": price,
                "sma50": sma,
                "days_since_buy": days_since_last,
            })
            continue

        reason = "dip_entry" if is_dip else "dca_fallback"

        # Calculate position size
        current_value = current_pos["market_value"] if current_pos else 0.0
        target_value = target_weight * core_capital
        gap = target_value - current_value
        max_per_buy = max_per_buy_pct * core_capital
        buy_dollars = min(gap, max_per_buy)

        if price <= 0 or buy_dollars <= 0:
            skips.append({"symbol": symbol, "reason": "zero_price_or_size"})
            continue

        qty = round(buy_dollars / price, 6)

        order = execute_order(symbol=symbol, side="buy", qty=qty)
        if order["status"] in ("filled", "pending"):
            filled_price = order.get("filled_price") or price
            position_id = str(uuid.uuid4())
            db.insert_core_buy({
                "symbol": symbol,
                "qty": qty,
                "price": filled_price,
                "cost_basis": round(qty * filled_price, 2),
                "position_id": position_id,
                "order_id": order.get("order_id"),
            })
            db.insert_trade({
                "symbol": symbol,
                "side": "buy",
                "qty": qty,
                "price": filled_price,
                "order_id": order.get("order_id"),
                "trade_type": "core_holdings",
                "status": order["status"],
                "position_id": position_id,
            })
            db.insert_decision({
                "ticker": symbol,
                "action": "buy",
                "reasoning": f"Core holdings {reason}: price={price:.2f}, sma50={sma:.2f}, days_since_buy={days_since_last}",
                "signals_snapshot": json.dumps({
                    "strategy_id": "core_holdings",
                    "reason": reason,
                    "price": price,
                    "sma50": sma,
                    "days_since_buy": days_since_last,
                }),
                "position_id": position_id,
            })
            buys.append({
                "symbol": symbol,
                "qty": qty,
                "price": filled_price,
                "reason": reason,
                "position_id": position_id,
            })

    exits = check_core_exits(config, db)
    return {"buys": buys, "skips": skips, "exits": exits, "rebalances": []}


def check_core_exits(config: dict, db: Database) -> list[dict]:
    """Check for removal, sustained-sentiment, and overweight exits.

    Never exits on technical signals (RSI/MACD). Returns list of executed exits.
    """
    core_cfg = config.get("core_holdings", {})
    exit_cfg = core_cfg.get("exit", {})

    # sell_on_signals must be False — this is a hard constraint
    if exit_cfg.get("sell_on_signals", False):
        raise ValueError("core_holdings.exit.sell_on_signals must be false — core holdings never sell on technical signals")

    sell_on_removal = exit_cfg.get("sell_on_removal", True)
    sentiment_threshold = exit_cfg.get("sentiment_exit_threshold", -0.3)
    sentiment_days = exit_cfg.get("sentiment_exit_days", 5)
    max_position_pct = exit_cfg.get("max_position_pct", 0.20)

    portfolio = get_portfolio()
    core_positions = _get_core_positions(portfolio)
    buy_list_symbols = {item["symbol"] for item in _get_buy_list(config)}

    total_core_value = sum(p["market_value"] for p in core_positions) or 1.0

    exits = []

    for pos in core_positions:
        symbol = pos["symbol"]
        exit_reason = None

        # 1. Removal exit
        if sell_on_removal and symbol not in buy_list_symbols:
            exit_reason = "removal"

        # 2. Sustained negative sentiment exit
        if exit_reason is None:
            signals = db.get_signals(symbol, limit=sentiment_days)
            if len(signals) >= sentiment_days:
                recent = signals[:sentiment_days]
                all_negative = all(
                    (s.get("sentiment_score") or 0) < sentiment_threshold
                    for s in recent
                )
                if all_negative:
                    exit_reason = "sentiment"

        # 3. Overweight trim — handled inside rebalance_core, not here
        # (here we only do full-position exits, not partial trims)

        if exit_reason is None:
            continue

        # Execute sell
        qty = pos.get("qty", 0)
        order = execute_order(symbol=symbol, side="sell", qty=qty)
        if order["status"] in ("filled", "pending"):
            filled_price = order.get("filled_price") or 0.0
            position_id = str(uuid.uuid4())
            db.insert_trade({
                "symbol": symbol,
                "side": "sell",
                "qty": qty,
                "price": filled_price,
                "order_id": order.get("order_id"),
                "trade_type": "core_holdings",
                "status": order["status"],
                "position_id": position_id,
            })
            db.insert_decision({
                "ticker": symbol,
                "action": "sell",
                "reasoning": f"Core holdings exit — reason: {exit_reason}",
                "signals_snapshot": json.dumps({
                    "strategy_id": "core_holdings",
                    "exit_reason": exit_reason,
                }),
                "position_id": position_id,
            })
            exits.append({
                "symbol": symbol,
                "qty": qty,
                "price": filled_price,
                "reason": exit_reason,
            })

    return exits


def rebalance_core(config: dict, db: Database) -> list[dict]:
    """Quarterly rebalance: sell overweight, buy underweight positions.

    Returns list of rebalance trades executed.
    """
    core_cfg = config.get("core_holdings", {})
    rebalance_cfg = core_cfg.get("rebalance", {})
    drift_threshold = rebalance_cfg.get("drift_threshold", 0.05)

    total_capital = config.get("capital", 5000)
    core_fraction = config.get("capital_split", {}).get("core", 0.0)
    core_capital = total_capital * core_fraction

    portfolio = get_portfolio()
    core_positions = _get_core_positions(portfolio)
    position_map = {p["symbol"]: p for p in core_positions}

    total_core_value = sum(p["market_value"] for p in core_positions)
    if total_core_value == 0:
        return []

    buy_list = _get_buy_list(config)
    rebalances = []

    for item in buy_list:
        symbol = item["symbol"]
        target_weight = item["weight"]
        pos = position_map.get(symbol)

        current_value = pos["market_value"] if pos else 0.0
        current_weight = current_value / total_core_value

        drift = current_weight - target_weight
        if abs(drift) <= drift_threshold:
            continue

        bar = _get_price_and_sma(symbol)
        price = bar["close"]
        if price <= 0:
            continue

        target_value = target_weight * core_capital

        if drift > 0:
            # Overweight — sell
            sell_value = current_value - target_value
            qty = round(sell_value / price, 6)
            action = "sell"
            reason = "overweight"
        else:
            # Underweight — buy
            buy_value = target_value - current_value
            qty = round(buy_value / price, 6)
            action = "buy"
            reason = "underweight"

        if qty <= 0:
            continue

        order = execute_order(symbol=symbol, side=action, qty=qty)
        if order["status"] in ("filled", "pending"):
            filled_price = order.get("filled_price") or price
            new_weight = target_weight  # approximation post-rebalance

            db.insert_rebalance_log({
                "symbol": symbol,
                "action": action,
                "qty": qty,
                "price": filled_price,
                "reason": reason,
                "old_weight": round(current_weight, 4),
                "new_weight": round(new_weight, 4),
            })
            db.insert_trade({
                "symbol": symbol,
                "side": action,
                "qty": qty,
                "price": filled_price,
                "order_id": order.get("order_id"),
                "trade_type": "core_holdings",
                "status": order["status"],
                "position_id": None,
            })
            rebalances.append({
                "symbol": symbol,
                "action": action,
                "qty": qty,
                "price": filled_price,
                "reason": reason,
                "old_weight": round(current_weight, 4),
                "new_weight": round(new_weight, 4),
            })

    return rebalances
```

- [ ] **Step 4: Run core engine tests**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest tests/test_core_engine.py -v
```
Expected: All tests pass.

- [ ] **Step 5: Run full test suite**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest --tb=short -q
```
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/claude_invest/modules/core_engine.py tests/test_core_engine.py
git commit -m "feat: add core_engine module with run_core_cycle, check_core_exits, rebalance_core, get_core_status"
```

---

## Task 6: CLI Commands

**Files:**
- Modify: `src/claude_invest/main.py`
- Create: `tests/test_core_cli.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_core_cli.py`:

```python
import json
import sys
import pytest
from unittest.mock import patch, MagicMock
from io import StringIO


def _run_main(args: list[str]) -> dict:
    """Helper: run main() with given args and capture JSON output."""
    with patch("sys.argv", ["claude-invest"] + args):
        captured = StringIO()
        with patch("sys.stdout", captured):
            try:
                from claude_invest.main import main
                main()
            except SystemExit:
                pass
        output = captured.getvalue().strip()
        if not output:
            return {}
        return json.loads(output)


def test_core_status_command_exists():
    """core-status command returns expected keys."""
    mock_status = {
        "core_capital": 2500.0,
        "invested": 0.0,
        "cash_remaining": 2500.0,
        "holdings": [],
        "next_rebalance_date": "2026-07-22",
        "days_until_rebalance": 89,
    }
    with patch("claude_invest.main.cmd_core_status") as mock_cmd:
        mock_cmd.return_value = None
        with patch("sys.argv", ["claude-invest", "core-status"]):
            from claude_invest import main as main_module
            # Verify the function is importable and dispatched
            assert hasattr(main_module, "cmd_core_status")


def test_core_buy_command_exists():
    from claude_invest import main as main_module
    assert hasattr(main_module, "cmd_core_buy")


def test_core_add_command_exists():
    from claude_invest import main as main_module
    assert hasattr(main_module, "cmd_core_add")


def test_core_remove_command_exists():
    from claude_invest import main as main_module
    assert hasattr(main_module, "cmd_core_remove")


def test_core_rebalance_command_exists():
    from claude_invest import main as main_module
    assert hasattr(main_module, "cmd_core_rebalance")


def test_core_cycle_command_exists():
    from claude_invest import main as main_module
    assert hasattr(main_module, "cmd_core_cycle")


def test_cmd_core_status_outputs_json():
    mock_status = {
        "core_capital": 2500.0,
        "invested": 500.0,
        "cash_remaining": 2000.0,
        "holdings": [],
        "next_rebalance_date": "2026-07-22",
        "days_until_rebalance": 89,
    }
    with patch("claude_invest.main.load_config", return_value={"capital": 5000, "capital_split": {"trading": 0.5, "core": 0.5}, "core_holdings": {"buy_list": [], "entry": {}, "exit": {}, "rebalance": {}}}), \
         patch("claude_invest.main.Database") as mock_db_cls, \
         patch("claude_invest.main.get_core_status", return_value=mock_status):
        mock_db_cls.return_value.__enter__ = MagicMock()
        mock_db_cls.return_value.initialize = MagicMock()
        mock_db_cls.return_value.close = MagicMock()
        captured = StringIO()
        with patch("sys.stdout", captured):
            from claude_invest.main import cmd_core_status
            cmd_core_status()
        output = json.loads(captured.getvalue())
        assert output["core_capital"] == 2500.0


def test_cmd_core_add_updates_yaml(tmp_path):
    """core-add writes new entry to buy_list in settings.yaml."""
    import yaml
    from claude_invest.main import cmd_core_add

    config = {
        "capital": 5000,
        "capital_split": {"trading": 0.5, "core": 0.5},
        "core_holdings": {
            "enabled": True,
            "buy_list": [
                {"symbol": "NVDA", "sector": "tech", "weight": 0.50},
                {"symbol": "MSFT", "sector": "tech", "weight": 0.50},
            ],
            "entry": {}, "exit": {}, "rebalance": {},
        },
    }
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(yaml.dump(config))

    with patch("claude_invest.main.DEFAULT_CONFIG_PATH", config_path), \
         patch("claude_invest.main.load_config", return_value=config):
        captured = StringIO()
        with patch("sys.stdout", captured):
            cmd_core_add("TSLA", "ev", 0.10)
        result = json.loads(captured.getvalue())
        assert result["status"] == "added"
        assert result["symbol"] == "TSLA"

    # Verify YAML was updated
    updated = yaml.safe_load(config_path.read_text())
    symbols = [x["symbol"] for x in updated["core_holdings"]["buy_list"]]
    assert "TSLA" in symbols


def test_cmd_core_remove_updates_yaml(tmp_path):
    """core-remove removes entry from buy_list in settings.yaml."""
    import yaml
    from claude_invest.main import cmd_core_remove

    config = {
        "capital": 5000,
        "capital_split": {"trading": 0.5, "core": 0.5},
        "core_holdings": {
            "enabled": True,
            "buy_list": [
                {"symbol": "NVDA", "sector": "tech", "weight": 0.50},
                {"symbol": "MSFT", "sector": "tech", "weight": 0.50},
            ],
            "entry": {}, "exit": {}, "rebalance": {},
        },
    }
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(yaml.dump(config))

    with patch("claude_invest.main.DEFAULT_CONFIG_PATH", config_path), \
         patch("claude_invest.main.load_config", return_value=config):
        captured = StringIO()
        with patch("sys.stdout", captured):
            cmd_core_remove("NVDA")
        result = json.loads(captured.getvalue())
        assert result["status"] == "removed"
        assert result["symbol"] == "NVDA"

    updated = yaml.safe_load(config_path.read_text())
    symbols = [x["symbol"] for x in updated["core_holdings"]["buy_list"]]
    assert "NVDA" not in symbols


def test_cmd_core_remove_not_found():
    """core-remove of non-existent symbol returns error."""
    from claude_invest.main import cmd_core_remove
    config = {
        "core_holdings": {
            "buy_list": [{"symbol": "NVDA", "sector": "tech", "weight": 1.0}],
        }
    }
    with patch("claude_invest.main.load_config", return_value=config), \
         patch("claude_invest.main.DEFAULT_CONFIG_PATH", "/tmp/fake.yaml"):
        captured = StringIO()
        with patch("sys.stdout", captured):
            cmd_core_remove("TSLA")
        result = json.loads(captured.getvalue())
        assert "error" in result
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest tests/test_core_cli.py -v 2>&1 | head -40
```
Expected: `AttributeError` — `cmd_core_status`, `cmd_core_buy` etc. don't exist in main.py yet.

- [ ] **Step 3: Add imports and helper to main.py**

At the top of `src/claude_invest/main.py`, add to the existing imports block:

```python
from claude_invest.modules.core_engine import (
    run_core_cycle, check_core_exits, rebalance_core, get_core_status
)
from claude_invest.config.loader import DEFAULT_CONFIG_PATH
```

Note: `DEFAULT_CONFIG_PATH` is already imported inline in some functions — consolidate it to the top-level import.

- [ ] **Step 4: Add 6 new command functions to main.py**

Add these functions after `cmd_strategies()`, before `main()`:

```python
def cmd_core_status():
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    status = get_core_status(config, db)
    db.close()
    _output(status)


def cmd_core_buy(symbol: str):
    """Manual core buy for a single symbol outside the daily schedule."""
    import uuid as _uuid
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()

    core_cfg = config.get("core_holdings", {})
    entry_cfg = core_cfg.get("entry", {})
    sma_period = entry_cfg.get("sma_period", 50)

    total_capital = config.get("capital", 5000)
    core_fraction = config.get("capital_split", {}).get("core", 0.0)
    core_capital = total_capital * core_fraction
    max_per_buy_pct = entry_cfg.get("max_per_buy", 0.02)
    buy_dollars = core_capital * max_per_buy_pct

    from claude_invest.modules.core_engine import _get_price_and_sma
    bar = _get_price_and_sma(symbol, sma_period)
    price = bar["close"]

    if price <= 0:
        db.close()
        _output({"error": f"Could not get price for {symbol}"})
        return

    qty = round(buy_dollars / price, 6)
    from claude_invest.modules.executor import execute_order as _execute_order
    order = _execute_order(symbol=symbol, side="buy", qty=qty)

    if order["status"] in ("filled", "pending"):
        filled_price = order.get("filled_price") or price
        position_id = str(_uuid.uuid4())
        db.insert_core_buy({
            "symbol": symbol,
            "qty": qty,
            "price": filled_price,
            "cost_basis": round(qty * filled_price, 2),
            "position_id": position_id,
            "order_id": order.get("order_id"),
        })
        db.insert_trade({
            "symbol": symbol, "side": "buy", "qty": qty,
            "price": filled_price, "order_id": order.get("order_id"),
            "trade_type": "core_holdings", "status": order["status"],
            "position_id": position_id,
        })
    db.close()
    _output({"status": order["status"], "symbol": symbol, "qty": qty, "order": order})


def cmd_core_add(symbol: str, sector: str, weight: float):
    """Add a symbol to core_holdings.buy_list in settings.yaml."""
    import yaml as _yaml
    config = load_config()
    buy_list = config.get("core_holdings", {}).get("buy_list", [])

    if any(item["symbol"] == symbol for item in buy_list):
        _output({"error": f"{symbol} already in buy_list"})
        return

    buy_list.append({"symbol": symbol, "sector": sector, "weight": weight})

    with open(str(DEFAULT_CONFIG_PATH), "r") as f:
        raw = _yaml.safe_load(f)
    raw.setdefault("core_holdings", {})["buy_list"] = buy_list
    with open(str(DEFAULT_CONFIG_PATH), "w") as f:
        _yaml.dump(raw, f, default_flow_style=False, sort_keys=False)

    _output({"status": "added", "symbol": symbol, "sector": sector, "weight": weight})


def cmd_core_remove(symbol: str):
    """Remove a symbol from core_holdings.buy_list in settings.yaml.

    The next core cycle will sell the position (if sell_on_removal: true).
    """
    import yaml as _yaml
    config = load_config()
    buy_list = config.get("core_holdings", {}).get("buy_list", [])

    original_len = len(buy_list)
    new_list = [item for item in buy_list if item["symbol"] != symbol]

    if len(new_list) == original_len:
        _output({"error": f"{symbol} not found in buy_list"})
        return

    with open(str(DEFAULT_CONFIG_PATH), "r") as f:
        raw = _yaml.safe_load(f)
    raw.setdefault("core_holdings", {})["buy_list"] = new_list
    with open(str(DEFAULT_CONFIG_PATH), "w") as f:
        _yaml.dump(raw, f, default_flow_style=False, sort_keys=False)

    _output({"status": "removed", "symbol": symbol,
             "note": "Position will be sold on next core cycle if sell_on_removal is true"})


def cmd_core_rebalance():
    """Force a quarterly rebalance immediately."""
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    rebalances = rebalance_core(config, db)
    db.close()
    _output({"rebalances": rebalances, "count": len(rebalances)})


def cmd_core_cycle():
    """Run a full core holdings cycle manually (entries + exits)."""
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    result = run_core_cycle(config, db)
    db.close()
    _output(result)
```

- [ ] **Step 5: Add core commands to main() dispatch and help text**

In the `main()` function, update the `_output({"error": "Usage: ...", "commands": [...]})` help list to include:

```python
"core-status", "core-buy <symbol>", "core-add <symbol> <sector> <weight>",
"core-remove <symbol>", "core-rebalance", "core-cycle",
```

Then add dispatch cases before the final `else` block:

```python
    elif command == "core-status":
        cmd_core_status()
    elif command == "core-buy" and len(sys.argv) >= 3:
        cmd_core_buy(sys.argv[2])
    elif command == "core-add" and len(sys.argv) >= 5:
        cmd_core_add(sys.argv[2], sys.argv[3], float(sys.argv[4]))
    elif command == "core-remove" and len(sys.argv) >= 3:
        cmd_core_remove(sys.argv[2])
    elif command == "core-rebalance":
        cmd_core_rebalance()
    elif command == "core-cycle":
        cmd_core_cycle()
```

- [ ] **Step 6: Verify DEFAULT_CONFIG_PATH import is at top level**

In `src/claude_invest/main.py`, confirm that `from claude_invest.config.loader import DEFAULT_CONFIG_PATH` is at the top of the file alongside the other imports. Remove any inline imports of it inside individual functions (`cmd_review_day`, `cmd_revert_change`) and replace them with the top-level import.

- [ ] **Step 7: Run CLI tests**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest tests/test_core_cli.py -v
```
Expected: All tests pass.

- [ ] **Step 8: Smoke-test CLI dispatch**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/claude-invest core-status 2>&1 | python3 -c "import sys, json; d = json.load(sys.stdin); print('core_capital:', d['core_capital'])"
```
Expected: `core_capital: 2500.0`

- [ ] **Step 9: Run full test suite**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest --tb=short -q
```
Expected: All tests pass.

- [ ] **Step 10: Commit**

```bash
git add src/claude_invest/main.py tests/test_core_cli.py
git commit -m "feat: add core-status, core-buy, core-add, core-remove, core-rebalance, core-cycle CLI commands"
```

---

## Task 7: API Endpoints

**Files:**
- Modify: `src/claude_invest/api_server.py`
- Create: `tests/test_core_api.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_core_api.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from claude_invest.api_server import app
    return TestClient(app)


@pytest.fixture
def mock_core_status():
    return {
        "core_capital": 2500.0,
        "invested": 850.0,
        "cash_remaining": 1650.0,
        "holdings": [
            {
                "symbol": "NVDA",
                "sector": "tech",
                "qty": 0.5,
                "cost_basis": 250.0,
                "current_value": 275.0,
                "unrealized_pnl": 25.0,
                "weight_actual": 0.11,
                "weight_target": 0.10,
                "drift": 0.01,
                "last_buy_date": "2026-04-20",
                "days_since_buy": 4,
            }
        ],
        "next_rebalance_date": "2026-07-20",
        "days_until_rebalance": 84,
    }


# --- GET /api/core/status ---

def test_core_status_endpoint_exists(client, mock_core_status):
    with patch("claude_invest.api_server.get_core_status", return_value=mock_core_status), \
         patch("claude_invest.api_server.load_config", return_value={}), \
         patch("claude_invest.api_server.Database") as mock_db_cls:
        mock_db_cls.return_value.initialize = MagicMock()
        mock_db_cls.return_value.close = MagicMock()
        resp = client.get("/api/core/status")
    assert resp.status_code == 200


def test_core_status_returns_correct_shape(client, mock_core_status):
    with patch("claude_invest.api_server.get_core_status", return_value=mock_core_status), \
         patch("claude_invest.api_server.load_config", return_value={}), \
         patch("claude_invest.api_server.Database") as mock_db_cls:
        mock_db_cls.return_value.initialize = MagicMock()
        mock_db_cls.return_value.close = MagicMock()
        resp = client.get("/api/core/status")
    data = resp.json()
    assert "core_capital" in data
    assert "invested" in data
    assert "cash_remaining" in data
    assert "holdings" in data
    assert "next_rebalance_date" in data
    assert "days_until_rebalance" in data
    assert data["core_capital"] == 2500.0
    assert len(data["holdings"]) == 1
    assert data["holdings"][0]["symbol"] == "NVDA"


# --- GET /api/core/schedule ---

def test_core_schedule_endpoint_exists(client):
    with patch("claude_invest.api_server.load_config", return_value={
        "core_holdings": {
            "buy_list": [
                {"symbol": "NVDA", "sector": "tech", "weight": 0.10},
                {"symbol": "MSFT", "sector": "tech", "weight": 0.10},
            ],
            "entry": {"sma_period": 50, "dca_interval_days": 7},
        }
    }), \
         patch("claude_invest.api_server.Database") as mock_db_cls, \
         patch("claude_invest.api_server._get_schedule_entries") as mock_sched:
        mock_db_cls.return_value.initialize = MagicMock()
        mock_db_cls.return_value.close = MagicMock()
        mock_sched.return_value = [
            {
                "symbol": "NVDA",
                "days_since_buy": 8,
                "current_price": 490.0,
                "sma50": 510.0,
                "is_dip": True,
                "dca_due": True,
                "next_buy_date": "2026-04-24",
            }
        ]
        resp = client.get("/api/core/schedule")
    assert resp.status_code == 200
    data = resp.json()
    assert "schedule" in data
    assert isinstance(data["schedule"], list)


def test_core_schedule_entry_shape(client):
    schedule_entry = {
        "symbol": "NVDA",
        "days_since_buy": 8,
        "current_price": 490.0,
        "sma50": 510.0,
        "is_dip": True,
        "dca_due": True,
        "next_buy_date": "2026-04-24",
    }
    with patch("claude_invest.api_server.load_config", return_value={
        "core_holdings": {
            "buy_list": [{"symbol": "NVDA", "sector": "tech", "weight": 0.10}],
            "entry": {"sma_period": 50, "dca_interval_days": 7},
        }
    }), \
         patch("claude_invest.api_server.Database") as mock_db_cls, \
         patch("claude_invest.api_server._get_schedule_entries", return_value=[schedule_entry]):
        mock_db_cls.return_value.initialize = MagicMock()
        mock_db_cls.return_value.close = MagicMock()
        resp = client.get("/api/core/schedule")
    data = resp.json()
    entry = data["schedule"][0]
    assert entry["symbol"] == "NVDA"
    assert "days_since_buy" in entry
    assert "current_price" in entry
    assert "sma50" in entry
    assert "is_dip" in entry
    assert "dca_due" in entry
    assert "next_buy_date" in entry


# --- GET /api/core/rebalance-preview ---

def test_core_rebalance_preview_exists(client):
    mock_preview = [
        {
            "symbol": "NVDA",
            "action": "sell",
            "qty": 0.2,
            "price": 520.0,
            "reason": "overweight",
            "old_weight": 0.15,
            "new_weight": 0.10,
        }
    ]
    with patch("claude_invest.api_server.load_config", return_value={}), \
         patch("claude_invest.api_server.Database") as mock_db_cls, \
         patch("claude_invest.api_server.rebalance_core", return_value=mock_preview):
        mock_db_cls.return_value.initialize = MagicMock()
        mock_db_cls.return_value.close = MagicMock()
        resp = client.get("/api/core/rebalance-preview")
    assert resp.status_code == 200


def test_core_rebalance_preview_is_dry_run(client):
    """Rebalance-preview must NOT execute any orders — dry_run=True."""
    mock_preview = [
        {"symbol": "MSFT", "action": "buy", "qty": 0.5, "price": 400.0,
         "reason": "underweight", "old_weight": 0.05, "new_weight": 0.10}
    ]
    with patch("claude_invest.api_server.load_config", return_value={}), \
         patch("claude_invest.api_server.Database") as mock_db_cls, \
         patch("claude_invest.api_server.rebalance_core", return_value=mock_preview) as mock_rebal:
        mock_db_cls.return_value.initialize = MagicMock()
        mock_db_cls.return_value.close = MagicMock()
        resp = client.get("/api/core/rebalance-preview")
    data = resp.json()
    assert "preview" in data
    assert data["dry_run"] is True
    assert isinstance(data["preview"], list)
    # Verify rebalance_core was called with dry_run=True
    mock_rebal.assert_called_once()
    call_kwargs = mock_rebal.call_args
    assert call_kwargs.kwargs.get("dry_run") is True or (
        len(call_kwargs.args) >= 3 and call_kwargs.args[2] is True
    )


def test_core_rebalance_preview_shape(client):
    mock_preview = [
        {"symbol": "NVDA", "action": "sell", "qty": 0.2, "price": 520.0,
         "reason": "overweight", "old_weight": 0.15, "new_weight": 0.10}
    ]
    with patch("claude_invest.api_server.load_config", return_value={}), \
         patch("claude_invest.api_server.Database") as mock_db_cls, \
         patch("claude_invest.api_server.rebalance_core", return_value=mock_preview):
        mock_db_cls.return_value.initialize = MagicMock()
        mock_db_cls.return_value.close = MagicMock()
        resp = client.get("/api/core/rebalance-preview")
    data = resp.json()
    item = data["preview"][0]
    assert item["symbol"] == "NVDA"
    assert item["action"] == "sell"
    assert "old_weight" in item
    assert "new_weight" in item
    assert "reason" in item
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest tests/test_core_api.py -v 2>&1 | head -40
```
Expected: Failures — `/api/core/status`, `/api/core/schedule`, `/api/core/rebalance-preview` routes don't exist yet; `_get_schedule_entries` and `rebalance_core` not imported in api_server.

- [ ] **Step 3: Add imports to api_server.py**

At the top of `src/claude_invest/api_server.py`, add to the existing imports:

```python
from claude_invest.modules.core_engine import (
    get_core_status,
    rebalance_core,
    _get_price_and_sma,
    _days_since,
    _get_buy_list,
)
```

- [ ] **Step 4: Add `_get_schedule_entries` helper to api_server.py**

Add this helper function before the new route handlers (after existing helpers):

```python
def _get_schedule_entries(config: dict, db) -> list[dict]:
    """Build per-symbol schedule info for /api/core/schedule."""
    from datetime import datetime, timedelta, timezone
    core_cfg = config.get("core_holdings", {})
    entry_cfg = core_cfg.get("entry", {})
    sma_period = entry_cfg.get("sma_period", 50)
    dca_interval_days = entry_cfg.get("dca_interval_days", 7)

    buy_list = _get_buy_list(config)
    entries = []

    for item in buy_list:
        symbol = item["symbol"]
        last_buy_ts = db.get_last_core_buy_date(symbol)
        days_since_buy = _days_since(last_buy_ts) if last_buy_ts else None

        try:
            bar = _get_price_and_sma(symbol, sma_period)
            current_price = bar["close"]
            sma50 = bar["sma50"]
            is_dip = current_price > 0 and sma50 > 0 and current_price < sma50
        except Exception:
            current_price = None
            sma50 = None
            is_dip = False

        dca_due = days_since_buy is None or days_since_buy >= dca_interval_days

        # Next buy date: if dca_due now, today; else last_buy + interval
        if dca_due:
            next_buy_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        elif last_buy_ts:
            try:
                last_dt = datetime.fromisoformat(last_buy_ts.replace("Z", "+00:00"))
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                next_buy_date = (last_dt + timedelta(days=dca_interval_days)).strftime("%Y-%m-%d")
            except ValueError:
                next_buy_date = None
        else:
            next_buy_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        entries.append({
            "symbol": symbol,
            "sector": item.get("sector", "unknown"),
            "weight_target": item["weight"],
            "days_since_buy": days_since_buy,
            "current_price": current_price,
            "sma50": sma50,
            "is_dip": is_dip,
            "dca_due": dca_due,
            "next_buy_date": next_buy_date,
        })

    return entries
```

- [ ] **Step 5: Add 3 new route handlers to api_server.py**

Add after the existing `/api/strategies` route:

```python
@app.get("/api/core/status")
def api_core_status():
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    try:
        status = get_core_status(config, db)
    finally:
        db.close()
    return status


@app.get("/api/core/schedule")
def api_core_schedule():
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    try:
        schedule = _get_schedule_entries(config, db)
    finally:
        db.close()
    return {"schedule": schedule}


@app.get("/api/core/rebalance-preview")
def api_core_rebalance_preview():
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    try:
        preview = rebalance_core(config, db, dry_run=True)
    finally:
        db.close()
    return {"preview": preview, "dry_run": True}
```

- [ ] **Step 6: Add `dry_run` parameter to `rebalance_core` in core_engine.py**

Update the `rebalance_core` function signature and body to support dry-run mode. In `src/claude_invest/modules/core_engine.py`, update the function signature:

```python
def rebalance_core(config: dict, db: Database, dry_run: bool = False) -> list[dict]:
    """Quarterly rebalance: sell overweight, buy underweight positions.

    When dry_run=True, calculates what would be done but executes no orders
    and writes nothing to the database. Returns the same list shape either way.
    """
```

Inside the function, wrap all `execute_order`, `db.insert_rebalance_log`, and `db.insert_trade` calls in `if not dry_run:` guards:

```python
        if qty <= 0:
            continue

        bar = _get_price_and_sma(symbol)
        price = bar["close"]
        if price <= 0:
            continue

        target_value = target_weight * core_capital
        if drift > 0:
            sell_value = current_value - target_value
            qty = round(sell_value / price, 6)
            action = "sell"
            reason = "overweight"
        else:
            buy_value = target_value - current_value
            qty = round(buy_value / price, 6)
            action = "buy"
            reason = "underweight"

        if qty <= 0:
            continue

        filled_price = price  # default for dry run
        order_id = None

        if not dry_run:
            order = execute_order(symbol=symbol, side=action, qty=qty)
            if order["status"] not in ("filled", "pending"):
                continue
            filled_price = order.get("filled_price") or price
            order_id = order.get("order_id")

            db.insert_rebalance_log({
                "symbol": symbol,
                "action": action,
                "qty": qty,
                "price": filled_price,
                "reason": reason,
                "old_weight": round(current_weight, 4),
                "new_weight": round(target_weight, 4),
            })
            db.insert_trade({
                "symbol": symbol,
                "side": action,
                "qty": qty,
                "price": filled_price,
                "order_id": order_id,
                "trade_type": "core_holdings",
                "status": order["status"],
                "position_id": None,
            })

        rebalances.append({
            "symbol": symbol,
            "action": action,
            "qty": qty,
            "price": filled_price,
            "reason": reason,
            "old_weight": round(current_weight, 4),
            "new_weight": round(target_weight, 4),
        })
```

- [ ] **Step 7: Run API tests — all should pass**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest tests/test_core_api.py -v
```
Expected: All tests pass.

- [ ] **Step 8: Run full test suite**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest --tb=short -q
```
Expected: All tests pass.

- [ ] **Step 9: Smoke-test with running server**

```bash
# In one terminal:
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/uvicorn claude_invest.api_server:app --port 8000 &
sleep 2
curl -s http://localhost:8000/api/core/status | python3 -c "import sys, json; d=json.load(sys.stdin); print('core_capital:', d['core_capital'])"
curl -s http://localhost:8000/api/core/schedule | python3 -c "import sys, json; d=json.load(sys.stdin); print('schedule entries:', len(d['schedule']))"
curl -s http://localhost:8000/api/core/rebalance-preview | python3 -c "import sys, json; d=json.load(sys.stdin); print('dry_run:', d['dry_run'], '| preview items:', len(d['preview']))"
```
Expected: `core_capital: 2500.0`, schedule entries count, `dry_run: True`.

- [ ] **Step 10: Commit**

```bash
git add src/claude_invest/api_server.py src/claude_invest/modules/core_engine.py tests/test_core_api.py
git commit -m "feat: add /api/core/status, /api/core/schedule, /api/core/rebalance-preview endpoints"
```

---

## Task 8: Dashboard Types, Hooks, and Page

**Files:**
- Modify: `dashboard/src/lib/types.ts`
- Modify: `dashboard/src/lib/api.ts`
- Create: `dashboard/src/app/core/page.tsx`
- Modify: `dashboard/src/components/nav.tsx`

- [ ] **Step 1: Add TypeScript interfaces to types.ts**

In `dashboard/src/lib/types.ts`, append after the last interface (`PerformanceSeries`):

```typescript
// --- Core Holdings ---

export interface CoreHolding {
  symbol: string;
  sector: string;
  qty: number;
  cost_basis: number;
  current_value: number;
  unrealized_pnl: number;
  weight_actual: number;
  weight_target: number;
  drift: number;
  last_buy_date: string | null;
  days_since_buy: number | null;
}

export interface CoreStatus {
  core_capital: number;
  invested: number;
  cash_remaining: number;
  holdings: CoreHolding[];
  next_rebalance_date: string;
  days_until_rebalance: number;
}

export interface CoreScheduleEntry {
  symbol: string;
  sector: string;
  weight_target: number;
  days_since_buy: number | null;
  current_price: number | null;
  sma50: number | null;
  is_dip: boolean;
  dca_due: boolean;
  next_buy_date: string | null;
}

export interface RebalancePreviewItem {
  symbol: string;
  action: "buy" | "sell";
  qty: number;
  price: number;
  reason: string;
  old_weight: number;
  new_weight: number;
}

export interface RebalancePreview {
  preview: RebalancePreviewItem[];
  dry_run: boolean;
}
```

- [ ] **Step 2: Add SWR hooks to api.ts**

In `dashboard/src/lib/api.ts`, append after the last `export function` (`revertChange`):

```typescript
export function useCoreStatus() {
  return useSWR<CoreStatus>("/api/core/status", fetcher, {
    refreshInterval: 30000,
  });
}

export function useCoreSchedule() {
  return useSWR<{ schedule: CoreScheduleEntry[] }>("/api/core/schedule", fetcher, {
    refreshInterval: 60000,
  });
}

export function useRebalancePreview() {
  return useSWR<RebalancePreview>("/api/core/rebalance-preview", fetcher, {
    refreshInterval: 300000, // 5 min — expensive call
  });
}
```

Also update the import at the top of `api.ts` to include the new types:

```typescript
import type {
  Trade,
  Decision,
  Signal,
  DiscoveryEntry,
  PortfolioSnapshot,
  Portfolio,
  Stats,
  Config,
  LearningReport,
  ChangeLogEntry,
  PerformanceSeries,
  CoreStatus,
  CoreScheduleEntry,
  RebalancePreview,
} from "./types";
```

- [ ] **Step 3: Create the /core page**

Create `dashboard/src/app/core/page.tsx`:

```tsx
"use client";

import { useCoreStatus, useCoreSchedule, useRebalancePreview } from "@/lib/api";
import type { CoreHolding, CoreScheduleEntry, RebalancePreviewItem } from "@/lib/types";

// --- Section 1: Portfolio Split ---

function PortfolioSplitCards({
  coreCapital,
  invested,
  cashRemaining,
  holdingsCount,
}: {
  coreCapital: number;
  invested: number;
  cashRemaining: number;
  holdingsCount: number;
}) {
  const pct = coreCapital > 0 ? Math.round((invested / coreCapital) * 100) : 0;
  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="bg-zinc-800 rounded-lg p-4">
        <div className="text-xs text-zinc-400 uppercase tracking-wide mb-1">Core Pool</div>
        <div className="text-2xl font-bold text-white">${coreCapital.toLocaleString()}</div>
        <div className="text-sm text-zinc-400 mt-1">
          ${invested.toLocaleString()} invested ({pct}%)
        </div>
        <div className="text-sm text-zinc-500">${cashRemaining.toLocaleString()} remaining</div>
      </div>
      <div className="bg-zinc-800 rounded-lg p-4">
        <div className="text-xs text-zinc-400 uppercase tracking-wide mb-1">Holdings</div>
        <div className="text-2xl font-bold text-white">{holdingsCount}</div>
        <div className="text-sm text-zinc-400 mt-1">active positions</div>
      </div>
    </div>
  );
}

// --- Section 2: Holdings Table ---

function driftColor(drift: number): string {
  const abs = Math.abs(drift);
  if (abs > 0.10) return "text-red-400";
  if (abs > 0.05) return "text-yellow-400";
  return "text-green-400";
}

function HoldingsTable({ holdings }: { holdings: CoreHolding[] }) {
  if (holdings.length === 0) {
    return <p className="text-zinc-500 text-sm">No core positions yet.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-zinc-400 border-b border-zinc-700">
            <th className="pb-2 pr-4">Symbol</th>
            <th className="pb-2 pr-4">Sector</th>
            <th className="pb-2 pr-4 text-right">Cost Basis</th>
            <th className="pb-2 pr-4 text-right">Current</th>
            <th className="pb-2 pr-4 text-right">P&amp;L</th>
            <th className="pb-2 pr-4 text-right">Weight</th>
            <th className="pb-2 pr-4 text-right">Target</th>
            <th className="pb-2 pr-4 text-right">Drift</th>
            <th className="pb-2">Last Buy</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => {
            const pnlColor = h.unrealized_pnl >= 0 ? "text-green-400" : "text-red-400";
            return (
              <tr key={h.symbol} className="border-b border-zinc-800 hover:bg-zinc-800/40">
                <td className="py-2 pr-4 font-medium text-white">{h.symbol}</td>
                <td className="py-2 pr-4 text-zinc-400 capitalize">{h.sector}</td>
                <td className="py-2 pr-4 text-right text-zinc-300">${h.cost_basis.toFixed(2)}</td>
                <td className="py-2 pr-4 text-right text-zinc-300">${h.current_value.toFixed(2)}</td>
                <td className={`py-2 pr-4 text-right ${pnlColor}`}>
                  {h.unrealized_pnl >= 0 ? "+" : ""}${h.unrealized_pnl.toFixed(2)}
                </td>
                <td className="py-2 pr-4 text-right text-zinc-300">
                  {(h.weight_actual * 100).toFixed(1)}%
                </td>
                <td className="py-2 pr-4 text-right text-zinc-400">
                  {(h.weight_target * 100).toFixed(1)}%
                </td>
                <td className={`py-2 pr-4 text-right ${driftColor(h.drift)}`}>
                  {h.drift >= 0 ? "+" : ""}{(h.drift * 100).toFixed(1)}%
                </td>
                <td className="py-2 text-zinc-400 text-xs">
                  {h.last_buy_date ?? "—"}
                  {h.days_since_buy !== null && (
                    <span className="text-zinc-600 ml-1">({h.days_since_buy}d)</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// --- Section 3: Buy Schedule ---

function BuyScheduleTable({ schedule }: { schedule: CoreScheduleEntry[] }) {
  if (schedule.length === 0) {
    return <p className="text-zinc-500 text-sm">No buy_list configured.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-zinc-400 border-b border-zinc-700">
            <th className="pb-2 pr-4">Symbol</th>
            <th className="pb-2 pr-4 text-right">Days Since Buy</th>
            <th className="pb-2 pr-4 text-right">Price</th>
            <th className="pb-2 pr-4 text-right">SMA-50</th>
            <th className="pb-2 pr-4 text-center">Dip?</th>
            <th className="pb-2 pr-4 text-center">DCA Due?</th>
            <th className="pb-2">Next Buy</th>
          </tr>
        </thead>
        <tbody>
          {schedule.map((s) => {
            const dipIndicator = s.is_dip
              ? <span className="text-green-400 font-medium">Yes</span>
              : <span className="text-zinc-500">No</span>;
            const dcaIndicator = s.dca_due
              ? <span className="text-green-400 font-medium">Due</span>
              : <span className="text-zinc-500">Not yet</span>;
            const daysSinceBuy = s.days_since_buy !== null
              ? (s.dca_due
                  ? <span className="text-green-400">{s.days_since_buy}d</span>
                  : <span className="text-zinc-400">{s.days_since_buy}d</span>)
              : <span className="text-zinc-500">Never</span>;
            return (
              <tr key={s.symbol} className="border-b border-zinc-800 hover:bg-zinc-800/40">
                <td className="py-2 pr-4 font-medium text-white">{s.symbol}</td>
                <td className="py-2 pr-4 text-right">{daysSinceBuy}</td>
                <td className="py-2 pr-4 text-right text-zinc-300">
                  {s.current_price != null ? `$${s.current_price.toFixed(2)}` : "—"}
                </td>
                <td className="py-2 pr-4 text-right text-zinc-400">
                  {s.sma50 != null ? `$${s.sma50.toFixed(2)}` : "—"}
                </td>
                <td className="py-2 pr-4 text-center">{dipIndicator}</td>
                <td className="py-2 pr-4 text-center">{dcaIndicator}</td>
                <td className="py-2 text-zinc-400 text-xs">{s.next_buy_date ?? "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// --- Section 4: Rebalance Status ---

function RebalanceStatus({
  daysUntilRebalance,
  nextRebalanceDate,
  holdings,
  preview,
  previewLoading,
}: {
  daysUntilRebalance: number;
  nextRebalanceDate: string;
  holdings: CoreHolding[];
  preview: RebalancePreviewItem[] | null;
  previewLoading: boolean;
}) {
  const urgencyColor = daysUntilRebalance <= 7
    ? "text-yellow-400"
    : daysUntilRebalance <= 30
    ? "text-zinc-300"
    : "text-zinc-400";

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <div>
          <span className="text-zinc-400 text-sm">Next rebalance: </span>
          <span className={`font-medium ${urgencyColor}`}>{nextRebalanceDate}</span>
          <span className="text-zinc-500 text-sm ml-2">({daysUntilRebalance} days)</span>
        </div>
      </div>

      {/* Weight bar chart */}
      {holdings.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs text-zinc-500 uppercase tracking-wide">Weight vs Target</div>
          {holdings.map((h) => {
            const actual = Math.round(h.weight_actual * 100);
            const target = Math.round(h.weight_target * 100);
            const barColor = Math.abs(h.drift) > 0.10
              ? "bg-red-500"
              : Math.abs(h.drift) > 0.05
              ? "bg-yellow-500"
              : "bg-green-500";
            return (
              <div key={h.symbol} className="flex items-center gap-2 text-xs">
                <span className="w-12 text-right text-zinc-400 font-mono">{h.symbol}</span>
                <div className="flex-1 h-4 bg-zinc-800 rounded relative">
                  {/* Target line */}
                  <div
                    className="absolute top-0 bottom-0 w-px bg-zinc-500"
                    style={{ left: `${target}%` }}
                  />
                  {/* Actual bar */}
                  <div
                    className={`h-full rounded ${barColor} opacity-70`}
                    style={{ width: `${Math.min(actual, 100)}%` }}
                  />
                </div>
                <span className="w-16 text-zinc-400 font-mono">
                  {actual}% / {target}%
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Preview rebalance */}
      <div>
        <div className="text-xs text-zinc-500 uppercase tracking-wide mb-2">Rebalance Preview (dry run)</div>
        {previewLoading ? (
          <p className="text-zinc-500 text-sm">Loading preview...</p>
        ) : preview && preview.length > 0 ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-zinc-400 border-b border-zinc-700">
                <th className="pb-1 pr-4">Symbol</th>
                <th className="pb-1 pr-4 text-center">Action</th>
                <th className="pb-1 pr-4 text-right">Qty</th>
                <th className="pb-1 pr-4 text-right">Price</th>
                <th className="pb-1 pr-4">Reason</th>
                <th className="pb-1 text-right">Weight Change</th>
              </tr>
            </thead>
            <tbody>
              {preview.map((item, i) => (
                <tr key={i} className="border-b border-zinc-800">
                  <td className="py-1 pr-4 font-medium text-white">{item.symbol}</td>
                  <td className="py-1 pr-4 text-center">
                    <span className={item.action === "buy" ? "text-green-400" : "text-red-400"}>
                      {item.action.toUpperCase()}
                    </span>
                  </td>
                  <td className="py-1 pr-4 text-right text-zinc-300">{item.qty.toFixed(4)}</td>
                  <td className="py-1 pr-4 text-right text-zinc-300">${item.price.toFixed(2)}</td>
                  <td className="py-1 pr-4 text-zinc-400 capitalize">{item.reason}</td>
                  <td className="py-1 text-right text-zinc-400 text-xs">
                    {(item.old_weight * 100).toFixed(1)}% → {(item.new_weight * 100).toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-zinc-500 text-sm">
            {preview ? "No rebalances needed — all positions within drift threshold." : "Unable to load preview."}
          </p>
        )}
      </div>
    </div>
  );
}

// --- Main Page ---

export default function CorePage() {
  const { data: status, error: statusError } = useCoreStatus();
  const { data: scheduleData, error: scheduleError } = useCoreSchedule();
  const { data: previewData, isLoading: previewLoading } = useRebalancePreview();

  if (statusError) {
    return (
      <div className="p-6 text-red-400">
        Failed to load core holdings status. Is the API server running?
      </div>
    );
  }

  if (!status) {
    return <div className="p-6 text-zinc-500">Loading core holdings...</div>;
  }

  return (
    <div className="p-6 space-y-8 max-w-6xl">
      <div>
        <h1 className="text-2xl font-bold text-white">Core Holdings</h1>
        <p className="text-zinc-400 text-sm mt-1">
          Long-term buy-and-hold portfolio with DCA entries and quarterly rebalancing.
        </p>
      </div>

      {/* Section 1: Portfolio Split */}
      <section>
        <h2 className="text-lg font-semibold text-zinc-200 mb-3">Portfolio Split</h2>
        <PortfolioSplitCards
          coreCapital={status.core_capital}
          invested={status.invested}
          cashRemaining={status.cash_remaining}
          holdingsCount={status.holdings.length}
        />
      </section>

      {/* Section 2: Holdings Table */}
      <section>
        <h2 className="text-lg font-semibold text-zinc-200 mb-3">Holdings</h2>
        <HoldingsTable holdings={status.holdings} />
      </section>

      {/* Section 3: Buy Schedule */}
      <section>
        <h2 className="text-lg font-semibold text-zinc-200 mb-3">Buy Schedule</h2>
        {scheduleError ? (
          <p className="text-red-400 text-sm">Failed to load schedule.</p>
        ) : scheduleData ? (
          <BuyScheduleTable schedule={scheduleData.schedule} />
        ) : (
          <p className="text-zinc-500 text-sm">Loading schedule...</p>
        )}
      </section>

      {/* Section 4: Rebalance Status */}
      <section>
        <h2 className="text-lg font-semibold text-zinc-200 mb-3">Rebalance Status</h2>
        <RebalanceStatus
          daysUntilRebalance={status.days_until_rebalance}
          nextRebalanceDate={status.next_rebalance_date}
          holdings={status.holdings}
          preview={previewData?.preview ?? null}
          previewLoading={previewLoading ?? false}
        />
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Add nav link to nav.tsx**

In `dashboard/src/components/nav.tsx`, add the Core Holdings link to the `links` array, after the `strategies` entry and before `config`:

```typescript
  { href: "/core", label: "Core Holdings", icon: "🏦" },
```

The updated `links` array:

```typescript
const links = [
  { href: "/", label: "Overview", icon: "📊" },
  { href: "/positions", label: "Positions", icon: "💼" },
  { href: "/trades", label: "Trades", icon: "📋" },
  { href: "/signals", label: "Signals", icon: "📡" },
  { href: "/discovery", label: "Discovery", icon: "🔍" },
  { href: "/lessons", label: "Lessons", icon: "🧠" },
  { href: "/learning", label: "Learning", icon: "📈" },
  { href: "/watchlist", label: "Watchlist", icon: "👁" },
  { href: "/strategies", label: "Strategies", icon: "🎯" },
  { href: "/core", label: "Core Holdings", icon: "🏦" },
  { href: "/config", label: "Config", icon: "⚙️" },
];
```

- [ ] **Step 5: TypeScript type-check**

```bash
cd /Users/adewaleadeleye/projects/claude-invest/dashboard && npx tsc --noEmit 2>&1
```
Expected: No errors. If there are missing type imports in `api.ts` (e.g., `CoreStatus` not listed in the import), fix the import list.

- [ ] **Step 6: Build dashboard**

```bash
cd /Users/adewaleadeleye/projects/claude-invest/dashboard && npm run build 2>&1 | tail -20
```
Expected: Build completes successfully. `/core` appears in the route listing.

- [ ] **Step 7: Smoke-test dashboard**

```bash
# Start API and dashboard
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/uvicorn claude_invest.api_server:app --port 8000 &
cd /Users/adewaleadeleye/projects/claude-invest/dashboard && npm run dev &
sleep 3
curl -s http://localhost:3000/core | grep -q "Core Holdings" && echo "Page renders OK"
```
Expected: `Page renders OK`.

- [ ] **Step 8: Commit**

```bash
git add dashboard/src/lib/types.ts dashboard/src/lib/api.ts dashboard/src/app/core/page.tsx dashboard/src/components/nav.tsx
git commit -m "feat: add /core dashboard page with holdings table, buy schedule, and rebalance preview"
```

---

## Task 9: Integration Test

**Files:**
- Create: `tests/test_core_integration.py`

- [ ] **Step 1: Write the integration test**

Create `tests/test_core_integration.py`:

```python
"""
End-to-end integration test for the core holdings cycle.

Scenario:
1. Create config with core_holdings (NVDA, MSFT, SPY at 33% each)
2. Seed DB with one existing core_buy for NVDA (10 days ago — DCA due)
3. Mock portfolio: NVDA already held; MSFT and SPY not held
4. Mock price data: MSFT price < SMA50 (dip); SPY price > SMA50 but DCA due
5. Run run_core_cycle()
6. Verify:
   - MSFT was bought (dip entry)
   - SPY was bought (dca_fallback — never bought before, dca_due)
   - NVDA was bought (dca_fallback — last buy 10d ago > interval 7d)
   - All 3 buys logged in core_buys table
   - All 3 buys logged in trades table with trade_type="core_holdings"
   - Decisions logged with correct reasoning
   - NVDA skip NOT in result (it was bought due to DCA)
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, call
from claude_invest.modules.db import Database
from claude_invest.modules.core_engine import run_core_cycle


@pytest.fixture
def integration_config():
    return {
        "mode": "paper",
        "capital": 6000,
        "capital_split": {"trading": 0.50, "core": 0.50},
        "core_holdings": {
            "enabled": True,
            "max_positions": 15,
            "buy_list": [
                {"symbol": "NVDA", "sector": "tech", "weight": 0.34},
                {"symbol": "MSFT", "sector": "tech", "weight": 0.33},
                {"symbol": "SPY",  "sector": "etf",  "weight": 0.33},
            ],
            "entry": {
                "mode": "dca_on_dip",
                "sma_period": 50,
                "dca_interval_days": 7,
                "max_per_buy": 0.02,
            },
            "exit": {
                "sell_on_signals": False,
                "sell_on_removal": True,
                "sentiment_exit_threshold": -0.3,
                "sentiment_exit_days": 5,
                "max_position_pct": 0.20,
            },
            "rebalance": {
                "interval_days": 90,
                "drift_threshold": 0.05,
            },
        },
    }


@pytest.fixture
def seeded_db(tmp_db_path, integration_config):
    db = Database(tmp_db_path)
    db.initialize()

    # NVDA: last buy 10 days ago (DCA due)
    old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
    db._get_conn().execute(
        "INSERT INTO core_buys (timestamp, symbol, qty, price, cost_basis) VALUES (?, ?, ?, ?, ?)",
        (old_ts, "NVDA", 0.1, 500.0, 50.0),
    )
    db._get_conn().commit()

    yield db
    db.close()


def _make_execute_order_mock(prices: dict):
    """Returns a mock execute_order that fills at given price per symbol."""
    def _mock_execute(symbol: str, side: str, qty: float):
        price = prices.get(symbol, 100.0)
        return {
            "status": "filled",
            "filled_price": price,
            "order_id": f"ord-{symbol}-{side}",
        }
    return MagicMock(side_effect=_mock_execute)


def _make_price_sma_mock(price_map: dict):
    """Returns a mock _get_price_and_sma with configurable price/sma per symbol."""
    def _mock(symbol: str, sma_period: int = 50):
        return price_map.get(symbol, {"close": 100.0, "sma50": 110.0})
    return _mock


def test_full_core_cycle_buys_and_logs(integration_config, seeded_db):
    """
    End-to-end: run_core_cycle with realistic config and seeded DB.
    Verifies buys, DB inserts, and decision logs.
    """
    price_data = {
        # NVDA: above SMA (no dip), but DCA due (10 days > 7 day interval)
        "NVDA": {"close": 530.0, "sma50": 510.0},
        # MSFT: below SMA → dip entry
        "MSFT": {"close": 380.0, "sma50": 400.0},
        # SPY: above SMA, no prior buy → dca_due (never bought)
        "SPY":  {"close": 520.0, "sma50": 510.0},
    }

    mock_portfolio = {
        "positions": [
            {
                "symbol": "NVDA",
                "qty": 0.1,
                "market_value": 53.0,
                "avg_entry_price": 500.0,
                "unrealized_pl": 3.0,
                "trade_type": "core_holdings",
            }
        ],
        "equity": 6053.0,
        "cash": 6000.0,
    }

    mock_execute = _make_execute_order_mock({
        "NVDA": 530.0, "MSFT": 380.0, "SPY": 520.0
    })

    with patch("claude_invest.modules.core_engine.get_portfolio", return_value=mock_portfolio), \
         patch("claude_invest.modules.core_engine._get_price_and_sma",
               side_effect=_make_price_sma_mock(price_data)), \
         patch("claude_invest.modules.core_engine.execute_order", mock_execute):
        result = run_core_cycle(integration_config, seeded_db)

    # --- Verify result structure ---
    assert "buys" in result
    assert "skips" in result
    assert "exits" in result
    assert "rebalances" in result

    # --- Verify buys ---
    bought_symbols = {b["symbol"] for b in result["buys"]}
    # MSFT: dip_entry (price 380 < sma 400)
    assert "MSFT" in bought_symbols, f"Expected MSFT buy (dip). Buys: {result['buys']}"
    # SPY: dca_fallback (never bought)
    assert "SPY" in bought_symbols, f"Expected SPY buy (dca_fallback). Buys: {result['buys']}"
    # NVDA: dca_fallback (last buy 10 days ago > interval 7)
    assert "NVDA" in bought_symbols, f"Expected NVDA buy (dca_fallback). Buys: {result['buys']}"

    # --- Verify buy reasons ---
    msft_buy = next(b for b in result["buys"] if b["symbol"] == "MSFT")
    spy_buy  = next(b for b in result["buys"] if b["symbol"] == "SPY")
    nvda_buy = next(b for b in result["buys"] if b["symbol"] == "NVDA")
    assert msft_buy["reason"] == "dip_entry",    f"Expected dip_entry for MSFT, got {msft_buy['reason']}"
    assert spy_buy["reason"]  == "dca_fallback", f"Expected dca_fallback for SPY, got {spy_buy['reason']}"
    assert nvda_buy["reason"] == "dca_fallback", f"Expected dca_fallback for NVDA, got {nvda_buy['reason']}"

    # --- Verify core_buys DB inserts ---
    all_core_buys = seeded_db.get_core_buys()
    # 3 new buys + 1 seeded NVDA = 4 total
    assert len(all_core_buys) == 4, f"Expected 4 core_buys entries, got {len(all_core_buys)}"

    new_symbols = {b["symbol"] for b in all_core_buys}
    assert "MSFT" in new_symbols
    assert "SPY"  in new_symbols
    assert "NVDA" in new_symbols

    # --- Verify trades table ---
    core_trades = [
        t for t in seeded_db.get_core_buys()  # all rows, then cross-check trades table
    ]
    # Direct check: each buy must be in the trades table with trade_type=core_holdings
    import sqlite3
    conn = seeded_db._get_conn()
    rows = conn.execute(
        "SELECT symbol, side, trade_type FROM trades WHERE trade_type = 'core_holdings'"
    ).fetchall()
    trade_symbols = {r["symbol"] for r in rows}
    assert "MSFT" in trade_symbols, "MSFT not found in trades table"
    assert "SPY"  in trade_symbols, "SPY not found in trades table"
    assert "NVDA" in trade_symbols, "NVDA not found in trades table"

    for row in rows:
        assert row["trade_type"] == "core_holdings"
        assert row["side"] == "buy"

    # --- Verify decisions table ---
    decisions = conn.execute(
        "SELECT ticker, action, signals_snapshot FROM decisions"
    ).fetchall()
    decision_tickers = {d["ticker"] for d in decisions}
    assert "MSFT" in decision_tickers, "MSFT not found in decisions table"
    assert "SPY"  in decision_tickers, "SPY not found in decisions table"
    assert "NVDA" in decision_tickers, "NVDA not found in decisions table"

    import json
    for d in decisions:
        snapshot = json.loads(d["signals_snapshot"])
        assert snapshot.get("strategy_id") == "core_holdings", (
            f"Expected strategy_id=core_holdings in snapshot for {d['ticker']}"
        )


def test_core_cycle_skips_at_target_weight(integration_config, seeded_db):
    """Symbol already at/above target weight is skipped, not re-bought."""
    core_capital = 6000 * 0.50  # 3000
    nvda_target = 0.34  # 34% of 3000 = 1020

    # NVDA: at target weight — should be skipped
    nvda_market_value = nvda_target * core_capital  # exactly at target

    mock_portfolio = {
        "positions": [
            {
                "symbol": "NVDA",
                "qty": 2.0,
                "market_value": nvda_market_value,
                "avg_entry_price": 510.0,
                "unrealized_pl": 0.0,
                "trade_type": "core_holdings",
            }
        ],
        "equity": 6000.0 + nvda_market_value,
        "cash": 6000.0,
    }

    price_data = {
        "NVDA": {"close": 510.0, "sma50": 510.0},
        "MSFT": {"close": 380.0, "sma50": 400.0},
        "SPY":  {"close": 520.0, "sma50": 510.0},
    }

    mock_execute = _make_execute_order_mock({"NVDA": 510.0, "MSFT": 380.0, "SPY": 520.0})

    with patch("claude_invest.modules.core_engine.get_portfolio", return_value=mock_portfolio), \
         patch("claude_invest.modules.core_engine._get_price_and_sma",
               side_effect=_make_price_sma_mock(price_data)), \
         patch("claude_invest.modules.core_engine.execute_order", mock_execute):
        result = run_core_cycle(integration_config, seeded_db)

    bought_symbols = {b["symbol"] for b in result["buys"]}
    skipped_symbols = {s["symbol"] for s in result["skips"]}

    assert "NVDA" not in bought_symbols, "NVDA should be skipped (at target weight)"
    assert "NVDA" in skipped_symbols, "NVDA should appear in skips"


def test_core_cycle_disabled_returns_empty(integration_config, seeded_db):
    """When core_holdings.enabled=False, cycle returns all-empty lists."""
    integration_config["core_holdings"]["enabled"] = False

    mock_portfolio = {"positions": [], "equity": 6000.0, "cash": 6000.0}

    with patch("claude_invest.modules.core_engine.get_portfolio", return_value=mock_portfolio):
        result = run_core_cycle(integration_config, seeded_db)

    assert result["buys"] == []
    assert result["skips"] == []
    assert result["exits"] == []
    assert result["rebalances"] == []

    # No DB writes
    all_buys = seeded_db.get_core_buys()
    assert len(all_buys) == 1  # only the seeded NVDA buy from fixture


def test_core_cycle_no_duplicate_buy_within_interval(integration_config, seeded_db):
    """Stock with a buy within dca_interval_days AND above SMA50 is NOT bought again."""
    # Insert a recent buy for MSFT (2 days ago — within 7-day interval)
    recent_ts = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    seeded_db._get_conn().execute(
        "INSERT INTO core_buys (timestamp, symbol, qty, price, cost_basis) VALUES (?, ?, ?, ?, ?)",
        (recent_ts, "MSFT", 0.1, 390.0, 39.0),
    )
    seeded_db._get_conn().commit()

    mock_portfolio = {"positions": [], "equity": 6000.0, "cash": 6000.0}
    price_data = {
        "NVDA": {"close": 530.0, "sma50": 510.0},
        # MSFT: above SMA (no dip) AND last buy 2 days ago (< interval) → skip
        "MSFT": {"close": 410.0, "sma50": 400.0},
        "SPY":  {"close": 520.0, "sma50": 510.0},
    }

    mock_execute = _make_execute_order_mock({"NVDA": 530.0, "MSFT": 410.0, "SPY": 520.0})

    with patch("claude_invest.modules.core_engine.get_portfolio", return_value=mock_portfolio), \
         patch("claude_invest.modules.core_engine._get_price_and_sma",
               side_effect=_make_price_sma_mock(price_data)), \
         patch("claude_invest.modules.core_engine.execute_order", mock_execute):
        result = run_core_cycle(integration_config, seeded_db)

    bought_symbols = {b["symbol"] for b in result["buys"]}
    skipped_symbols = {s["symbol"] for s in result["skips"]}

    assert "MSFT" not in bought_symbols, (
        f"MSFT should NOT be bought (above SMA, recent buy). Buys: {result['buys']}"
    )
    assert "MSFT" in skipped_symbols, (
        f"MSFT should be in skips. Skips: {result['skips']}"
    )


def test_core_cycle_exit_removes_delisted_stock(integration_config, seeded_db):
    """Stock not in buy_list but held as core_holdings is sold (sell_on_removal)."""
    # TSLA is NOT in the buy_list
    mock_portfolio = {
        "positions": [
            {
                "symbol": "TSLA",
                "qty": 1.0,
                "market_value": 200.0,
                "avg_entry_price": 200.0,
                "unrealized_pl": 0.0,
                "trade_type": "core_holdings",
            }
        ],
        "equity": 6200.0,
        "cash": 6000.0,
    }

    price_data = {
        "NVDA": {"close": 530.0, "sma50": 510.0},
        "MSFT": {"close": 380.0, "sma50": 400.0},
        "SPY":  {"close": 520.0, "sma50": 510.0},
        "TSLA": {"close": 200.0, "sma50": 210.0},
    }

    mock_execute = _make_execute_order_mock(
        {"NVDA": 530.0, "MSFT": 380.0, "SPY": 520.0, "TSLA": 200.0}
    )

    with patch("claude_invest.modules.core_engine.get_portfolio", return_value=mock_portfolio), \
         patch("claude_invest.modules.core_engine._get_price_and_sma",
               side_effect=_make_price_sma_mock(price_data)), \
         patch("claude_invest.modules.core_engine.execute_order", mock_execute):
        result = run_core_cycle(integration_config, seeded_db)

    assert len(result["exits"]) == 1, f"Expected 1 exit (TSLA removal). Exits: {result['exits']}"
    assert result["exits"][0]["symbol"] == "TSLA"
    assert result["exits"][0]["reason"] == "removal"
```

- [ ] **Step 2: Run tests to confirm they fail first**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest tests/test_core_integration.py -v 2>&1 | head -40
```
Expected: Failures if `core_engine` not yet implemented (Tasks 1-5 not done), or all pass if run after Tasks 1-6. Run this after Task 5 is complete.

- [ ] **Step 3: Run all integration tests**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest tests/test_core_integration.py -v
```
Expected: 5/5 pass:
- `test_full_core_cycle_buys_and_logs` — all 3 buys executed and logged
- `test_core_cycle_skips_at_target_weight` — NVDA skipped at target
- `test_core_cycle_disabled_returns_empty` — empty result when disabled
- `test_core_cycle_no_duplicate_buy_within_interval` — MSFT not bought twice
- `test_core_cycle_exit_removes_delisted_stock` — TSLA sold on removal

- [ ] **Step 4: Run full test suite**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest --tb=short -q
```
Expected: All tests pass — no regressions across Tasks 1-9.

- [ ] **Step 5: Print a summary of all core tests**

```bash
cd /Users/adewaleadeleye/projects/claude-invest && .venv/bin/pytest tests/test_capital_split.py tests/test_core_db.py tests/test_risk_manager_core.py tests/test_core_engine.py tests/test_core_cli.py tests/test_core_api.py tests/test_core_integration.py -v --tb=short 2>&1 | tail -30
```
Expected: All core tests pass, total count printed.

- [ ] **Step 6: Commit**

```bash
git add tests/test_core_integration.py
git commit -m "feat: add end-to-end integration tests for core holdings cycle"
```

---

## Self-Review

### Spec Coverage
| Spec Section | Task(s) |
|---|---|
| 1. Capital Management | Task 1, 3 |
| 2. Core Holdings Config | Task 1 |
| 3. Core Engine | Task 5 |
| 4. Database Changes | Task 2 |
| 5. Cron Schedule | Documented in Task 5 |
| 6. CLI Commands | Task 6 |
| 7. API Endpoints | Task 7 |
| 8. Dashboard | Task 8 |
| 9. Risk Manager | Task 4 |
| 10. Learning Engine Integration | Task 5 (tags with strategy_id) |
| 11. Existing Strategy Integration | Task 3 |
| 12. Not Included | N/A (documented) |
| 13. Testing | Tasks 1-9 |
