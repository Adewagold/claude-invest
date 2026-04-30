"""Tests for core_engine.py"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from claude_invest.modules.db import Database
from claude_invest.modules.core_engine import (
    get_core_status,
    run_core_cycle,
    check_core_exits,
    rebalance_core,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def core_config():
    return {
        "mode": "paper",
        "capital": 10000,
        "max_positions": 15,
        "max_per_ticker": 0.10,
        "position_size_pct": 0.02,
        "daily_loss_limit": -300,
        "pdt_tracking": False,
        "capital_split": {"trading": 0.50, "core": 0.50},
        "core_holdings": {
            "enabled": True,
            "max_positions": 15,
            "buy_list": [
                {"symbol": "NVDA", "sector": "tech", "weight": 0.50},
                {"symbol": "MSFT", "sector": "tech", "weight": 0.50},
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
def db(tmp_path):
    d = Database(str(tmp_path / "test.db"))
    d.initialize()
    return d


def make_portfolio(positions=None):
    positions = positions or []
    return {
        "equity": 10000,
        "cash": 5000,
        "buying_power": 5000,
        "daily_pnl": 0,
        "positions": positions,
        "position_count": len(positions),
    }


# ---------------------------------------------------------------------------
# get_core_status tests
# ---------------------------------------------------------------------------

def test_get_core_status_empty(core_config, db):
    """No holdings returns empty-valued list."""
    portfolio = make_portfolio()
    status = get_core_status(core_config, db, portfolio)

    assert status["core_capital"] == 5000.0  # 10000 * 0.50
    assert isinstance(status["holdings"], list)
    assert len(status["holdings"]) == 2  # buy_list has 2 items
    for h in status["holdings"]:
        assert h["current_value"] == 0.0
        assert h["weight"] == 0.0
        assert h["cost_basis"] == 0.0
    assert "next_rebalance_date" in status
    assert "cash_remaining" in status


def test_get_core_status_with_holdings(core_config, db):
    """Returns correct weights and drift when holdings are present."""
    # Seed a core buy for NVDA
    db.insert_core_buy({
        "symbol": "NVDA",
        "qty": 2.0,
        "price": 500.0,
        "cost_basis": 1000.0,
    })

    portfolio = make_portfolio(positions=[
        {"symbol": "NVDA", "qty": 2.0, "avg_entry_price": 500.0, "current_price": 600.0, "unrealized_pl": 200.0, "market_value": 1200.0},
        {"symbol": "MSFT", "qty": 1.0, "avg_entry_price": 400.0, "current_price": 400.0, "unrealized_pl": 0.0, "market_value": 400.0},
    ])

    status = get_core_status(core_config, db, portfolio)

    total = 1200.0 + 400.0  # 1600
    nvda_holding = next(h for h in status["holdings"] if h["symbol"] == "NVDA")
    msft_holding = next(h for h in status["holdings"] if h["symbol"] == "MSFT")

    assert abs(nvda_holding["weight"] - (1200.0 / total)) < 1e-6
    assert abs(msft_holding["weight"] - (400.0 / total)) < 1e-6

    # drift = actual - target (target is 0.50 for both)
    assert abs(nvda_holding["drift"] - (1200.0 / total - 0.50)) < 1e-6
    assert nvda_holding["cost_basis"] == 1000.0


# ---------------------------------------------------------------------------
# run_core_cycle tests
# ---------------------------------------------------------------------------

@patch("claude_invest.modules.core_engine.execute_order")
@patch("claude_invest.modules.core_engine.analyze_technicals")
@patch("claude_invest.modules.core_engine.get_portfolio")
def test_run_core_cycle_dip_entry(mock_portfolio, mock_technicals, mock_execute, core_config, db):
    """Buys when current price is below SMA-50 (dip entry)."""
    mock_portfolio.return_value = make_portfolio()
    mock_technicals.return_value = {
        "ticker": "NVDA",
        "current_price": 450.0,
        "sma_50": 500.0,  # price < sma_50 => dip
        "rsi": 40.0,
        "macd": -0.5,
    }
    mock_execute.return_value = {
        "order_id": "ORD-NVDA-1",
        "symbol": "NVDA",
        "side": "buy",
        "qty": 0.222222,
        "filled_price": 450.0,
        "status": "filled",
    }

    result = run_core_cycle(core_config, db)

    assert len(result["buys_executed"]) >= 1
    nvda_buy = next((b for b in result["buys_executed"] if b["symbol"] == "NVDA"), None)
    assert nvda_buy is not None
    assert nvda_buy["reason"] == "dip_entry"


@patch("claude_invest.modules.core_engine.execute_order")
@patch("claude_invest.modules.core_engine.analyze_technicals")
@patch("claude_invest.modules.core_engine.get_portfolio")
def test_run_core_cycle_dca_fallback(mock_portfolio, mock_technicals, mock_execute, core_config, db):
    """Buys when last buy was more than dca_interval_days ago (DCA fallback)."""
    mock_portfolio.return_value = make_portfolio()

    # Price above SMA-50, so dip_entry=False; but last buy was 10 days ago => dca_due=True
    mock_technicals.return_value = {
        "ticker": "NVDA",
        "current_price": 600.0,
        "sma_50": 500.0,  # price > sma_50 => NOT a dip
        "rsi": 60.0,
        "macd": 0.5,
    }
    mock_execute.return_value = {
        "order_id": "ORD-NVDA-2",
        "symbol": "NVDA",
        "side": "buy",
        "qty": 0.166667,
        "filled_price": 600.0,
        "status": "filled",
    }

    # Seed a buy from 10 days ago
    old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    db._get_conn().execute(
        "INSERT INTO core_buys (timestamp, symbol, qty, price, cost_basis) VALUES (?, ?, ?, ?, ?)",
        (old_ts, "NVDA", 1.0, 500.0, 500.0),
    )
    db._get_conn().commit()

    result = run_core_cycle(core_config, db)

    nvda_buy = next((b for b in result["buys_executed"] if b["symbol"] == "NVDA"), None)
    assert nvda_buy is not None
    assert nvda_buy["reason"] == "dca_fallback"


@patch("claude_invest.modules.core_engine.execute_order")
@patch("claude_invest.modules.core_engine.analyze_technicals")
@patch("claude_invest.modules.core_engine.get_portfolio")
def test_run_core_cycle_skips_recently_bought(mock_portfolio, mock_technicals, mock_execute, core_config, db):
    """No buy when last buy was < 7 days ago AND price is above SMA-50."""
    mock_portfolio.return_value = make_portfolio()
    # Both symbols return price > SMA-50 (no dip)
    mock_technicals.return_value = {
        "current_price": 600.0,
        "sma_50": 500.0,  # price > sma_50 => no dip
        "rsi": 55.0,
        "macd": 0.2,
    }
    mock_execute.return_value = {}

    recent_ts = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    # Seed recent buys for BOTH symbols in the buy_list
    for sym in ("NVDA", "MSFT"):
        db._get_conn().execute(
            "INSERT INTO core_buys (timestamp, symbol, qty, price, cost_basis) VALUES (?, ?, ?, ?, ?)",
            (recent_ts, sym, 1.0, 580.0, 580.0),
        )
    db._get_conn().commit()

    result = run_core_cycle(core_config, db)

    assert len(result["buys_executed"]) == 0
    nvda_skip = next((s for s in result["buys_skipped"] if s["symbol"] == "NVDA"), None)
    assert nvda_skip is not None
    assert nvda_skip["reason"] == "no_trigger"
    mock_execute.assert_not_called()


# ---------------------------------------------------------------------------
# check_core_exits tests
# ---------------------------------------------------------------------------

@patch("claude_invest.modules.core_engine.execute_order")
def test_check_core_exits_removal(mock_execute, core_config, db):
    """Sells a stock that was removed from the buy_list."""
    mock_execute.return_value = {
        "order_id": "ORD-EXIT-1",
        "symbol": "ORCL",
        "side": "sell",
        "qty": 5.0,
        "filled_price": 120.0,
        "status": "filled",
    }

    # Seed a core buy for ORCL (not in buy_list)
    db.insert_core_buy({
        "symbol": "ORCL",
        "qty": 5.0,
        "price": 110.0,
        "cost_basis": 550.0,
    })

    portfolio = make_portfolio(positions=[
        {"symbol": "ORCL", "qty": 5.0, "avg_entry_price": 110.0, "current_price": 120.0, "unrealized_pl": 50.0, "market_value": 600.0},
    ])

    exits = check_core_exits(core_config, db, portfolio)

    orcl_exit = next((e for e in exits if e["symbol"] == "ORCL"), None)
    assert orcl_exit is not None
    assert orcl_exit["reason"] == "removed_from_buy_list"
    assert orcl_exit["qty"] == 5.0
    mock_execute.assert_called_once_with("ORCL", "sell", 5.0)


@patch("claude_invest.modules.core_engine.execute_order")
def test_check_core_exits_no_signal_sell(mock_execute, core_config, db):
    """Does NOT sell even when RSI > 80 — only sentiment-based exits are allowed."""
    # Seed core buys for both NVDA and MSFT so they appear in core positions
    for sym in ("NVDA", "MSFT"):
        db.insert_core_buy({
            "symbol": sym,
            "qty": 2.0,
            "price": 500.0,
            "cost_basis": 1000.0,
        })

    # Insert signals with high RSI for NVDA (should be ignored by core engine)
    for i in range(5):
        db.insert_signal({
            "ticker": "NVDA",
            "sentiment_score": 0.5,  # positive sentiment — no sentiment exit
            "rsi": 85.0,             # overbought RSI — must be IGNORED
            "macd": 1.5,
        })

    # Portfolio with both positions roughly equal weight (~50/50) so no overweight trim
    portfolio = make_portfolio(positions=[
        {"symbol": "NVDA", "qty": 2.0, "avg_entry_price": 500.0, "current_price": 600.0, "unrealized_pl": 200.0, "market_value": 1200.0},
        {"symbol": "MSFT", "qty": 2.0, "avg_entry_price": 500.0, "current_price": 600.0, "unrealized_pl": 200.0, "market_value": 1200.0},
    ])
    # NVDA weight = 50%, MSFT weight = 50%; max_position_pct is 20% but buy_list target is 50%
    # The overweight trim uses target_weight (0.50), so actual 0.50 == target, no trim.

    exits = check_core_exits(core_config, db, portfolio)

    nvda_exit = next((e for e in exits if e["symbol"] == "NVDA"), None)
    # Must NOT have been sold — RSI-based signals must never trigger a sell
    assert nvda_exit is None
    mock_execute.assert_not_called()


# ---------------------------------------------------------------------------
# rebalance_core tests
# ---------------------------------------------------------------------------

@patch("claude_invest.modules.core_engine.execute_order")
def test_rebalance_dry_run(mock_execute, core_config, db):
    """Dry run returns preview actions without executing orders."""
    portfolio = make_portfolio(positions=[
        {"symbol": "NVDA", "qty": 2.0, "avg_entry_price": 500.0, "current_price": 500.0, "unrealized_pl": 0.0, "market_value": 800.0},
        {"symbol": "MSFT", "qty": 1.0, "avg_entry_price": 200.0, "current_price": 200.0, "unrealized_pl": 0.0, "market_value": 200.0},
    ])
    # total = 1000; NVDA weight=0.80, MSFT weight=0.20; targets are 0.50/0.50
    # Both drift > 0.05 threshold

    actions = rebalance_core(core_config, db, portfolio, dry_run=True)

    assert len(actions) > 0
    mock_execute.assert_not_called()
    for action in actions:
        assert action["dry_run"] is True
        assert "order" not in action


@patch("claude_invest.modules.core_engine.execute_order")
def test_rebalance_trims_overweight(mock_execute, core_config, db):
    """Sells excess when a position exceeds its target weight by more than drift_threshold."""
    mock_execute.return_value = {
        "order_id": "ORD-TRIM-1",
        "symbol": "NVDA",
        "side": "sell",
        "qty": 1.2,
        "filled_price": 500.0,
        "status": "filled",
    }

    portfolio = make_portfolio(positions=[
        # NVDA is 80% of core — target is 50%, drift is +30% >> threshold of 5%
        {"symbol": "NVDA", "qty": 4.0, "avg_entry_price": 500.0, "current_price": 500.0, "unrealized_pl": 0.0, "market_value": 2000.0},
        {"symbol": "MSFT", "qty": 1.0, "avg_entry_price": 500.0, "current_price": 500.0, "unrealized_pl": 0.0, "market_value": 500.0},
    ])
    # total = 2500; NVDA weight=0.80, MSFT weight=0.20

    actions = rebalance_core(core_config, db, portfolio, dry_run=False)

    nvda_action = next((a for a in actions if a["symbol"] == "NVDA"), None)
    assert nvda_action is not None
    assert nvda_action["side"] == "sell"
    assert nvda_action["qty"] > 0

    # MSFT is underweight (0.20 vs target 0.50) → should buy
    msft_action = next((a for a in actions if a["symbol"] == "MSFT"), None)
    assert msft_action is not None
    assert msft_action["side"] == "buy"

    assert mock_execute.call_count == 2
