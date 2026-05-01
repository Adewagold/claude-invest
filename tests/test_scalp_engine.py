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


def _make_anchored_position(ticker="MARA", entry_price=18.0, side="long",
                            shares=100, age_minutes=10, fixed_now=None):
    """Create a position with entry_time relative to fixed_now (for deterministic tests)."""
    if fixed_now is None:
        fixed_now = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    entry_time = fixed_now - timedelta(minutes=age_minutes)
    return {
        "ticker": ticker,
        "side": side,
        "shares": shares,
        "entry_price": entry_price,
        "current_price": entry_price,
        "entry_time": entry_time.isoformat(),
        "entry_mode": "dip_buying",
        "strategy_id": "volatility_scalper",
    }


@patch("claude_invest.modules.scalp_engine._current_et_time")
@patch("claude_invest.modules.scalp_engine.get_current_price")
@patch("claude_invest.modules.scalp_engine.execute_order")
def test_take_profit_triggers_at_3_pct(mock_exec, mock_price, mock_time):
    fixed_now = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    mock_time.return_value = fixed_now
    mock_exec.return_value = {"status": "filled"}
    mock_price.return_value = 18.55  # +3.06% above 18.0

    db = _make_db()
    db.get_open_positions_by_strategy.return_value = [
        _make_anchored_position(entry_price=18.0, fixed_now=fixed_now)
    ]

    closed = check_scalp_exits(BASE_CONFIG, db)

    assert len(closed) == 1
    assert closed[0]["exit_reason"] == "take_profit"
    assert closed[0]["pnl_pct"] > 0


@patch("claude_invest.modules.scalp_engine._current_et_time")
@patch("claude_invest.modules.scalp_engine.get_current_price")
@patch("claude_invest.modules.scalp_engine.execute_order")
def test_stop_loss_triggers_at_minus_3_pct(mock_exec, mock_price, mock_time):
    fixed_now = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    mock_time.return_value = fixed_now
    mock_exec.return_value = {"status": "filled"}
    mock_price.return_value = 17.45  # -3.06% below 18.0

    db = _make_db()
    db.get_open_positions_by_strategy.return_value = [
        _make_anchored_position(entry_price=18.0, fixed_now=fixed_now)
    ]

    closed = check_scalp_exits(BASE_CONFIG, db)

    assert len(closed) == 1
    assert closed[0]["exit_reason"] == "stop_loss"
    assert closed[0]["pnl_pct"] < 0


@patch("claude_invest.modules.scalp_engine._current_et_time")
@patch("claude_invest.modules.scalp_engine.get_current_price")
@patch("claude_invest.modules.scalp_engine.execute_order")
def test_max_hold_triggers_after_120_minutes(mock_exec, mock_price, mock_time):
    fixed_now = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    mock_time.return_value = fixed_now
    mock_exec.return_value = {"status": "filled"}
    mock_price.return_value = 18.10  # no TP/SL

    # Create position with entry_time 130 min before fixed_now
    entry_time = fixed_now - timedelta(minutes=130)
    position = {
        "ticker": "MARA",
        "side": "long",
        "shares": 100,
        "entry_price": 18.0,
        "current_price": 18.0,
        "entry_time": entry_time.isoformat(),
        "entry_mode": "dip_buying",
        "strategy_id": "volatility_scalper",
    }

    db = _make_db()
    db.get_open_positions_by_strategy.return_value = [position]

    closed = check_scalp_exits(BASE_CONFIG, db)

    assert len(closed) == 1
    assert closed[0]["exit_reason"] == "max_hold"


@patch("claude_invest.modules.scalp_engine.get_current_price")
@patch("claude_invest.modules.scalp_engine.execute_order")
@patch("claude_invest.modules.scalp_engine._current_et_time")
def test_force_exit_closes_all_at_1555(mock_time, mock_exec, mock_price):
    """At or after 15:55 ET all scalp positions are closed regardless of P&L."""
    fixed_now = datetime(2026, 5, 1, 15, 56, tzinfo=timezone.utc)
    mock_time.return_value = fixed_now
    mock_exec.return_value = {"status": "filled"}
    mock_price.return_value = 18.10

    db = _make_db()
    db.get_open_positions_by_strategy.return_value = [
        _make_anchored_position(ticker="MARA", fixed_now=fixed_now),
        _make_anchored_position(ticker="IONQ", fixed_now=fixed_now),
    ]

    closed = check_scalp_exits(BASE_CONFIG, db)

    assert len(closed) == 2
    assert all(c["exit_reason"] == "force_exit" for c in closed)
