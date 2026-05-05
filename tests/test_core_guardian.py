import pytest
from unittest.mock import patch
from claude_invest.modules.db import Database
from claude_invest.modules.core_guardian import (
    update_peaks,
    check_core_health,
    check_probation_promotions,
)


@pytest.fixture
def guardian_config():
    return {
        "capital": 5000,
        "capital_split": {"core": 0.5, "trading": 0.5},
        "core_holdings": {
            "buy_list": [
                {"symbol": "NVDA", "sector": "tech", "weight": 0.071},
                {"symbol": "SPY", "sector": "etf", "weight": 0.071},
            ],
        },
        "core_guardian": {
            "warning_drawdown": -0.15,
            "reduce_drawdown": -0.25,
            "exit_drawdown": -0.35,
            "warning_days": 5,
            "reduce_days": 10,
            "crash_override_threshold": -0.10,
            "probation_tighter_factor": 0.67,
        },
        "graduation": {
            "probation_days": 30,
        },
    }


@pytest.fixture
def guardian_db(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    return db


def test_update_peaks_sets_new_peak(guardian_config, guardian_db):
    """First time seeing a symbol sets the peak."""
    portfolio = {
        "positions": [
            {"symbol": "NVDA", "current_price": 200.0, "market_value": 200.0,
             "qty": 1, "avg_entry_price": 180.0, "unrealized_pl": 20.0},
        ]
    }
    update_peaks(guardian_db, portfolio, {"NVDA"})
    peak = guardian_db.get_core_peak("NVDA")
    assert peak["peak_price"] == 200.0


def test_update_peaks_only_increases(guardian_config, guardian_db):
    """Peak should not decrease."""
    guardian_db.upsert_core_peak("NVDA", 210.0, "2026-05-01")
    portfolio = {
        "positions": [
            {"symbol": "NVDA", "current_price": 195.0, "market_value": 195.0,
             "qty": 1, "avg_entry_price": 180.0, "unrealized_pl": 15.0},
        ]
    }
    update_peaks(guardian_db, portfolio, {"NVDA"})
    peak = guardian_db.get_core_peak("NVDA")
    assert peak["peak_price"] == 210.0  # Unchanged


def test_no_action_within_thresholds(guardian_config, guardian_db):
    """No drawdown -> no action."""
    guardian_db.upsert_core_peak("NVDA", 200.0, "2026-05-01")
    guardian_db.upsert_core_peak("SPY", 725.0, "2026-05-01")
    portfolio = {
        "positions": [
            {"symbol": "NVDA", "current_price": 195.0, "market_value": 195.0,
             "qty": 1, "avg_entry_price": 180.0, "unrealized_pl": 15.0},
            {"symbol": "SPY", "current_price": 720.0, "market_value": 720.0,
             "qty": 1, "avg_entry_price": 700.0, "unrealized_pl": 20.0},
        ]
    }

    result = check_core_health(guardian_config, guardian_db, portfolio)
    assert result["warnings"] == []
    assert result["trims"] == []
    assert result["exits"] == []
    assert result["crash_override"] is False


def test_warning_at_15pct_drawdown(guardian_config, guardian_db):
    """15% drawdown for 5+ days triggers warning."""
    guardian_db.upsert_core_peak("NVDA", 200.0, "2026-04-25")
    guardian_db.upsert_core_peak("SPY", 725.0, "2026-05-01")
    portfolio = {
        "positions": [
            {"symbol": "NVDA", "current_price": 168.0, "market_value": 168.0,
             "qty": 1, "avg_entry_price": 180.0, "unrealized_pl": -12.0},
            {"symbol": "SPY", "current_price": 720.0, "market_value": 720.0,
             "qty": 1, "avg_entry_price": 700.0, "unrealized_pl": 20.0},
        ]
    }

    with patch("claude_invest.modules.core_guardian._days_since_peak", return_value=6):
        result = check_core_health(guardian_config, guardian_db, portfolio)

    assert len(result["warnings"]) == 1
    assert result["warnings"][0]["symbol"] == "NVDA"


def test_crash_override_suspends_exits(guardian_config, guardian_db):
    """When SPY is down >10%, suspend all individual exits."""
    guardian_db.upsert_core_peak("NVDA", 200.0, "2026-04-25")
    guardian_db.upsert_core_peak("SPY", 800.0, "2026-04-01")
    portfolio = {
        "positions": [
            {"symbol": "NVDA", "current_price": 130.0, "market_value": 130.0,
             "qty": 1, "avg_entry_price": 180.0, "unrealized_pl": -50.0},
            {"symbol": "SPY", "current_price": 700.0, "market_value": 700.0,
             "qty": 1, "avg_entry_price": 700.0, "unrealized_pl": 0.0},
        ]
    }

    with patch("claude_invest.modules.core_guardian._days_since_peak", return_value=15):
        result = check_core_health(guardian_config, guardian_db, portfolio)

    assert result["crash_override"] is True
    assert result["exits"] == []
    assert result["trims"] == []


def test_exit_at_35pct_drawdown(guardian_config, guardian_db):
    """35% drawdown triggers full exit."""
    guardian_db.upsert_core_peak("NVDA", 200.0, "2026-04-20")
    guardian_db.upsert_core_peak("SPY", 725.0, "2026-05-01")
    portfolio = {
        "positions": [
            {"symbol": "NVDA", "current_price": 125.0, "market_value": 125.0,
             "qty": 1, "avg_entry_price": 180.0, "unrealized_pl": -55.0},
            {"symbol": "SPY", "current_price": 720.0, "market_value": 720.0,
             "qty": 1, "avg_entry_price": 700.0, "unrealized_pl": 20.0},
        ]
    }

    with patch("claude_invest.modules.core_guardian._days_since_peak", return_value=15), \
         patch("claude_invest.modules.core_guardian.execute_order") as mock_order:
        mock_order.return_value = {"order_id": "test", "status": "filled"}
        result = check_core_health(guardian_config, guardian_db, portfolio)

    assert len(result["exits"]) == 1
    assert result["exits"][0]["symbol"] == "NVDA"


def test_probation_promotion_after_30_days(guardian_config, guardian_db):
    """Stock in probation for 30+ days without hitting -15% gets promoted."""
    guardian_db.insert_graduation({
        "symbol": "MU",
        "entry_price": 565.0,
        "graduation_price": 645.0,
        "hold_days": 10,
        "gain_pct": 0.14,
        "sentiment_score": 0.20,
    })
    # Set timestamp to 35 days ago
    conn = guardian_db._get_conn()
    conn.execute(
        "UPDATE graduations SET timestamp = datetime('now', '-35 days') WHERE symbol = 'MU'"
    )
    conn.commit()

    guardian_db.upsert_core_peak("MU", 660.0, "2026-04-10")

    portfolio = {
        "positions": [
            {"symbol": "MU", "current_price": 650.0, "market_value": 650.0,
             "qty": 1, "avg_entry_price": 565.0, "unrealized_pl": 85.0},
        ]
    }

    promotions = check_probation_promotions(guardian_config, guardian_db, portfolio)
    assert len(promotions) == 1
    assert promotions[0]["symbol"] == "MU"

    # Verify DB was updated
    grad = guardian_db.get_graduation_by_symbol("MU")
    assert grad["status"] == "promoted"
