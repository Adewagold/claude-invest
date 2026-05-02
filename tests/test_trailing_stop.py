import pytest
from claude_invest.modules.trailing_stop import (
    update_peak, check_trailing_stop, check_partial_profit, reset_peak
)


def test_update_peak_tracks_highest():
    reset_peak("TEST")
    assert update_peak("TEST", 100) == 100
    assert update_peak("TEST", 110) == 110
    assert update_peak("TEST", 105) == 110  # doesn't go down
    reset_peak("TEST")


def test_trailing_stop_not_triggered_when_profitable():
    reset_peak("TEST2")
    result = check_trailing_stop("TEST2", 105, entry_price=100, trailing_pct=0.05)
    assert result["triggered"] is False
    assert result["peak_price"] == 105
    reset_peak("TEST2")


def test_trailing_stop_triggered_on_drop():
    reset_peak("TEST3")
    update_peak("TEST3", 120)  # Set peak
    result = check_trailing_stop("TEST3", 113, entry_price=100, trailing_pct=0.05)
    # Drop from 120 to 113 = 5.8% > 5% threshold
    assert result["triggered"] is True
    assert result["drop_from_peak_pct"] > 0.05
    reset_peak("TEST3")


def test_trailing_stop_inactive_when_not_profitable():
    reset_peak("TEST4")
    result = check_trailing_stop("TEST4", 95, entry_price=100, trailing_pct=0.05)
    assert result["triggered"] is False
    assert "inactive" in result["reason"]
    reset_peak("TEST4")


def test_partial_profit_at_10pct():
    result = check_partial_profit("TEST5", current_price=110, entry_price=100)
    assert result is not None
    assert result["hit"] is True
    assert result["sell_pct"] == 0.25


def test_partial_profit_not_hit():
    result = check_partial_profit("TEST6", current_price=105, entry_price=100)
    assert result is None  # Only 5% profit, need 10%


def test_partial_profit_at_20pct():
    # At 25% profit both levels are exceeded; function returns the first matching level (10%)
    # To specifically test the 20% level, pass custom levels starting at 20%
    result = check_partial_profit(
        "TEST7",
        current_price=125,
        entry_price=100,
        levels=[
            {"profit_pct": 0.20, "sell_pct": 0.25, "label": "20% profit — sell 25%"},
        ],
    )
    assert result is not None
    assert "20%" in result["label"]
