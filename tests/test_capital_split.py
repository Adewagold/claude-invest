def test_strategy_capital_with_split():
    from claude_invest.modules.strategy_engine import get_strategy_capital
    config = {
        "capital": 5000,
        "capital_split": {"trading": 0.50, "core": 0.50},
        "strategies": {
            "mean_reversion": {"capital_pct": 0.33},
        },
    }
    capital = get_strategy_capital(config, "mean_reversion")
    assert capital == 2500 * 0.33  # $825, not $1650


def test_strategy_capital_without_split():
    from claude_invest.modules.strategy_engine import get_strategy_capital
    config = {
        "capital": 5000,
        "strategies": {
            "mean_reversion": {"capital_pct": 0.33},
        },
    }
    capital = get_strategy_capital(config, "mean_reversion")
    assert capital == 5000 * 0.33  # backward compat


from claude_invest.modules.db import Database
from claude_invest.modules.risk_manager import RiskManager


def test_risk_manager_trading_capital(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    config = {
        "capital": 5000,
        "capital_split": {"trading": 0.50, "core": 0.50},
        "max_positions": 8, "max_per_ticker": 0.10,
        "position_size_pct": 0.02, "daily_loss_limit": -150, "pdt_tracking": False,
    }
    rm = RiskManager(config, db)
    assert rm.trading_capital == 2500
    assert rm.core_capital == 2500
    db.close()


def test_risk_manager_core_position_size(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    config = {
        "capital": 5000,
        "capital_split": {"trading": 0.50, "core": 0.50},
        "max_positions": 8, "max_per_ticker": 0.10,
        "position_size_pct": 0.02, "daily_loss_limit": -150, "pdt_tracking": False,
        "core_holdings": {"entry": {"max_per_buy": 0.02}},
    }
    rm = RiskManager(config, db)
    # core_capital = 2500, max_per_buy = 0.02, so $50 max per buy
    qty = rm.calculate_core_position_size(100.0, config)
    assert qty == 0.5  # $50 / $100 = 0.5 shares
    db.close()


def test_risk_manager_check_core_trade(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    config = {
        "capital": 5000,
        "capital_split": {"trading": 0.50, "core": 0.50},
        "max_positions": 8, "max_per_ticker": 0.10,
        "position_size_pct": 0.02, "daily_loss_limit": -150, "pdt_tracking": False,
        "core_holdings": {"entry": {"max_per_buy": 0.02}},
    }
    rm = RiskManager(config, db)
    portfolio = {"daily_pnl": 0, "position_count": 2, "positions": []}
    result = rm.check_trade("NVDA", 0.5, 100, portfolio, strategy_type="core_holdings")
    assert result["approved"] is True
    db.close()


def test_risk_manager_backward_compat(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    config = {
        "capital": 5000,
        "max_positions": 8, "max_per_ticker": 0.10,
        "position_size_pct": 0.02, "daily_loss_limit": -150, "pdt_tracking": False,
    }
    rm = RiskManager(config, db)
    assert rm.trading_capital == 5000  # no split = all trading
    assert rm.core_capital == 0
    db.close()
