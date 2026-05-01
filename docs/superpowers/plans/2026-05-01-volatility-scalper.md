# Volatility Scalper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a volatility scalper strategy that catches high-ATR intraday moves via dip buying, rally shorting, and news reaction scalping with 15-minute bars.

**Architecture:** New `volatility_scanner.py` and `scalp_engine.py` modules. Updated `technicals.py` for 15-min bar support. New CLI commands and API endpoints. Plugs into existing trading cron.

**Tech Stack:** Python 3.12, SQLite3, FastAPI, Alpaca API

**Spec:** `docs/superpowers/specs/2026-05-01-volatility-scalper-design.md`

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `src/claude_invest/modules/volatility_scanner.py` | Scan and rank high-ATR candidates from curated watchlist + discovery |
| `src/claude_invest/modules/scalp_engine.py` | Entry logic (dip buying, rally shorting, news reaction) and exit checks |
| `tests/test_volatility_scanner.py` | Unit tests for scanner ranking, filtering, and discovery toggle |
| `tests/test_scalp_engine.py` | Unit tests for all trading modes, concurrency guard, and exit conditions |
| `tests/test_scalp_integration.py` | End-to-end cycle test with mocked Alpaca data |

### Modified Files
| File | Changes |
|------|---------|
| `src/claude_invest/config/settings.yaml` | Add `volatility_scalper` block; set `mean_reversion`, `trend_pullback`, `momentum` `capital_pct` to `0.25` |
| `src/claude_invest/modules/technicals.py` | Add `timeframe: str = "1Hour"` parameter to `analyze_technicals` and `_get_bars`; pass through to Alpaca request |
| `src/claude_invest/main.py` | Add `cmd_scalp_cycle`, `cmd_scalp_scan`, `cmd_scalp_status` functions; add three `elif` branches in CLI dispatch |
| `src/claude_invest/modules/api_server.py` | Add `GET /api/scalp/status` and `GET /api/scalp/candidates` endpoints inside `create_app` |

---

## Task 1: Update settings.yaml

**Files:**
- Modify: `src/claude_invest/config/settings.yaml`

- [ ] **Step 1: Write failing test for volatility_scalper config**

Create `tests/test_volatility_scalper_config.py`:

```python
import pytest
import yaml
from pathlib import Path


SETTINGS_PATH = Path("src/claude_invest/config/settings.yaml")


def load_settings():
    with open(SETTINGS_PATH) as f:
        return yaml.safe_load(f)


def test_volatility_scalper_block_present():
    config = load_settings()
    assert "volatility_scalper" in config


def test_volatility_scalper_capital_pct():
    config = load_settings()
    vs = config["volatility_scalper"]
    assert vs["capital_pct"] == 0.25


def test_volatility_scalper_modes_present():
    config = load_settings()
    modes = config["volatility_scalper"]["modes"]
    assert modes["dip_buying"] is True
    assert modes["rally_shorting"] is False
    assert modes["news_reaction"] is True


def test_volatility_scalper_watchlist():
    config = load_settings()
    wl = config["volatility_scalper"]["watchlist"]
    assert isinstance(wl, list)
    assert len(wl) >= 1


def test_volatility_scalper_params_complete():
    config = load_settings()
    params = config["volatility_scalper"]["params"]
    required = [
        "bar_timeframe", "dip_threshold", "rally_threshold",
        "rsi_period", "rsi_oversold", "rsi_overbought",
        "take_profit_pct", "stop_loss_pct", "max_hold_minutes",
        "force_exit_time", "max_concurrent",
    ]
    for key in required:
        assert key in params, f"Missing param: {key}"


def test_all_trading_strategies_at_0_25():
    config = load_settings()
    strategies = config["strategies"]
    for name in ["mean_reversion", "trend_pullback", "momentum"]:
        assert strategies[name]["capital_pct"] == 0.25, \
            f"{name} capital_pct should be 0.25 after adding volatility_scalper"
```

Run: `pytest tests/test_volatility_scalper_config.py -v` — all tests must fail.

- [ ] **Step 2: Update settings.yaml**

In `src/claude_invest/config/settings.yaml`:

1. Change `mean_reversion.capital_pct` from `0.33` to `0.25`
2. Change `trend_pullback.capital_pct` from `0.34` to `0.25`
3. Change `momentum.capital_pct` from `0.33` to `0.25`
4. Add the following block at the end of the `strategies` section (after `momentum`):

```yaml
  volatility_scalper:
    name: "Volatility Scalper"
    enabled: true
    capital_pct: 0.25
    modes:
      dip_buying: true
      rally_shorting: false
      news_reaction: true
    watchlist: [OKLO, RIVN, PLTR, IONQ, MARA]
    discovery:
      enabled: true
      min_atr_pct: 0.04
      lookback_days: 20
    params:
      bar_timeframe: "15Min"
      dip_threshold: -0.05
      rally_threshold: 0.05
      rsi_period: 14
      rsi_oversold: 30
      rsi_overbought: 75
      news_sentiment_buy: -0.3
      news_sentiment_short: 0.4
      news_min_articles: 3
      take_profit_pct: 0.03
      stop_loss_pct: 0.03
      max_hold_minutes: 120
      force_exit_time: "15:55"
      max_concurrent: 2
```

Also add `volatility_scalper` to `strategies.active`:

```yaml
strategies:
  active:
    - mean_reversion
    - trend_pullback
    - momentum
    - volatility_scalper
```

- [ ] **Step 3: Verify tests pass**

Run: `pytest tests/test_volatility_scalper_config.py -v` — all 6 tests must pass.

- [ ] **Step 4: Commit**

```bash
git add src/claude_invest/config/settings.yaml tests/test_volatility_scalper_config.py
git commit -m "feat: add volatility_scalper config and rebalance capital_pct to 0.25"
```

---

## Task 2: Update technicals.py — add timeframe parameter

**Files:**
- Modify: `src/claude_invest/modules/technicals.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_technicals.py` (or create if it does not exist):

```python
from unittest.mock import patch, MagicMock
import pandas as pd
import pytest
from claude_invest.modules.technicals import analyze_technicals, _get_bars


def _make_fake_df(n=60):
    """Return a minimal OHLCV DataFrame."""
    import numpy as np
    rng = pd.date_range("2026-01-01", periods=n, freq="1h")
    data = {
        "timestamp": rng,
        "open": np.linspace(10, 20, n),
        "high": np.linspace(10.5, 20.5, n),
        "low": np.linspace(9.5, 19.5, n),
        "close": np.linspace(10, 20, n),
        "volume": [100_000] * n,
    }
    return pd.DataFrame(data)


@patch("claude_invest.modules.technicals._get_bars")
def test_analyze_technicals_default_timeframe(mock_get_bars):
    mock_get_bars.return_value = _make_fake_df()
    result = analyze_technicals("AAPL")
    mock_get_bars.assert_called_once_with("AAPL", timeframe="1Hour")
    assert "rsi" in result
    assert result["ticker"] == "AAPL"


@patch("claude_invest.modules.technicals._get_bars")
def test_analyze_technicals_15min_timeframe(mock_get_bars):
    mock_get_bars.return_value = _make_fake_df()
    result = analyze_technicals("MARA", timeframe="15Min")
    mock_get_bars.assert_called_once_with("MARA", timeframe="15Min")
    assert result["ticker"] == "MARA"


@patch("claude_invest.modules.technicals.StockHistoricalDataClient")
def test_get_bars_passes_timeframe_to_alpaca(mock_client_cls):
    """_get_bars must map timeframe string to correct Alpaca TimeFrame object."""
    from alpaca.data.timeframe import TimeFrame
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    fake_bars = MagicMock()
    fake_bars.df = _make_fake_df().set_index("timestamp")
    mock_client.get_stock_bars.return_value = fake_bars

    _get_bars("MARA", timeframe="15Min")
    call_args = mock_client.get_stock_bars.call_args
    request = call_args[0][0]
    assert request.timeframe == TimeFrame.Minute * 15
```

Run: `pytest tests/test_technicals.py -v` — failing tests prove the feature is missing.

- [ ] **Step 2: Update technicals.py**

In `src/claude_invest/modules/technicals.py`:

1. Add `TimeFrame` minute constant import (already imported via `from alpaca.data.timeframe import TimeFrame`).
2. Add a helper to resolve timeframe string:

```python
_TIMEFRAME_MAP = {
    "1Hour": TimeFrame.Hour,
    "1Day": TimeFrame.Day,
    "15Min": TimeFrame.Minute * 15,
    "5Min": TimeFrame.Minute * 5,
    "1Min": TimeFrame.Minute,
}
```

3. Update `_get_bars` signature:

```python
def _get_bars(ticker: str, days: int = 60, timeframe: str = "1Hour") -> pd.DataFrame:
```

4. Inside `_get_bars`, replace the hardcoded `TimeFrame.Hour` with:

```python
tf = _TIMEFRAME_MAP.get(timeframe, TimeFrame.Hour)
```

Use `tf` in both the `StockBarsRequest` and `CryptoBarsRequest` calls (crypto keeps its own default).

5. Update `analyze_technicals` signature:

```python
def analyze_technicals(ticker: str, timeframe: str = "1Hour") -> dict:
```

6. Inside `analyze_technicals`, call:

```python
df = _get_bars(ticker, timeframe=timeframe)
```

No other callers need changes — the default `"1Hour"` preserves existing behavior.

- [ ] **Step 3: Verify tests pass**

Run: `pytest tests/test_technicals.py -v` — all new tests must pass; no existing tests broken.

- [ ] **Step 4: Commit**

```bash
git add src/claude_invest/modules/technicals.py tests/test_technicals.py
git commit -m "feat: add timeframe parameter to analyze_technicals and _get_bars"
```

---

## Task 3: Volatility scanner module

**Files:**
- Create: `src/claude_invest/modules/volatility_scanner.py`
- Create: `tests/test_volatility_scanner.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_volatility_scanner.py`:

```python
from unittest.mock import patch, MagicMock
import pytest
from claude_invest.modules.volatility_scanner import scan_volatile_stocks


SCALPER_CONFIG = {
    "volatility_scalper": {
        "watchlist": ["MARA", "IONQ", "RIVN"],
        "discovery": {
            "enabled": True,
            "min_atr_pct": 0.04,
            "lookback_days": 20,
        },
        "params": {
            "bar_timeframe": "15Min",
        },
    }
}


def _mock_stock_data(ticker, atr_pct=0.05, intraday_change=-0.06, volume_ratio=2.0):
    return {
        "ticker": ticker,
        "atr_pct": atr_pct,
        "intraday_change": intraday_change,
        "volume_ratio": volume_ratio,
    }


@patch("claude_invest.modules.volatility_scanner._fetch_stock_metrics")
def test_scan_returns_list(mock_fetch):
    mock_fetch.side_effect = lambda ticker, cfg: _mock_stock_data(ticker)
    result = scan_volatile_stocks(SCALPER_CONFIG)
    assert isinstance(result, list)
    assert len(result) > 0


@patch("claude_invest.modules.volatility_scanner._fetch_stock_metrics")
def test_each_result_has_required_keys(mock_fetch):
    mock_fetch.side_effect = lambda ticker, cfg: _mock_stock_data(ticker)
    result = scan_volatile_stocks(SCALPER_CONFIG)
    required = {"ticker", "atr_pct", "intraday_change", "volume_ratio", "source", "rank"}
    for item in result:
        assert required <= set(item.keys()), f"Missing keys in {item}"


@patch("claude_invest.modules.volatility_scanner._fetch_stock_metrics")
def test_curated_tickers_present(mock_fetch):
    mock_fetch.side_effect = lambda ticker, cfg: _mock_stock_data(ticker)
    result = scan_volatile_stocks(SCALPER_CONFIG)
    tickers = [r["ticker"] for r in result]
    for t in ["MARA", "IONQ", "RIVN"]:
        assert t in tickers


@patch("claude_invest.modules.volatility_scanner._fetch_stock_metrics")
def test_curated_tickers_ranked_first(mock_fetch):
    """Curated tickers must appear before discovered ones regardless of score."""
    def side_effect(ticker, cfg):
        # Give discovered ticker a higher raw score than curated
        if ticker == "SOUN":
            return _mock_stock_data(ticker, atr_pct=0.99, intraday_change=-0.99, volume_ratio=9.9)
        return _mock_stock_data(ticker, atr_pct=0.05)
    mock_fetch.side_effect = side_effect

    config = {
        "volatility_scalper": {
            "watchlist": ["MARA"],
            "discovery": {"enabled": True, "min_atr_pct": 0.04, "lookback_days": 20},
            "params": {"bar_timeframe": "15Min"},
        }
    }

    with patch("claude_invest.modules.volatility_scanner._discover_volatile_stocks",
               return_value=["SOUN"]):
        result = scan_volatile_stocks(config)

    curated_positions = [i for i, r in enumerate(result) if r["source"] == "curated"]
    discovered_positions = [i for i, r in enumerate(result) if r["source"] == "discovered"]
    if curated_positions and discovered_positions:
        assert max(curated_positions) < min(discovered_positions)


@patch("claude_invest.modules.volatility_scanner._fetch_stock_metrics")
@patch("claude_invest.modules.volatility_scanner._discover_volatile_stocks")
def test_discovery_disabled_returns_only_curated(mock_discover, mock_fetch):
    mock_fetch.side_effect = lambda ticker, cfg: _mock_stock_data(ticker)
    config = {
        "volatility_scalper": {
            "watchlist": ["MARA", "IONQ"],
            "discovery": {"enabled": False, "min_atr_pct": 0.04, "lookback_days": 20},
            "params": {"bar_timeframe": "15Min"},
        }
    }
    result = scan_volatile_stocks(config)
    mock_discover.assert_not_called()
    assert all(r["source"] == "curated" for r in result)


@patch("claude_invest.modules.volatility_scanner._fetch_stock_metrics")
def test_low_atr_stocks_excluded_from_discovery(mock_fetch):
    """Stocks below min_atr_pct must be filtered out of discovered results."""
    def side_effect(ticker, cfg):
        if ticker == "LOW_ATR":
            return _mock_stock_data(ticker, atr_pct=0.01)  # below 0.04 threshold
        return _mock_stock_data(ticker, atr_pct=0.06)
    mock_fetch.side_effect = side_effect

    config = {
        "volatility_scalper": {
            "watchlist": ["MARA"],
            "discovery": {"enabled": True, "min_atr_pct": 0.04, "lookback_days": 20},
            "params": {"bar_timeframe": "15Min"},
        }
    }
    with patch("claude_invest.modules.volatility_scanner._discover_volatile_stocks",
               return_value=["LOW_ATR", "HIGH_ATR"]):
        result = scan_volatile_stocks(config)
    tickers = [r["ticker"] for r in result]
    assert "LOW_ATR" not in tickers


@patch("claude_invest.modules.volatility_scanner._fetch_stock_metrics")
def test_results_are_ranked_ascending(mock_fetch):
    mock_fetch.side_effect = lambda ticker, cfg: _mock_stock_data(ticker)
    result = scan_volatile_stocks(SCALPER_CONFIG)
    ranks = [r["rank"] for r in result]
    assert ranks == list(range(1, len(ranks) + 1))
```

Run: `pytest tests/test_volatility_scanner.py -v` — all tests fail (module does not exist yet).

- [ ] **Step 2: Create volatility_scanner.py**

Create `src/claude_invest/modules/volatility_scanner.py`:

```python
"""
Volatility Scanner — ranks high-ATR stock candidates for the scalp engine.

Public API:
    scan_volatile_stocks(config: dict) -> list[dict]
"""

import os
from datetime import datetime, timedelta, timezone

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame
from dotenv import load_dotenv

load_dotenv()


def _get_alpaca_client() -> StockHistoricalDataClient:
    return StockHistoricalDataClient(
        os.environ["ALPACA_API_KEY"],
        os.environ["ALPACA_SECRET_KEY"],
    )


def _compute_atr_pct(ticker: str, lookback_days: int, client: StockHistoricalDataClient) -> float:
    """Return ATR as a fraction of price over lookback_days daily bars."""
    start = datetime.now(timezone.utc) - timedelta(days=lookback_days + 5)
    req = StockBarsRequest(symbol_or_symbols=ticker, timeframe=TimeFrame.Day, start=start)
    bars = client.get_stock_bars(req).df.reset_index()
    bars.columns = [c.lower() for c in bars.columns]
    if len(bars) < 2:
        return 0.0
    tr = (bars["high"] - bars["low"]).abs()
    atr = tr.rolling(min(14, len(tr))).mean().iloc[-1]
    price = float(bars["close"].iloc[-1])
    return float(atr / price) if price else 0.0


def _compute_volume_ratio(ticker: str, lookback_days: int, client: StockHistoricalDataClient) -> float:
    """Return today's volume divided by the 20-day average daily volume."""
    start = datetime.now(timezone.utc) - timedelta(days=lookback_days + 5)
    req = StockBarsRequest(symbol_or_symbols=ticker, timeframe=TimeFrame.Day, start=start)
    bars = client.get_stock_bars(req).df.reset_index()
    bars.columns = [c.lower() for c in bars.columns]
    if len(bars) < 2:
        return 1.0
    avg_volume = float(bars["volume"].iloc[:-1].mean())
    today_volume = float(bars["volume"].iloc[-1])
    return round(today_volume / avg_volume, 2) if avg_volume else 1.0


def _compute_intraday_change(ticker: str, client: StockHistoricalDataClient) -> float:
    """Return % change from yesterday's close to today's latest trade."""
    start = datetime.now(timezone.utc) - timedelta(days=5)
    req = StockBarsRequest(symbol_or_symbols=ticker, timeframe=TimeFrame.Day, start=start)
    bars = client.get_stock_bars(req).df.reset_index()
    bars.columns = [c.lower() for c in bars.columns]
    if len(bars) < 2:
        return 0.0
    prev_close = float(bars["close"].iloc[-2])
    latest_close = float(bars["close"].iloc[-1])
    return round((latest_close - prev_close) / prev_close, 4) if prev_close else 0.0


def _fetch_stock_metrics(ticker: str, scalper_config: dict) -> dict:
    """Fetch ATR%, intraday change, and volume ratio for a single ticker."""
    client = _get_alpaca_client()
    lookback = scalper_config.get("discovery", {}).get("lookback_days", 20)
    atr_pct = _compute_atr_pct(ticker, lookback, client)
    intraday_change = _compute_intraday_change(ticker, client)
    volume_ratio = _compute_volume_ratio(ticker, lookback, client)
    return {
        "ticker": ticker,
        "atr_pct": round(atr_pct, 4),
        "intraday_change": intraday_change,
        "volume_ratio": volume_ratio,
    }


def _score(metrics: dict) -> float:
    """Composite score: (atr_pct * 0.5) + (abs(intraday_change) * 0.3) + (volume_ratio * 0.2)."""
    return (
        metrics["atr_pct"] * 0.5
        + abs(metrics["intraday_change"]) * 0.3
        + metrics["volume_ratio"] * 0.2
    )


def _discover_volatile_stocks(scalper_config: dict) -> list[str]:
    """
    Return a list of ticker symbols discovered via a broad scan.

    Currently returns an empty list — discovery via pre-defined broader universe
    can be wired in here. The interface is extracted so it can be mocked in tests.
    """
    # Future: query Alpaca screener / pre-defined universe and filter by ATR%.
    return []


def scan_volatile_stocks(config: dict) -> list[dict]:
    """
    Return a ranked list of volatile stock candidates.

    Args:
        config: full settings dict (reads from config["volatility_scalper"])

    Returns:
        List of dicts with keys: ticker, atr_pct, intraday_change,
        volume_ratio, source ("curated" | "discovered"), rank (1-indexed).
    """
    scalper_cfg = config.get("volatility_scalper", {})
    discovery_cfg = scalper_cfg.get("discovery", {})
    min_atr_pct = discovery_cfg.get("min_atr_pct", 0.04)
    discovery_enabled = discovery_cfg.get("enabled", False)

    curated_tickers: list[str] = scalper_cfg.get("watchlist", [])
    discovered_tickers: list[str] = (
        _discover_volatile_stocks(scalper_cfg) if discovery_enabled else []
    )

    # Remove duplicates: curated takes priority
    all_tickers = list(curated_tickers) + [
        t for t in discovered_tickers if t not in curated_tickers
    ]

    candidates: list[dict] = []
    for ticker in all_tickers:
        metrics = _fetch_stock_metrics(ticker, scalper_cfg)
        source = "curated" if ticker in curated_tickers else "discovered"

        # Filter discovered tickers below ATR threshold; always include curated
        if source == "discovered" and metrics["atr_pct"] < min_atr_pct:
            continue

        candidates.append({**metrics, "source": source})

    # Sort: curated first (preserving score order within curated), then discovered by score
    curated_sorted = sorted(
        [c for c in candidates if c["source"] == "curated"],
        key=_score,
        reverse=True,
    )
    discovered_sorted = sorted(
        [c for c in candidates if c["source"] == "discovered"],
        key=_score,
        reverse=True,
    )

    ranked = curated_sorted + discovered_sorted
    for i, item in enumerate(ranked, start=1):
        item["rank"] = i

    return ranked
```

- [ ] **Step 3: Verify tests pass**

Run: `pytest tests/test_volatility_scanner.py -v` — all 7 tests must pass.

- [ ] **Step 4: Commit**

```bash
git add src/claude_invest/modules/volatility_scanner.py tests/test_volatility_scanner.py
git commit -m "feat: add volatility_scanner module with scan_volatile_stocks"
```

---

## Task 4: Scalp engine module

**Files:**
- Create: `src/claude_invest/modules/scalp_engine.py`
- Create: `tests/test_scalp_engine.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_scalp_engine.py`:

```python
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest

from claude_invest.modules.scalp_engine import run_scalp_cycle, check_scalp_exits


BASE_CONFIG = {
    "capital": 5000,
    "capital_split": {"trading": 0.5, "core": 0.5},
    "volatility_scalper": {
        "enabled": True,
        "capital_pct": 0.25,
        "modes": {
            "dip_buying": True,
            "rally_shorting": False,
            "news_reaction": False,
        },
        "watchlist": ["MARA"],
        "discovery": {"enabled": False, "min_atr_pct": 0.04, "lookback_days": 20},
        "params": {
            "bar_timeframe": "15Min",
            "dip_threshold": -0.05,
            "rally_threshold": 0.05,
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 75,
            "news_sentiment_buy": -0.3,
            "news_sentiment_short": 0.4,
            "news_min_articles": 3,
            "take_profit_pct": 0.03,
            "stop_loss_pct": 0.03,
            "max_hold_minutes": 120,
            "force_exit_time": "15:55",
            "max_concurrent": 2,
        },
    },
}


def _make_db(open_positions=None):
    """Create a mock Database with configurable open scalp positions."""
    db = MagicMock()
    db.get_open_positions_by_strategy.return_value = open_positions or []
    db.record_trade.return_value = None
    return db


# ── run_scalp_cycle ─────────────────────────────────────────────────────────

@patch("claude_invest.modules.scalp_engine.scan_volatile_stocks")
@patch("claude_invest.modules.scalp_engine.analyze_technicals")
@patch("claude_invest.modules.scalp_engine.execute_order")
def test_run_scalp_cycle_returns_summary(mock_exec, mock_tech, mock_scan):
    mock_scan.return_value = [
        {"ticker": "MARA", "atr_pct": 0.07, "intraday_change": -0.06,
         "volume_ratio": 2.4, "source": "curated", "rank": 1}
    ]
    mock_tech.return_value = {
        "ticker": "MARA", "rsi": 25.0, "current_price": 18.0,
        "macd": 0.0, "macd_signal": 0.0, "sma_20": 17.0, "sma_50": 16.0, "trend": "neutral"
    }
    mock_exec.return_value = {"status": "filled", "filled_qty": 5, "filled_avg_price": 18.0}

    db = _make_db()
    result = run_scalp_cycle(BASE_CONFIG, db)

    assert "scanned" in result
    assert "signals_found" in result
    assert "trades_placed" in result
    assert "skipped_reason" in result
    assert isinstance(result["skipped_reason"], list)


@patch("claude_invest.modules.scalp_engine.scan_volatile_stocks")
@patch("claude_invest.modules.scalp_engine.analyze_technicals")
@patch("claude_invest.modules.scalp_engine.execute_order")
def test_dip_buying_entry_fires_when_conditions_met(mock_exec, mock_tech, mock_scan):
    """RSI < 30 + intraday change < -5% triggers a buy."""
    mock_scan.return_value = [
        {"ticker": "MARA", "atr_pct": 0.07, "intraday_change": -0.07,
         "volume_ratio": 2.4, "source": "curated", "rank": 1}
    ]
    mock_tech.return_value = {
        "ticker": "MARA", "rsi": 25.0, "current_price": 18.0,
        "macd": 0.0, "macd_signal": 0.0, "sma_20": 17.0, "sma_50": 16.0, "trend": "neutral"
    }
    mock_exec.return_value = {"status": "filled", "filled_qty": 5, "filled_avg_price": 18.0}

    db = _make_db()
    result = run_scalp_cycle(BASE_CONFIG, db)

    assert result["trades_placed"] >= 1
    mock_exec.assert_called_once()


@patch("claude_invest.modules.scalp_engine.scan_volatile_stocks")
@patch("claude_invest.modules.scalp_engine.analyze_technicals")
@patch("claude_invest.modules.scalp_engine.execute_order")
def test_rally_shorting_disabled_produces_no_shorts(mock_exec, mock_tech, mock_scan):
    """rally_shorting: false — no short orders even when RSI > 75 + rally > 5%."""
    mock_scan.return_value = [
        {"ticker": "MARA", "atr_pct": 0.07, "intraday_change": 0.08,
         "volume_ratio": 2.4, "source": "curated", "rank": 1}
    ]
    mock_tech.return_value = {
        "ticker": "MARA", "rsi": 80.0, "current_price": 20.0,
        "macd": 0.0, "macd_signal": 0.0, "sma_20": 19.0, "sma_50": 18.0, "trend": "bullish"
    }

    db = _make_db()
    result = run_scalp_cycle(BASE_CONFIG, db)

    assert result["trades_placed"] == 0
    mock_exec.assert_not_called()


@patch("claude_invest.modules.scalp_engine.scan_volatile_stocks")
@patch("claude_invest.modules.scalp_engine.analyze_technicals")
@patch("claude_invest.modules.scalp_engine.execute_order")
def test_max_concurrent_guard_blocks_new_entry(mock_exec, mock_tech, mock_scan):
    """When 2 open scalp positions exist, no new trades are placed."""
    mock_scan.return_value = [
        {"ticker": "MARA", "atr_pct": 0.07, "intraday_change": -0.07,
         "volume_ratio": 2.4, "source": "curated", "rank": 1}
    ]
    mock_tech.return_value = {
        "ticker": "MARA", "rsi": 25.0, "current_price": 18.0,
        "macd": 0.0, "macd_signal": 0.0, "sma_20": 17.0, "sma_50": 16.0, "trend": "neutral"
    }
    # Already at the max_concurrent limit (2 open positions)
    db = _make_db(open_positions=[{"ticker": "IONQ"}, {"ticker": "RIVN"}])
    result = run_scalp_cycle(BASE_CONFIG, db)

    assert result["trades_placed"] == 0
    mock_exec.assert_not_called()
    assert any("max_concurrent" in r for r in result["skipped_reason"])


# ── check_scalp_exits ────────────────────────────────────────────────────────

def _make_position(ticker="MARA", entry_price=18.0, current_price=18.0,
                   side="long", shares=100, age_minutes=10,
                   entry_mode="dip_buying"):
    entry_time = datetime.now(timezone.utc) - timedelta(minutes=age_minutes)
    return {
        "ticker": ticker,
        "side": side,
        "shares": shares,
        "entry_price": entry_price,
        "current_price": current_price,
        "entry_time": entry_time.isoformat(),
        "entry_mode": entry_mode,
        "strategy_id": "volatility_scalper",
    }


@patch("claude_invest.modules.scalp_engine.get_current_price")
@patch("claude_invest.modules.scalp_engine.execute_order")
def test_take_profit_triggers_at_3_pct(mock_exec, mock_price):
    mock_exec.return_value = {"status": "filled"}
    mock_price.return_value = 18.55  # +3.06% above 18.0

    db = _make_db()
    db.get_open_positions_by_strategy.return_value = [_make_position(entry_price=18.0)]

    closed = check_scalp_exits(BASE_CONFIG, db)

    assert len(closed) == 1
    assert closed[0]["exit_reason"] == "take_profit"
    assert closed[0]["pnl_pct"] > 0


@patch("claude_invest.modules.scalp_engine.get_current_price")
@patch("claude_invest.modules.scalp_engine.execute_order")
def test_stop_loss_triggers_at_minus_3_pct(mock_exec, mock_price):
    mock_exec.return_value = {"status": "filled"}
    mock_price.return_value = 17.45  # -3.06% below 18.0

    db = _make_db()
    db.get_open_positions_by_strategy.return_value = [_make_position(entry_price=18.0)]

    closed = check_scalp_exits(BASE_CONFIG, db)

    assert len(closed) == 1
    assert closed[0]["exit_reason"] == "stop_loss"
    assert closed[0]["pnl_pct"] < 0


@patch("claude_invest.modules.scalp_engine.get_current_price")
@patch("claude_invest.modules.scalp_engine.execute_order")
def test_max_hold_triggers_after_120_minutes(mock_exec, mock_price):
    mock_exec.return_value = {"status": "filled"}
    mock_price.return_value = 18.10  # no TP/SL

    db = _make_db()
    db.get_open_positions_by_strategy.return_value = [
        _make_position(entry_price=18.0, age_minutes=130)
    ]

    closed = check_scalp_exits(BASE_CONFIG, db)

    assert len(closed) == 1
    assert closed[0]["exit_reason"] == "max_hold"


@patch("claude_invest.modules.scalp_engine.get_current_price")
@patch("claude_invest.modules.scalp_engine.execute_order")
@patch("claude_invest.modules.scalp_engine._current_et_time")
def test_force_exit_closes_all_at_1555(mock_time, mock_exec, mock_price):
    """At or after 15:55 ET all scalp positions are closed regardless of P&L."""
    mock_time.return_value = datetime(2026, 5, 1, 15, 56, tzinfo=timezone.utc)
    mock_exec.return_value = {"status": "filled"}
    mock_price.return_value = 18.10

    db = _make_db()
    db.get_open_positions_by_strategy.return_value = [
        _make_position(ticker="MARA"),
        _make_position(ticker="IONQ"),
    ]

    closed = check_scalp_exits(BASE_CONFIG, db)

    assert len(closed) == 2
    assert all(c["exit_reason"] == "force_exit" for c in closed)
```

Run: `pytest tests/test_scalp_engine.py -v` — all tests fail.

- [ ] **Step 2: Create scalp_engine.py**

Create `src/claude_invest/modules/scalp_engine.py`:

```python
"""
Scalp Engine — entry and exit logic for the Volatility Scalper strategy.

Public API:
    run_scalp_cycle(config: dict, db) -> dict
    check_scalp_exits(config: dict, db) -> list[dict]
"""

import uuid
from datetime import datetime, timezone, timedelta

from claude_invest.modules.technicals import analyze_technicals
from claude_invest.modules.executor import execute_order
from claude_invest.modules.volatility_scanner import scan_volatile_stocks

STRATEGY_ID = "volatility_scalper"


def _current_et_time() -> datetime:
    """Return current UTC time (stub target for test mocking of force-exit clock)."""
    return datetime.now(timezone.utc)


def get_current_price(ticker: str) -> float:
    """Fetch the latest price for a ticker via Alpaca snapshot."""
    import os
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest
    from dotenv import load_dotenv
    load_dotenv()
    client = StockHistoricalDataClient(
        os.environ["ALPACA_API_KEY"],
        os.environ["ALPACA_SECRET_KEY"],
    )
    req = StockLatestQuoteRequest(symbol_or_symbols=ticker)
    quote = client.get_stock_latest_quote(req)
    return float(quote[ticker].ask_price or quote[ticker].bid_price)


def _calculate_shares(config: dict, price: float) -> int:
    """Return whole-share count based on volatility_scalper capital allocation."""
    total_capital = config.get("capital", 5000)
    trading_pct = config.get("capital_split", {}).get("trading", 0.5)
    scalper_pct = config["volatility_scalper"]["capital_pct"]
    max_concurrent = config["volatility_scalper"]["params"]["max_concurrent"]
    per_trade_capital = (total_capital * trading_pct * scalper_pct) / max_concurrent
    return max(1, int(per_trade_capital / price))


def _check_dip_buy_signal(metrics: dict, technicals: dict, params: dict) -> bool:
    intraday_change = metrics.get("intraday_change", 0)
    rsi = technicals.get("rsi") or 100
    return (
        intraday_change <= params["dip_threshold"]
        and rsi < params["rsi_oversold"]
    )


def _check_rally_short_signal(metrics: dict, technicals: dict, params: dict) -> bool:
    intraday_change = metrics.get("intraday_change", 0)
    rsi = technicals.get("rsi") or 0
    return (
        intraday_change >= params["rally_threshold"]
        and rsi > params["rsi_overbought"]
    )


def run_scalp_cycle(config: dict, db) -> dict:
    """
    Run one full scalp cycle: scan candidates, evaluate setups, place trades.

    Returns:
        dict with keys: scanned, signals_found, trades_placed, skipped_reason
    """
    scalper_cfg = config["volatility_scalper"]
    params = scalper_cfg["params"]
    modes = scalper_cfg.get("modes", {})
    max_concurrent = params["max_concurrent"]

    summary = {
        "scanned": 0,
        "signals_found": 0,
        "trades_placed": 0,
        "skipped_reason": [],
    }

    candidates = scan_volatile_stocks(config)
    summary["scanned"] = len(candidates)

    # Count existing open scalp positions
    open_positions = db.get_open_positions_by_strategy(STRATEGY_ID)
    open_tickers = {p["ticker"] for p in open_positions}

    for candidate in candidates:
        ticker = candidate["ticker"]

        # Concurrency guard
        if len(open_positions) >= max_concurrent:
            summary["skipped_reason"].append(
                f"{ticker}: max_concurrent ({max_concurrent}) reached"
            )
            continue

        # Already holding this ticker
        if ticker in open_tickers:
            summary["skipped_reason"].append(f"{ticker}: already holding position")
            continue

        technicals = analyze_technicals(ticker, timeframe=params["bar_timeframe"])

        signal = None
        side = None

        if modes.get("dip_buying") and _check_dip_buy_signal(candidate, technicals, params):
            signal = "dip_buying"
            side = "buy"
        elif modes.get("rally_shorting") and _check_rally_short_signal(candidate, technicals, params):
            signal = "rally_shorting"
            side = "sell_short"

        if not signal:
            summary["skipped_reason"].append(f"{ticker}: no signal")
            continue

        summary["signals_found"] += 1
        price = technicals["current_price"]
        shares = _calculate_shares(config, price)

        order_result = execute_order(ticker, side, shares)
        if order_result.get("status") == "filled":
            db.record_trade({
                "id": str(uuid.uuid4()),
                "ticker": ticker,
                "action": side,
                "shares": shares,
                "price": order_result.get("filled_avg_price", price),
                "strategy_id": STRATEGY_ID,
                "entry_mode": signal,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            open_positions.append({"ticker": ticker})
            open_tickers.add(ticker)
            summary["trades_placed"] += 1

    return summary


def check_scalp_exits(config: dict, db) -> list[dict]:
    """
    Check all open scalp positions for exit conditions.

    Priority order: force_exit > take_profit > stop_loss > max_hold

    Returns:
        List of dicts with: ticker, exit_reason, pnl_pct
    """
    params = config["volatility_scalper"]["params"]
    take_profit_pct = params["take_profit_pct"]
    stop_loss_pct = params["stop_loss_pct"]
    max_hold_minutes = params["max_hold_minutes"]
    force_exit_time_str = params["force_exit_time"]  # "15:55"
    force_hour, force_minute = map(int, force_exit_time_str.split(":"))

    now = _current_et_time()
    force_exit = now.hour > force_hour or (now.hour == force_hour and now.minute >= force_minute)

    open_positions = db.get_open_positions_by_strategy(STRATEGY_ID)
    closed = []

    for position in open_positions:
        ticker = position["ticker"]
        entry_price = position["entry_price"]
        side = position.get("side", "long")
        shares = position.get("shares", 0)
        entry_time = datetime.fromisoformat(position["entry_time"])

        current_price = get_current_price(ticker)
        if side == "long":
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - current_price) / entry_price

        age_minutes = (now - entry_time).total_seconds() / 60

        exit_reason = None

        if force_exit:
            exit_reason = "force_exit"
        elif pnl_pct >= take_profit_pct:
            exit_reason = "take_profit"
        elif pnl_pct <= -stop_loss_pct:
            exit_reason = "stop_loss"
        elif age_minutes >= max_hold_minutes:
            exit_reason = "max_hold"

        if exit_reason:
            close_side = "sell" if side == "long" else "buy_to_cover"
            execute_order(ticker, close_side, shares)
            db.close_position(ticker, STRATEGY_ID, exit_reason)
            closed.append({
                "ticker": ticker,
                "exit_reason": exit_reason,
                "pnl_pct": round(pnl_pct, 4),
            })

    return closed
```

- [ ] **Step 3: Verify tests pass**

Run: `pytest tests/test_scalp_engine.py -v` — all 9 tests must pass.

- [ ] **Step 4: Commit**

```bash
git add src/claude_invest/modules/scalp_engine.py tests/test_scalp_engine.py
git commit -m "feat: add scalp_engine module with run_scalp_cycle and check_scalp_exits"
```

---

## Task 5: CLI commands + API endpoints

**Files:**
- Modify: `src/claude_invest/main.py`
- Modify: `src/claude_invest/modules/api_server.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_scalp_cli_api.py`:

```python
"""Tests for scalp CLI commands and API endpoints."""
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from claude_invest.modules.api_server import create_app


@pytest.fixture
def client(tmp_db_path):
    app = create_app(db_path=tmp_db_path)
    return TestClient(app)


# ── API endpoint tests ───────────────────────────────────────────────────────

@patch("claude_invest.modules.api_server.scan_volatile_stocks")
@patch("claude_invest.modules.api_server.load_config")
def test_scalp_candidates_endpoint(mock_config, mock_scan, client):
    mock_config.return_value = {
        "volatility_scalper": {
            "watchlist": ["MARA"],
            "discovery": {"enabled": False, "min_atr_pct": 0.04, "lookback_days": 20},
            "params": {"bar_timeframe": "15Min"},
        }
    }
    mock_scan.return_value = [
        {"ticker": "MARA", "atr_pct": 0.072, "intraday_change": -0.061,
         "volume_ratio": 2.4, "source": "curated", "rank": 1}
    ]
    response = client.get("/api/scalp/candidates")
    assert response.status_code == 200
    data = response.json()
    assert "candidates" in data
    assert "scanned_at" in data
    assert data["candidates"][0]["ticker"] == "MARA"


def test_scalp_status_endpoint_returns_positions(client, tmp_db_path):
    from claude_invest.modules.db import Database
    db = Database(tmp_db_path)
    db.initialize()
    db.close()

    response = client.get("/api/scalp/status")
    assert response.status_code == 200
    data = response.json()
    assert "positions" in data
    assert "count" in data
    assert "max_concurrent" in data


# ── CLI command tests (smoke tests via subprocess) ───────────────────────────

def test_scalp_scan_command_exists():
    """Verify scalp-scan is wired into main.py dispatch."""
    import subprocess
    result = subprocess.run(
        ["python", "-m", "claude_invest.main", "scalp-scan"],
        capture_output=True, text=True,
        env={**__import__("os").environ,
             "ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"},
    )
    # Should not error with "Unknown command"
    assert "Unknown command" not in result.stdout
    assert "Unknown command" not in result.stderr
```

Run: `pytest tests/test_scalp_cli_api.py -v` — tests fail because endpoints/commands don't exist.

- [ ] **Step 2: Add CLI commands to main.py**

In `src/claude_invest/main.py`:

1. Add imports at the top (with other module imports):

```python
from claude_invest.modules.volatility_scanner import scan_volatile_stocks
from claude_invest.modules.scalp_engine import run_scalp_cycle, check_scalp_exits
```

2. Add three command functions (place them near the other `cmd_*` functions):

```python
def cmd_scalp_scan():
    config = load_config()
    candidates = scan_volatile_stocks(config)
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M ET")
    print(f"\nVolatile Candidates ({now})")
    print("=" * 42)
    for c in candidates:
        tag = c.get("source", "?")
        sign = "+" if c["intraday_change"] >= 0 else ""
        print(
            f" {c['rank']:2}. {c['ticker']:<6} "
            f"ATR: {c['atr_pct']*100:.1f}%  "
            f"Change: {sign}{c['intraday_change']*100:.1f}%  "
            f"Vol/Avg: {c['volume_ratio']:.1f}x  [{tag}]"
        )


def cmd_scalp_cycle():
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    result = run_scalp_cycle(config, db)
    db.close()
    _output(result)


def cmd_scalp_status():
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    positions = db.get_open_positions_by_strategy("volatility_scalper")
    db.close()
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M ET")
    print(f"\nOpen Scalp Positions ({now})")
    print("=" * 43)
    if not positions:
        print("  No open scalp positions.")
        return
    for p in positions:
        side = p.get("side", "BUY").upper()
        shares = p.get("shares", 0)
        entry = p.get("entry_price", 0)
        current = p.get("current_price", entry)
        pnl = (current - entry) / entry * 100 if entry else 0
        age = p.get("age_minutes", "?")
        sign = "+" if pnl >= 0 else ""
        print(
            f" {p['ticker']:<6} {side}  {shares:>4} shares  "
            f"Entry: ${entry:.2f}  Current: ${current:.2f}  "
            f"P&L: {sign}{pnl:.1f}%  Age: {age}min"
        )
```

3. Add dispatch branches inside the `if __name__ == "__main__":` block, after `core-rebalance`:

```python
    elif command == "scalp-cycle":
        cmd_scalp_cycle()
    elif command == "scalp-scan":
        cmd_scalp_scan()
    elif command == "scalp-status":
        cmd_scalp_status()
```

- [ ] **Step 3: Add API endpoints to api_server.py**

In `src/claude_invest/modules/api_server.py`:

1. Add imports at the top (with other module imports):

```python
from claude_invest.modules.volatility_scanner import scan_volatile_stocks
```

2. Add two endpoints inside `create_app`, before `return app`:

```python
    @app.get("/api/scalp/candidates")
    def api_scalp_candidates():
        config = load_config()
        candidates = scan_volatile_stocks(config)
        from datetime import datetime, timezone
        return {
            "candidates": candidates,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/api/scalp/status")
    def api_scalp_status():
        config = load_config()
        db = get_db()
        positions = db.get_open_positions_by_strategy("volatility_scalper")
        db.close()
        max_concurrent = (
            config.get("volatility_scalper", {})
            .get("params", {})
            .get("max_concurrent", 2)
        )
        return {
            "positions": positions,
            "count": len(positions),
            "max_concurrent": max_concurrent,
        }
```

- [ ] **Step 4: Verify tests pass**

Run: `pytest tests/test_scalp_cli_api.py -v` — all 3 tests must pass.

- [ ] **Step 5: Commit**

```bash
git add src/claude_invest/main.py src/claude_invest/modules/api_server.py tests/test_scalp_cli_api.py
git commit -m "feat: add scalp CLI commands (scalp-cycle, scalp-scan, scalp-status) and API endpoints"
```

---

## Task 6: Integration test

**Files:**
- Create: `tests/test_scalp_integration.py`

- [ ] **Step 1: Write the integration test**

Create `tests/test_scalp_integration.py`:

```python
"""
Integration test: full scalp cycle from scan through entry to exit, with mocked Alpaca.

Verifies:
  - scan_volatile_stocks -> run_scalp_cycle -> check_scalp_exits flows correctly
  - Trade is recorded in the DB with strategy_id = "volatility_scalper"
  - Learning engine can query trades by strategy_id
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest

from claude_invest.modules.db import Database
from claude_invest.modules.volatility_scanner import scan_volatile_stocks
from claude_invest.modules.scalp_engine import run_scalp_cycle, check_scalp_exits


INTEGRATION_CONFIG = {
    "capital": 5000,
    "capital_split": {"trading": 0.5, "core": 0.5},
    "volatility_scalper": {
        "enabled": True,
        "capital_pct": 0.25,
        "modes": {
            "dip_buying": True,
            "rally_shorting": False,
            "news_reaction": False,
        },
        "watchlist": ["MARA"],
        "discovery": {"enabled": False, "min_atr_pct": 0.04, "lookback_days": 20},
        "params": {
            "bar_timeframe": "15Min",
            "dip_threshold": -0.05,
            "rally_threshold": 0.05,
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 75,
            "news_sentiment_buy": -0.3,
            "news_sentiment_short": 0.4,
            "news_min_articles": 3,
            "take_profit_pct": 0.03,
            "stop_loss_pct": 0.03,
            "max_hold_minutes": 120,
            "force_exit_time": "15:55",
            "max_concurrent": 2,
        },
    },
}


@patch("claude_invest.modules.volatility_scanner._fetch_stock_metrics")
@patch("claude_invest.modules.scalp_engine.analyze_technicals")
@patch("claude_invest.modules.scalp_engine.execute_order")
@patch("claude_invest.modules.scalp_engine.get_current_price")
def test_full_scalp_cycle_entry_to_exit(
    mock_price, mock_exec, mock_tech, mock_metrics, tmp_db_path
):
    """
    Full cycle:
      1. scan finds MARA as a dip candidate
      2. run_scalp_cycle places a buy order and records it in the DB
      3. check_scalp_exits detects take-profit and closes the position
    """
    # --- Entry phase ---
    mock_metrics.return_value = {
        "ticker": "MARA", "atr_pct": 0.07, "intraday_change": -0.07, "volume_ratio": 2.4
    }
    mock_tech.return_value = {
        "ticker": "MARA", "rsi": 25.0, "current_price": 18.0,
        "macd": 0.0, "macd_signal": 0.0, "sma_20": 17.0, "sma_50": 16.0, "trend": "neutral"
    }
    mock_exec.return_value = {"status": "filled", "filled_qty": 5, "filled_avg_price": 18.0}

    db = Database(tmp_db_path)
    db.initialize()

    cycle_result = run_scalp_cycle(INTEGRATION_CONFIG, db)

    assert cycle_result["trades_placed"] == 1, "Expected exactly one trade to be placed"

    # Verify trade was recorded with correct strategy_id
    trades = db.get_trades(limit=10)
    scalp_trades = [t for t in trades if t.get("strategy_id") == "volatility_scalper"]
    assert len(scalp_trades) == 1, "Trade must be tagged with strategy_id='volatility_scalper'"
    assert scalp_trades[0]["ticker"] == "MARA"
    assert scalp_trades[0]["action"] == "buy"

    # --- Exit phase: simulate take-profit (+3.1%) ---
    mock_price.return_value = 18.56  # +3.1% above 18.0

    closed = check_scalp_exits(INTEGRATION_CONFIG, db)

    assert len(closed) == 1
    assert closed[0]["ticker"] == "MARA"
    assert closed[0]["exit_reason"] == "take_profit"
    assert closed[0]["pnl_pct"] > 0.03

    db.close()


@patch("claude_invest.modules.volatility_scanner._fetch_stock_metrics")
@patch("claude_invest.modules.scalp_engine.analyze_technicals")
@patch("claude_invest.modules.scalp_engine.execute_order")
def test_learning_engine_can_query_by_strategy_id(mock_exec, mock_tech, mock_metrics, tmp_db_path):
    """
    The learning engine queries trades by strategy_id.
    Verify that after a scalp cycle, filtered queries return the correct trade.
    """
    mock_metrics.return_value = {
        "ticker": "MARA", "atr_pct": 0.07, "intraday_change": -0.07, "volume_ratio": 2.4
    }
    mock_tech.return_value = {
        "ticker": "MARA", "rsi": 25.0, "current_price": 18.0,
        "macd": 0.0, "macd_signal": 0.0, "sma_20": 17.0, "sma_50": 16.0, "trend": "neutral"
    }
    mock_exec.return_value = {"status": "filled", "filled_qty": 5, "filled_avg_price": 18.0}

    db = Database(tmp_db_path)
    db.initialize()

    run_scalp_cycle(INTEGRATION_CONFIG, db)

    # Query trades filtered by strategy_id (mimics learning engine behavior)
    all_trades = db.get_trades(limit=100)
    scalp_trades = [t for t in all_trades if t.get("strategy_id") == "volatility_scalper"]

    assert len(scalp_trades) >= 1
    assert all(t["strategy_id"] == "volatility_scalper" for t in scalp_trades)

    db.close()
```

- [ ] **Step 2: Run the integration tests**

```bash
pytest tests/test_scalp_integration.py -v
```

Both tests must pass. If `db.get_open_positions_by_strategy` or `db.close_position` do not exist on the `Database` class, add them now:

In `src/claude_invest/modules/db.py`, add:

```python
def get_open_positions_by_strategy(self, strategy_id: str) -> list[dict]:
    """Return all open (not yet closed) trades for a given strategy_id."""
    rows = self.conn.execute(
        """
        SELECT id, ticker, action, shares, price, strategy_id, entry_mode, timestamp
        FROM trades
        WHERE strategy_id = ? AND status = 'open'
        ORDER BY timestamp DESC
        """,
        (strategy_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def close_position(self, ticker: str, strategy_id: str, exit_reason: str) -> None:
    """Mark an open position as closed and record the exit reason."""
    self.conn.execute(
        """
        UPDATE trades
        SET status = 'closed', exit_reason = ?, closed_at = ?
        WHERE ticker = ? AND strategy_id = ? AND status = 'open'
        """,
        (exit_reason, __import__("datetime").datetime.utcnow().isoformat(), ticker, strategy_id),
    )
    self.conn.commit()
```

- [ ] **Step 3: Run full test suite**

```bash
pytest tests/ -v --tb=short
```

All existing tests plus the new tests must pass. Fix any regressions before proceeding.

- [ ] **Step 4: Commit**

```bash
git add tests/test_scalp_integration.py src/claude_invest/modules/db.py
git commit -m "test: add integration test for full scalp cycle entry-to-exit"
```

---

## Run Commands Reference

| Command | Purpose |
|---------|---------|
| `pytest tests/test_volatility_scalper_config.py -v` | Validate settings.yaml changes |
| `pytest tests/test_technicals.py -v` | Validate timeframe parameter |
| `pytest tests/test_volatility_scanner.py -v` | Validate scanner module |
| `pytest tests/test_scalp_engine.py -v` | Validate scalp engine |
| `pytest tests/test_scalp_cli_api.py -v` | Validate CLI + API |
| `pytest tests/test_scalp_integration.py -v` | Validate full cycle |
| `pytest tests/ -v --tb=short` | Full suite regression check |
| `python -m claude_invest.main scalp-scan` | Live scanner output |
| `python -m claude_invest.main scalp-status` | Live open positions |
| `python -m claude_invest.main scalp-cycle` | Run one full cycle |
| `curl localhost:8000/api/scalp/candidates` | API candidates endpoint |
| `curl localhost:8000/api/scalp/status` | API status endpoint |
