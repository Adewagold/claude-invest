# Learning Engine & Portfolio Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a learning engine that analyzes trade outcomes, scores signal patterns, and feeds strategy lessons back into the trading crons — plus a portfolio tracker that monitors allocation across risk tiers and sectors.

**Architecture:** Three new Python modules (learner, portfolio_tracker, strategy) that read from the existing SQLite database. A lessons/ directory stores accumulated patterns and the strategy brief. Cron prompts are updated to read the strategy brief. New CLI commands and API endpoints expose the data.

**Tech Stack:** Python 3.12+, SQLite (existing), pytest, FastAPI (existing)

---

## File Structure

```
claude-invest/
├── src/claude_invest/
│   ├── modules/
│   │   ├── learner.py              # Pattern analyzer (NEW)
│   │   ├── portfolio_tracker.py    # Allocation monitor (NEW)
│   │   ├── strategy.py             # Strategy brief builder (NEW)
│   │   ├── api_server.py           # Add new endpoints (MODIFY)
│   │   └── ... existing modules unchanged
│   ├── main.py                     # Add new CLI commands (MODIFY)
│   └── config/
│       └── settings.yaml           # Add portfolio config (MODIFY)
├── lessons/                        # Lessons storage (NEW)
│   ├── lessons.json
│   ├── strategy-brief.md
│   └── daily/
├── tests/
│   ├── test_learner.py             # NEW
│   ├── test_portfolio_tracker.py   # NEW
│   └── test_strategy.py            # NEW
```

---

### Task 1: Config Extension

**Files:**
- Modify: `src/claude_invest/config/settings.yaml`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing test**

`tests/test_config.py` — add to existing file:
```python
def test_config_has_portfolio_section():
    config = load_config()
    assert "portfolio" in config
    assert "allocation" in config["portfolio"]
    assert config["portfolio"]["allocation"]["safe"] == 0.30
    assert config["portfolio"]["allocation"]["neutral"] == 0.40
    assert config["portfolio"]["allocation"]["risk"] == 0.30
    assert "drift_threshold" in config["portfolio"]
    assert "sectors" in config["portfolio"]
    assert "risk_tiers" in config


def test_config_risk_tiers():
    config = load_config()
    assert "safe" in config["risk_tiers"]
    assert "neutral" in config["risk_tiers"]
    assert "risk" in config["risk_tiers"]
    assert "meme" in config["risk_tiers"]["risk"]
    assert "technology" in config["risk_tiers"]["neutral"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && .venv/bin/pytest tests/test_config.py -v`
Expected: FAIL — KeyError on "portfolio"

- [ ] **Step 3: Add portfolio config to settings.yaml**

Append to `src/claude_invest/config/settings.yaml`:
```yaml

portfolio:
  allocation:
    safe: 0.30
    neutral: 0.40
    risk: 0.30
  drift_threshold: 0.10
  sectors:
    overrides:
      TRUMP/USD: "meme"
      DOGE/USD: "meme"
      SHIB/USD: "meme"
      BONK/USD: "meme"
      WIF/USD: "meme"
      PEPE/USD: "meme"
  time_horizon:
    short_term_max_days: 30
    long_term_min_days: 30

risk_tiers:
  safe:
    - bonds
    - reits
    - dividend
    - utilities
    - consumer_staples
  neutral:
    - large_cap
    - technology
    - healthcare
    - financial
    - industrial
    - energy
  risk:
    - small_cap
    - biotech
    - meme
    - crypto
    - penny
    - speculative
```

- [ ] **Step 4: Update config validation to include new keys**

In `src/claude_invest/config/loader.py`, add `"portfolio"` and `"risk_tiers"` to `REQUIRED_KEYS`:
```python
REQUIRED_KEYS = [
    "mode", "capital", "max_positions", "max_per_ticker",
    "position_size_pct", "daily_loss_limit", "pdt_tracking",
    "exit_strategy", "polling", "discovery", "trading_style",
    "portfolio", "risk_tiers",
]
```

- [ ] **Step 5: Update sample_config fixture in conftest.py**

Add to the `sample_config` fixture in `tests/conftest.py`:
```python
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
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `source .venv/bin/activate && .venv/bin/pytest tests/test_config.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/claude_invest/config/ tests/test_config.py tests/conftest.py
git commit -m "feat: add portfolio allocation and risk tier config"
```

---

### Task 2: Portfolio Tracker Module

**Files:**
- Create: `src/claude_invest/modules/portfolio_tracker.py`
- Create: `tests/test_portfolio_tracker.py`

- [ ] **Step 1: Write failing tests**

`tests/test_portfolio_tracker.py`:
```python
import pytest
from claude_invest.modules.portfolio_tracker import (
    classify_sector,
    assign_risk_tier,
    get_allocation,
)


@pytest.fixture
def tracker_config(sample_config):
    config, _ = sample_config
    return config


def test_classify_sector_with_override(tracker_config):
    result = classify_sector("TRUMP/USD", tracker_config)
    assert result == "meme"


def test_classify_sector_default():
    # Without override, crypto symbols default to "crypto"
    config = {
        "portfolio": {"sectors": {"overrides": {}}},
        "risk_tiers": {},
    }
    result = classify_sector("BTC/USD", config)
    assert result == "crypto"


def test_assign_risk_tier_meme(tracker_config):
    tier = assign_risk_tier("meme", tracker_config)
    assert tier == "risk"


def test_assign_risk_tier_technology(tracker_config):
    tier = assign_risk_tier("technology", tracker_config)
    assert tier == "neutral"


def test_assign_risk_tier_reits(tracker_config):
    tier = assign_risk_tier("reits", tracker_config)
    assert tier == "safe"


def test_assign_risk_tier_unknown(tracker_config):
    tier = assign_risk_tier("unknown_sector", tracker_config)
    assert tier == "neutral"  # default to neutral


def test_get_allocation_basic(tracker_config):
    positions = [
        {"symbol": "PFE", "market_value": 5300.0, "avg_entry_price": 26.52, "current_price": 27.56, "qty": 194},
        {"symbol": "BTCUSD", "market_value": 99.0, "avg_entry_price": 75658, "current_price": 76000, "qty": 0.0013},
        {"symbol": "TRUMPUSD", "market_value": 100.0, "avg_entry_price": 2.84, "current_price": 2.90, "qty": 35},
    ]
    result = get_allocation(tracker_config, positions)

    assert "tiers" in result
    assert "safe" in result["tiers"]
    assert "neutral" in result["tiers"]
    assert "risk" in result["tiers"]
    assert result["total_value"] == 5499.0
    assert "sectors" in result
    # TRUMP should be in meme (risk tier via override)
    assert "meme" in result["sectors"]


def test_get_allocation_drift_detection(tracker_config):
    # All in one position — should trigger drift alerts
    positions = [
        {"symbol": "PFE", "market_value": 5000.0, "avg_entry_price": 26.52, "current_price": 27.56, "qty": 194},
    ]
    result = get_allocation(tracker_config, positions)

    # PFE is healthcare → neutral tier. 100% in neutral, 0% in safe/risk
    # All tiers should have drift alerts (threshold is 10%)
    assert result["tiers"]["safe"]["alert"] is True
    assert result["tiers"]["risk"]["alert"] is True


def test_get_allocation_empty_positions(tracker_config):
    result = get_allocation(tracker_config, [])
    assert result["total_value"] == 0
    assert result["tiers"]["safe"]["actual"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && .venv/bin/pytest tests/test_portfolio_tracker.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement portfolio tracker**

`src/claude_invest/modules/portfolio_tracker.py`:
```python
from datetime import datetime, timezone


# Default sector mapping for symbols
CRYPTO_SYMBOLS = {"BTC", "ETH", "SOL", "DOGE", "SHIB", "PEPE", "BONK", "WIF",
                  "TRUMP", "LINK", "ADA", "AVAX", "DOT", "XRP", "LTC"}

SECTOR_KEYWORDS = {
    "healthcare": ["PFE", "JNJ", "UNH", "MRNA", "ABT", "LLY", "BMY"],
    "technology": ["AAPL", "MSFT", "NVDA", "SNDK", "INTC", "AMD", "GOOG", "META", "AMZN"],
    "energy": ["XOM", "CVX", "XLE", "OIL", "SCO", "USO"],
    "reits": ["O", "AMT", "SPG", "VNQ", "VICI"],
    "financial": ["JPM", "BAC", "GS", "V", "MA"],
}


def classify_sector(symbol: str, config: dict) -> str:
    overrides = config.get("portfolio", {}).get("sectors", {}).get("overrides", {})
    if symbol in overrides:
        return overrides[symbol]

    # Strip /USD suffix for matching
    base = symbol.replace("/USD", "").replace("USD", "")

    if base in CRYPTO_SYMBOLS:
        return "crypto"

    for sector, tickers in SECTOR_KEYWORDS.items():
        if base in tickers or symbol in tickers:
            return sector

    return "general"


def assign_risk_tier(sector: str, config: dict) -> str:
    risk_tiers = config.get("risk_tiers", {})
    for tier, sectors in risk_tiers.items():
        if sector in sectors:
            return tier
    return "neutral"


def get_allocation(config: dict, positions: list[dict]) -> dict:
    allocation_targets = config.get("portfolio", {}).get("allocation", {})
    drift_threshold = config.get("portfolio", {}).get("drift_threshold", 0.10)

    total_value = sum(p["market_value"] for p in positions)

    # Classify each position
    classified = []
    for p in positions:
        sector = classify_sector(p["symbol"], config)
        tier = assign_risk_tier(sector, config)
        classified.append({**p, "sector": sector, "tier": tier})

    # Aggregate by tier
    tier_values = {"safe": 0.0, "neutral": 0.0, "risk": 0.0}
    for p in classified:
        tier_values[p["tier"]] = tier_values.get(p["tier"], 0) + p["market_value"]

    # Build tier summary
    tiers = {}
    for tier_name in ["safe", "neutral", "risk"]:
        target = allocation_targets.get(tier_name, 0.33)
        actual = tier_values[tier_name] / total_value if total_value > 0 else 0
        drift = actual - target
        tiers[tier_name] = {
            "target": target,
            "actual": round(actual, 4),
            "drift": round(drift, 4),
            "value": round(tier_values[tier_name], 2),
            "alert": abs(drift) > drift_threshold,
        }

    # Aggregate by sector
    sectors = {}
    for p in classified:
        if p["sector"] not in sectors:
            sectors[p["sector"]] = {"value": 0.0, "positions": []}
        sectors[p["sector"]]["value"] += p["market_value"]
        sectors[p["sector"]]["positions"].append(p["symbol"])
    for s in sectors.values():
        s["pct"] = round(s["value"] / total_value, 4) if total_value > 0 else 0
        s["value"] = round(s["value"], 2)

    # Time horizon (based on hold duration — simplified, uses entry date if available)
    time_horizon = {"short_term": [], "long_term": []}
    for p in classified:
        # Without entry timestamps in position data, default to short_term
        time_horizon["short_term"].append(p["symbol"])

    return {
        "total_value": round(total_value, 2),
        "tiers": tiers,
        "sectors": sectors,
        "positions": classified,
        "time_horizon": time_horizon,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && .venv/bin/pytest tests/test_portfolio_tracker.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/claude_invest/modules/portfolio_tracker.py tests/test_portfolio_tracker.py
git commit -m "feat: add portfolio tracker with sector classification and allocation monitoring"
```

---

### Task 3: Learner Module

**Files:**
- Create: `src/claude_invest/modules/learner.py`
- Create: `tests/test_learner.py`

- [ ] **Step 1: Write failing tests**

`tests/test_learner.py`:
```python
import json
import pytest
from claude_invest.modules.db import Database
from claude_invest.modules.learner import (
    parse_signal_combo,
    analyze_day,
    score_patterns,
)


@pytest.fixture
def seeded_db(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()

    # Winning trade: MACD crossover + RSI 45 + neutral trend
    db.insert_decision({
        "ticker": "BTC/USD",
        "action": "buy",
        "reasoning": "MACD crossover, RSI 45",
        "signals_snapshot": json.dumps({
            "rsi": 45, "macd": -200, "macd_signal": -250,
            "trend": "neutral", "sentiment": 0.1, "price": 75000,
        }),
    })
    db.insert_decision({
        "ticker": "BTC/USD",
        "action": "sell",
        "reasoning": "Taking profit",
        "signals_snapshot": json.dumps({"price": 76000}),
    })
    db.insert_trade({
        "symbol": "BTC/USD", "side": "buy", "qty": 0.001,
        "price": 75000, "order_id": "t1", "trade_type": "swing", "status": "filled",
    })
    db.insert_trade({
        "symbol": "BTC/USD", "side": "sell", "qty": 0.001,
        "price": 76000, "order_id": "t2", "trade_type": "swing", "status": "filled",
    })

    # Losing trade: RSI > 70 + gap up
    db.insert_decision({
        "ticker": "CMND",
        "action": "buy",
        "reasoning": "FDA catalyst",
        "signals_snapshot": json.dumps({
            "rsi": 74.5, "macd": 0.13, "macd_signal": 0.06,
            "trend": "bullish", "sentiment": 0.2, "price": 1.45,
        }),
    })
    db.insert_decision({
        "ticker": "CMND",
        "action": "sell",
        "reasoning": "Stop loss",
        "signals_snapshot": json.dumps({"price": 1.30}),
    })
    db.insert_trade({
        "symbol": "CMND", "side": "buy", "qty": 80,
        "price": 1.45, "order_id": "t3", "trade_type": "day", "status": "filled",
    })
    db.insert_trade({
        "symbol": "CMND", "side": "sell", "qty": 80,
        "price": 1.30, "order_id": "t4", "trade_type": "day", "status": "filled",
    })

    return db


def test_parse_signal_combo():
    snapshot = {"rsi": 45, "macd": -200, "macd_signal": -250, "trend": "neutral", "sentiment": 0.1}
    combo = parse_signal_combo(snapshot)

    assert "rsi_30_50" in combo
    assert "macd_above_signal" in combo
    assert "trend_neutral" in combo


def test_parse_signal_combo_overbought():
    snapshot = {"rsi": 74.5, "macd": 0.13, "macd_signal": 0.06, "trend": "bullish", "sentiment": 0.2}
    combo = parse_signal_combo(snapshot)

    assert "rsi_70_100" in combo
    assert "macd_above_signal" in combo
    assert "trend_bullish" in combo


def test_score_patterns(seeded_db):
    patterns = score_patterns(seeded_db)

    # Should have at least 2 pattern entries
    assert len(patterns) >= 2

    # The RSI 30-50 pattern should be a win
    rsi_30_50 = [p for p in patterns if "rsi_30_50" in p["signal_combo"]]
    if rsi_30_50:
        assert rsi_30_50[0]["wins"] >= 1

    # The RSI 70-100 pattern should be a loss
    rsi_70_100 = [p for p in patterns if "rsi_70_100" in p["signal_combo"]]
    if rsi_70_100:
        assert rsi_70_100[0]["losses"] >= 1


def test_analyze_day(seeded_db):
    report = analyze_day(seeded_db)

    assert "total_trades" in report
    assert "wins" in report
    assert "losses" in report
    assert "win_rate" in report
    assert "patterns" in report
    assert "total_pnl" in report
    assert report["total_trades"] >= 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && .venv/bin/pytest tests/test_learner.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement learner module**

`src/claude_invest/modules/learner.py`:
```python
import json
from datetime import datetime, timezone

from claude_invest.modules.db import Database


def parse_signal_combo(snapshot: dict) -> str:
    parts = []

    rsi = snapshot.get("rsi")
    if rsi is not None:
        if rsi < 30:
            parts.append("rsi_0_30")
        elif rsi < 50:
            parts.append("rsi_30_50")
        elif rsi < 70:
            parts.append("rsi_50_70")
        else:
            parts.append("rsi_70_100")

    macd = snapshot.get("macd")
    macd_sig = snapshot.get("macd_signal")
    if macd is not None and macd_sig is not None:
        if macd > macd_sig:
            parts.append("macd_above_signal")
        else:
            parts.append("macd_below_signal")

    trend = snapshot.get("trend")
    if trend:
        parts.append(f"trend_{trend}")

    sentiment = snapshot.get("sentiment")
    if sentiment is not None:
        if sentiment > 0.3:
            parts.append("sent_positive")
        elif sentiment < -0.2:
            parts.append("sent_negative")
        else:
            parts.append("sent_neutral")

    return " + ".join(sorted(parts)) if parts else "unknown"


def _match_trades(db: Database) -> list[dict]:
    trades = db.get_trades(limit=500)
    decisions = db.get_decisions(limit=500)

    # Group trades by symbol: pair buys with subsequent sells
    buy_decisions = [d for d in decisions if d["action"] == "buy"]
    sell_decisions = [d for d in decisions if d["action"] == "sell"]

    matched = []
    for buy in buy_decisions:
        ticker = buy["ticker"]
        buy_time = buy["timestamp"]

        # Find corresponding sell
        sell = None
        for s in sell_decisions:
            if s["ticker"] == ticker and s["timestamp"] > buy_time:
                sell = s
                break

        # Parse entry signals
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
            exit_price = 0
            pnl = 0
            status = "open"

        matched.append({
            "ticker": ticker,
            "entry_time": buy_time,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": pnl,
            "win": pnl > 0,
            "status": status,
            "signal_combo": parse_signal_combo(entry_signals),
            "entry_signals": entry_signals,
            "reasoning": buy.get("reasoning", ""),
        })

    return matched


def score_patterns(db: Database) -> list[dict]:
    matched = _match_trades(db)
    closed = [m for m in matched if m["status"] == "closed"]

    # Group by signal combo
    combos: dict[str, dict] = {}
    for trade in closed:
        combo = trade["signal_combo"]
        if combo not in combos:
            combos[combo] = {"wins": 0, "losses": 0, "total_pnl": 0.0, "trades": []}
        if trade["win"]:
            combos[combo]["wins"] += 1
        else:
            combos[combo]["losses"] += 1
        combos[combo]["total_pnl"] += trade["pnl"]
        combos[combo]["trades"].append(trade["ticker"])

    patterns = []
    for combo, data in combos.items():
        total = data["wins"] + data["losses"]
        win_rate = data["wins"] / total if total > 0 else 0
        confidence = "high" if total >= 3 else "low"
        patterns.append({
            "signal_combo": combo,
            "wins": data["wins"],
            "losses": data["losses"],
            "total": total,
            "win_rate": round(win_rate, 4),
            "avg_pnl": round(data["total_pnl"] / total, 4) if total > 0 else 0,
            "confidence": confidence,
            "tickers": data["trades"],
        })

    patterns.sort(key=lambda x: x["win_rate"], reverse=True)
    return patterns


def analyze_day(db: Database, date: str | None = None) -> dict:
    matched = _match_trades(db)
    closed = [m for m in matched if m["status"] == "closed"]

    wins = sum(1 for t in closed if t["win"])
    losses = sum(1 for t in closed if not t["win"])
    total = wins + losses
    total_pnl = sum(t["pnl"] for t in closed)

    patterns = score_patterns(db)

    mistakes = []
    for t in closed:
        if not t["win"] and t["entry_signals"].get("rsi", 0) > 70:
            mistakes.append(
                f"Bought {t['ticker']} at RSI {t['entry_signals']['rsi']:.1f} — lost"
            )

    return {
        "date": date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / total, 4) if total > 0 else 0,
        "total_pnl": round(total_pnl, 4),
        "patterns": patterns,
        "mistakes": mistakes,
        "open_positions": [m for m in matched if m["status"] == "open"],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && .venv/bin/pytest tests/test_learner.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/claude_invest/modules/learner.py tests/test_learner.py
git commit -m "feat: add learner module with pattern analysis and trade matching"
```

---

### Task 4: Strategy Builder Module

**Files:**
- Create: `src/claude_invest/modules/strategy.py`
- Create: `tests/test_strategy.py`
- Create: `lessons/` directory

- [ ] **Step 1: Write failing tests**

`tests/test_strategy.py`:
```python
import json
import os
import pytest
from claude_invest.modules.strategy import (
    update_lessons,
    build_strategy_brief,
    load_lessons,
)


@pytest.fixture
def lessons_dir(tmp_path):
    d = tmp_path / "lessons"
    d.mkdir()
    (d / "daily").mkdir()
    return str(d)


def test_update_lessons_creates_file(lessons_dir):
    patterns = [
        {
            "signal_combo": "macd_above_signal + rsi_30_50 + trend_neutral",
            "wins": 3, "losses": 0, "total": 3,
            "win_rate": 1.0, "avg_pnl": 1.5, "confidence": "high",
            "tickers": ["BTC/USD", "ETH/USD", "TRUMP/USD"],
        },
        {
            "signal_combo": "macd_above_signal + rsi_70_100 + trend_bullish",
            "wins": 0, "losses": 2, "total": 2,
            "win_rate": 0.0, "avg_pnl": -8.5, "confidence": "low",
            "tickers": ["CMND", "ATAI"],
        },
    ]
    update_lessons(lessons_dir, patterns, "2026-04-20")

    lessons_path = os.path.join(lessons_dir, "lessons.json")
    assert os.path.exists(lessons_path)

    data = json.loads(open(lessons_path).read())
    assert len(data["patterns"]) == 2
    assert data["last_updated"] == "2026-04-20"


def test_load_lessons_empty(lessons_dir):
    lessons = load_lessons(lessons_dir)
    assert lessons["patterns"] == []


def test_load_lessons_existing(lessons_dir):
    data = {"patterns": [{"signal_combo": "test", "wins": 1}], "last_updated": "2026-04-20"}
    with open(os.path.join(lessons_dir, "lessons.json"), "w") as f:
        json.dump(data, f)

    lessons = load_lessons(lessons_dir)
    assert len(lessons["patterns"]) == 1


def test_build_strategy_brief(lessons_dir):
    patterns = [
        {
            "signal_combo": "macd_above_signal + rsi_30_50",
            "wins": 4, "losses": 0, "total": 4,
            "win_rate": 1.0, "avg_pnl": 2.0, "confidence": "high",
        },
        {
            "signal_combo": "rsi_70_100",
            "wins": 0, "losses": 3, "total": 3,
            "win_rate": 0.0, "avg_pnl": -10.0, "confidence": "high",
        },
    ]
    update_lessons(lessons_dir, patterns, "2026-04-20")

    allocation = {
        "tiers": {
            "safe": {"target": 0.30, "actual": 0.0, "drift": -0.30, "alert": True},
            "neutral": {"target": 0.40, "actual": 0.80, "drift": 0.40, "alert": True},
            "risk": {"target": 0.30, "actual": 0.20, "drift": -0.10, "alert": False},
        },
        "total_value": 5500,
    }

    brief = build_strategy_brief(lessons_dir, allocation)

    assert "ALWAYS" in brief or "PREFER" in brief
    assert "NEVER" in brief or "AVOID" in brief
    assert "rsi_70_100" in brief
    assert isinstance(brief, str)
    assert len(brief) > 50

    # Should be written to file
    brief_path = os.path.join(lessons_dir, "strategy-brief.md")
    assert os.path.exists(brief_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && .venv/bin/pytest tests/test_strategy.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Create lessons directory**

```bash
mkdir -p /Users/adewaleadeleye/projects/claude-invest/lessons/daily
echo '{"patterns": [], "last_updated": null}' > /Users/adewaleadeleye/projects/claude-invest/lessons/lessons.json
echo "No strategy brief generated yet. Run: python main.py review-day" > /Users/adewaleadeleye/projects/claude-invest/lessons/strategy-brief.md
```

- [ ] **Step 4: Implement strategy module**

`src/claude_invest/modules/strategy.py`:
```python
import json
import os
from datetime import datetime, timezone


def load_lessons(lessons_dir: str) -> dict:
    path = os.path.join(lessons_dir, "lessons.json")
    if not os.path.exists(path):
        return {"patterns": [], "last_updated": None}
    with open(path) as f:
        return json.load(f)


def update_lessons(lessons_dir: str, patterns: list[dict], date: str):
    existing = load_lessons(lessons_dir)

    # Merge patterns: update existing combos, add new ones
    existing_combos = {p["signal_combo"]: p for p in existing["patterns"]}
    for p in patterns:
        combo = p["signal_combo"]
        if combo in existing_combos:
            old = existing_combos[combo]
            old["wins"] = p["wins"]
            old["losses"] = p["losses"]
            old["total"] = p["total"]
            old["win_rate"] = p["win_rate"]
            old["avg_pnl"] = p["avg_pnl"]
            old["confidence"] = p["confidence"]
        else:
            existing_combos[combo] = p

    data = {
        "patterns": list(existing_combos.values()),
        "last_updated": date,
    }

    path = os.path.join(lessons_dir, "lessons.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    # Write daily report
    daily_path = os.path.join(lessons_dir, "daily", f"{date}.md")
    os.makedirs(os.path.dirname(daily_path), exist_ok=True)
    with open(daily_path, "w") as f:
        f.write(f"# Trading Lessons — {date}\n\n")
        for p in sorted(patterns, key=lambda x: x["win_rate"], reverse=True):
            status = "WIN" if p["win_rate"] > 0.5 else "LOSS" if p["win_rate"] < 0.5 else "MIXED"
            f.write(f"- [{status}] {p['signal_combo']}: {p['wins']}W/{p['losses']}L (avg P&L: {p['avg_pnl']:.2f})\n")


def build_strategy_brief(lessons_dir: str, allocation: dict) -> str:
    lessons = load_lessons(lessons_dir)
    patterns = lessons.get("patterns", [])

    lines = ["# Strategy Brief", ""]
    lines.append(f"*Updated: {lessons.get('last_updated', 'never')}*")
    lines.append("")

    # Rules (high confidence)
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

    # Allocation alerts
    tiers = allocation.get("tiers", {})
    alerts = [(name, t) for name, t in tiers.items() if t.get("alert")]
    if alerts:
        lines.append("## ALLOCATION ALERTS")
        for name, t in alerts:
            direction = "OVER" if t["drift"] > 0 else "UNDER"
            lines.append(f"- {name.upper()}: {t['actual']:.0%} actual vs {t['target']:.0%} target ({direction} by {abs(t['drift']):.0%})")
        lines.append("")

    # Win rate summary
    total_wins = sum(p.get("wins", 0) for p in patterns)
    total_losses = sum(p.get("losses", 0) for p in patterns)
    total = total_wins + total_losses
    if total > 0:
        lines.append(f"## OVERALL: {total_wins}W/{total_losses}L ({total_wins/total:.0%} win rate)")

    brief = "\n".join(lines)

    # Write to file
    brief_path = os.path.join(lessons_dir, "strategy-brief.md")
    with open(brief_path, "w") as f:
        f.write(brief)

    return brief
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `source .venv/bin/activate && .venv/bin/pytest tests/test_strategy.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/claude_invest/modules/strategy.py tests/test_strategy.py lessons/
git commit -m "feat: add strategy builder with lessons storage and strategy brief generation"
```

---

### Task 5: CLI Commands

**Files:**
- Modify: `src/claude_invest/main.py`

- [ ] **Step 1: Add review-day, allocation, and lessons commands**

Add these functions and CLI routes to `src/claude_invest/main.py`:

```python
# Add imports at top:
from claude_invest.modules.learner import analyze_day, score_patterns
from claude_invest.modules.portfolio_tracker import get_allocation
from claude_invest.modules.strategy import update_lessons, build_strategy_brief, load_lessons

LESSONS_DIR = "lessons"


def cmd_review_day(date: str | None = None):
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()

    # Analyze trades
    report = analyze_day(db, date)

    # Get allocation
    from claude_invest.modules.portfolio import get_portfolio
    try:
        portfolio = get_portfolio()
        allocation = get_allocation(config, portfolio["positions"])
    except Exception:
        allocation = {"tiers": {}, "total_value": 0}

    # Update lessons
    update_lessons(LESSONS_DIR, report["patterns"], report["date"])

    # Build strategy brief
    brief = build_strategy_brief(LESSONS_DIR, allocation)

    report["allocation"] = allocation
    report["strategy_brief"] = brief

    db.close()
    _output(report)


def cmd_allocation():
    config = load_config()
    from claude_invest.modules.portfolio import get_portfolio
    portfolio = get_portfolio()
    allocation = get_allocation(config, portfolio["positions"])
    _output(allocation)


def cmd_lessons():
    lessons = load_lessons(LESSONS_DIR)
    _output(lessons)
```

Add CLI routes in the `main()` function:
```python
    elif command == "review-day":
        cmd_review_day(sys.argv[2] if len(sys.argv) >= 3 else None)
    elif command == "allocation":
        cmd_allocation()
    elif command == "lessons":
        cmd_lessons()
```

Also update the usage message to include the new commands:
```python
    "review-day [date]", "allocation", "lessons",
```

- [ ] **Step 2: Test CLI manually**

Run:
```bash
source .venv/bin/activate
.venv/bin/python -m claude_invest.main review-day
.venv/bin/python -m claude_invest.main allocation
.venv/bin/python -m claude_invest.main lessons
```
Expected: JSON output for each command.

- [ ] **Step 3: Commit**

```bash
git add src/claude_invest/main.py
git commit -m "feat: add review-day, allocation, and lessons CLI commands"
```

---

### Task 6: API Endpoints

**Files:**
- Modify: `src/claude_invest/modules/api_server.py`

- [ ] **Step 1: Add new endpoints**

Add these imports and endpoints to `api_server.py`:

```python
# Add imports:
from claude_invest.modules.learner import analyze_day
from claude_invest.modules.portfolio_tracker import get_allocation
from claude_invest.modules.strategy import load_lessons, build_strategy_brief
```

Add inside `create_app()`:
```python
    @app.get("/api/review-day")
    def api_review_day(date: str | None = None):
        db = get_db()
        report = analyze_day(db, date)
        db.close()
        return report

    @app.get("/api/allocation")
    def api_allocation():
        config = load_config()
        portfolio_data = get_portfolio()
        allocation = get_allocation(config, portfolio_data["positions"])
        return allocation

    @app.get("/api/lessons")
    def api_lessons():
        return load_lessons("lessons")

    @app.get("/api/strategy-brief")
    def api_strategy_brief():
        import os
        path = os.path.join("lessons", "strategy-brief.md")
        if os.path.exists(path):
            with open(path) as f:
                return {"brief": f.read()}
        return {"brief": "No strategy brief yet. Run review-day first."}
```

- [ ] **Step 2: Test endpoints**

```bash
# Start server
source .venv/bin/activate && .venv/bin/python -m claude_invest.modules.api_server &
sleep 2

# Test each endpoint
curl -s http://localhost:8000/api/allocation | python3 -m json.tool | head -20
curl -s http://localhost:8000/api/lessons | python3 -m json.tool | head -10
curl -s http://localhost:8000/api/strategy-brief | python3 -m json.tool
```

- [ ] **Step 3: Commit**

```bash
git add src/claude_invest/modules/api_server.py
git commit -m "feat: add API endpoints for allocation, lessons, and strategy brief"
```

---

### Task 7: Cron Prompt Update

**Files:**
- Modify: `.claude-plugin/skills/start-trading/prompts/market-hours.md`
- Modify: `.claude-plugin/skills/start-trading/prompts/after-hours.md`
- Modify: `.claude-plugin/skills/start-trading/prompts/crypto-overnight.md`

- [ ] **Step 1: Add strategy brief reading to all three prompts**

Add this block at the beginning of each prompt file (after the first line), before any trading instructions:

```markdown
## Strategy Brief

Before making any decisions, read the current strategy brief:
```bash
cat lessons/strategy-brief.md
```

Apply any RULES strictly — these are high-confidence patterns from past trades.
Consider OBSERVATIONS as guidance.
Check ALLOCATION ALERTS before opening new positions in overweight tiers.
```

- [ ] **Step 2: Commit**

```bash
git add .claude-plugin/skills/start-trading/prompts/
git commit -m "feat: add strategy brief reading to all trading cron prompts"
```

---

### Task 8: Review-Day Cron + /review-day Skill

**Files:**
- Create: `.claude-plugin/skills/review-day/SKILL.md`

- [ ] **Step 1: Create the review-day skill**

`.claude-plugin/skills/review-day/SKILL.md`:
```markdown
---
description: Run daily trading analysis — review wins/losses, score signal patterns, update strategy brief, check portfolio allocation
argument-hint: [date] (optional, defaults to today)
allowed-tools: Bash, CronCreate, Read
---

# Review Day

Run the daily trading analysis and learning cycle.

## Steps

### 1. Run the analysis
```bash
cd /Users/adewaleadeleye/projects/claude-invest
.venv/bin/python -m claude_invest.main review-day
```

### 2. Show the strategy brief
```bash
cat lessons/strategy-brief.md
```

### 3. Show allocation
```bash
.venv/bin/python -m claude_invest.main allocation
```

### 4. Present a summary to the user

Format the output as:
- Win/loss record and win rate
- Top performing signal patterns
- Mistakes to avoid
- Allocation status with drift alerts
- Strategy rules that were added or updated

Ask the user if they want to adjust any allocation targets or add manual sector overrides.
```

- [ ] **Step 2: Commit**

```bash
git add .claude-plugin/skills/review-day/
git commit -m "feat: add /review-day skill for daily trading analysis"
```

---

### Task 9: Integration Test

**Files:**
- Create: `tests/test_learning_integration.py`

- [ ] **Step 1: Write integration test**

`tests/test_learning_integration.py`:
```python
import json
import os
import pytest
from claude_invest.modules.db import Database
from claude_invest.modules.learner import analyze_day, score_patterns
from claude_invest.modules.portfolio_tracker import get_allocation
from claude_invest.modules.strategy import update_lessons, build_strategy_brief, load_lessons


def test_full_learning_pipeline(tmp_db_path, sample_config, tmp_path):
    config, _ = sample_config
    db = Database(tmp_db_path)
    db.initialize()
    lessons_dir = str(tmp_path / "lessons")
    os.makedirs(os.path.join(lessons_dir, "daily"), exist_ok=True)

    # Simulate trades
    db.insert_decision({
        "ticker": "AAPL", "action": "buy", "reasoning": "Strong signals",
        "signals_snapshot": json.dumps({"rsi": 45, "macd": 1, "macd_signal": 0, "trend": "bullish", "sentiment": 0.5, "price": 150}),
    })
    db.insert_decision({
        "ticker": "AAPL", "action": "sell", "reasoning": "Target hit",
        "signals_snapshot": json.dumps({"price": 160}),
    })
    db.insert_trade({"symbol": "AAPL", "side": "buy", "qty": 1, "price": 150, "order_id": "i1", "trade_type": "swing", "status": "filled"})
    db.insert_trade({"symbol": "AAPL", "side": "sell", "qty": 1, "price": 160, "order_id": "i2", "trade_type": "swing", "status": "filled"})

    # 1. Analyze
    report = analyze_day(db)
    assert report["wins"] >= 1
    assert report["total_pnl"] > 0

    # 2. Score patterns
    patterns = score_patterns(db)
    assert len(patterns) >= 1

    # 3. Update lessons
    update_lessons(lessons_dir, patterns, "2026-04-20")
    lessons = load_lessons(lessons_dir)
    assert len(lessons["patterns"]) >= 1

    # 4. Build strategy brief
    positions = [{"symbol": "AAPL", "market_value": 160, "avg_entry_price": 150, "current_price": 160, "qty": 1}]
    allocation = get_allocation(config, positions)
    brief = build_strategy_brief(lessons_dir, allocation)

    assert isinstance(brief, str)
    assert len(brief) > 50
    assert os.path.exists(os.path.join(lessons_dir, "strategy-brief.md"))
    assert os.path.exists(os.path.join(lessons_dir, "daily", "2026-04-20.md"))

    db.close()


def test_allocation_with_mixed_portfolio(sample_config):
    config, _ = sample_config
    positions = [
        {"symbol": "PFE", "market_value": 5300, "avg_entry_price": 26.52, "current_price": 27.56, "qty": 194},
        {"symbol": "SNDK", "market_value": 920, "avg_entry_price": 913, "current_price": 920, "qty": 1},
        {"symbol": "BTCUSD", "market_value": 99, "avg_entry_price": 75658, "current_price": 76000, "qty": 0.001},
        {"symbol": "ETHUSD", "market_value": 98, "avg_entry_price": 2337, "current_price": 2320, "qty": 0.042},
        {"symbol": "TRUMPUSD", "market_value": 100, "avg_entry_price": 2.84, "current_price": 2.90, "qty": 35},
    ]
    allocation = get_allocation(config, positions)

    # PFE = healthcare (neutral), SNDK = technology (neutral)
    # BTC/ETH = crypto (risk), TRUMP = meme (risk, via override)
    assert allocation["total_value"] == 6517
    assert allocation["tiers"]["neutral"]["actual"] > 0.5  # PFE + SNDK dominate
    assert allocation["tiers"]["risk"]["actual"] > 0  # crypto + meme
    assert allocation["tiers"]["safe"]["actual"] == 0  # no safe assets
    assert allocation["tiers"]["safe"]["alert"] is True  # 0% vs 30% target
```

- [ ] **Step 2: Run full test suite**

Run: `source .venv/bin/activate && .venv/bin/pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_learning_integration.py
git commit -m "feat: add integration tests for full learning pipeline"
```

---

### Task 10: First Live Run

- [ ] **Step 1: Run review-day on real data**

```bash
cd /Users/adewaleadeleye/projects/claude-invest
source .venv/bin/activate
.venv/bin/python -m claude_invest.main review-day
```

Expected: JSON output with patterns from our actual trading history (BTC, ETH, TRUMP, CMND, SNDK trades).

- [ ] **Step 2: Check the strategy brief**

```bash
cat lessons/strategy-brief.md
```

Expected: A strategy brief with rules/observations based on our real trades.

- [ ] **Step 3: Check allocation**

```bash
.venv/bin/python -m claude_invest.main allocation
```

Expected: Shows current portfolio allocation with drift alerts (we're heavy in neutral/healthcare from PFE, light on safe assets).

- [ ] **Step 4: Verify API endpoints**

```bash
curl -s http://localhost:8000/api/allocation | python3 -m json.tool | head -20
curl -s http://localhost:8000/api/strategy-brief | python3 -m json.tool
```

- [ ] **Step 5: Commit lessons files**

```bash
git add lessons/
git commit -m "chore: first learning analysis from live trading data"
```
