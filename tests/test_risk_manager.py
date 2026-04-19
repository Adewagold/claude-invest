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
