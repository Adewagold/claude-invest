import pytest
from unittest.mock import patch
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
            {"symbol": "MU", "qty": 4, "avg_entry_price": 500.0,
             "current_price": 610.0, "market_value": 2440.0, "unrealized_pl": 440.0}
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


def test_graduation_position_not_found(grad_config, grad_db):
    """Symbol not in portfolio -> sell."""
    portfolio = {"positions": []}

    result = check_graduation("FAKE", grad_config, grad_db, portfolio)
    assert result["decision"] == "sell"
    assert "not found" in result["reason"].lower()
