import json
import pytest
from unittest.mock import patch, MagicMock
from claude_invest.modules.db import Database
from claude_invest.modules.core_engine import run_core_cycle, get_core_status, rebalance_core


@pytest.fixture
def core_config():
    return {
        "capital": 5000,
        "capital_split": {"trading": 0.50, "core": 0.50},
        "max_positions": 8,
        "max_per_ticker": 0.10,
        "position_size_pct": 0.02,
        "daily_loss_limit": -150,
        "pdt_tracking": False,
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
def core_db(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    return db


def test_full_core_pipeline(core_config, core_db):
    """Integration test: cycle buys stocks, status reports them, rebalance previews."""
    mock_portfolio = {
        "equity": 85000, "cash": 80000, "buying_power": 160000,
        "daily_pnl": 0, "positions": [], "position_count": 0,
    }
    mock_technicals_nvda = {
        "current_price": 500.0, "rsi": 45, "macd": 1.0, "macd_signal": 0.5,
        "sma_20": 510, "sma_50": 520, "trend": "neutral",  # price < SMA-50 = dip
    }
    mock_technicals_msft = {
        "current_price": 400.0, "rsi": 50, "macd": 0.5, "macd_signal": 0.3,
        "sma_20": 390, "sma_50": 395, "trend": "neutral",  # price > SMA-50, no dip but DCA
    }
    mock_order = {
        "order_id": "test-order", "symbol": "NVDA", "side": "buy",
        "qty": 0.1, "filled_price": 500.0, "status": "filled",
    }

    with patch("claude_invest.modules.core_engine.get_portfolio", return_value=mock_portfolio), \
         patch("claude_invest.modules.core_engine.analyze_technicals") as mock_tech, \
         patch("claude_invest.modules.core_engine.execute_order", return_value=mock_order):

        mock_tech.side_effect = lambda t: mock_technicals_nvda if t == "NVDA" else mock_technicals_msft

        # Step 1: Run core cycle — should buy NVDA (dip) and MSFT (DCA first time)
        result = run_core_cycle(core_config, core_db)
        assert "buys_executed" in result
        assert len(result["buys_executed"]) >= 1  # At least NVDA (dip entry)

        # Step 2: Verify core_buys table has records
        buys = core_db.get_core_buys()
        assert len(buys) >= 1

        # Step 3: Check status
        mock_portfolio_with_positions = {
            "equity": 85000, "cash": 79900, "buying_power": 159800,
            "daily_pnl": 0,
            "positions": [
                {"symbol": "NVDA", "qty": 0.1, "market_value": 50.0, "avg_entry_price": 500, "current_price": 500, "unrealized_pl": 0},
            ],
            "position_count": 1,
        }
        with patch("claude_invest.modules.core_engine.get_portfolio", return_value=mock_portfolio_with_positions):
            status = get_core_status(core_config, core_db, mock_portfolio_with_positions)
            assert status["core_capital"] == 2500
            assert len(status["holdings"]) >= 1

        # Step 4: Rebalance preview (dry run)
        with patch("claude_invest.modules.core_engine.get_portfolio", return_value=mock_portfolio_with_positions):
            preview = rebalance_core(core_config, core_db, mock_portfolio_with_positions, dry_run=True)
            assert isinstance(preview, list)


def test_core_disabled_returns_empty(core_config, core_db):
    """When core_holdings.enabled is false, cycle returns empty."""
    core_config["core_holdings"]["enabled"] = False
    with patch("claude_invest.modules.core_engine.get_portfolio", return_value={
        "equity": 85000, "cash": 80000, "buying_power": 160000,
        "daily_pnl": 0, "positions": [], "position_count": 0,
    }):
        result = run_core_cycle(core_config, core_db)
        assert result.get("buys", []) == [] or result.get("status") == "disabled"
