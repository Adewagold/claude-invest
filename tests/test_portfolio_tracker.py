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
    config = {"portfolio": {"sectors": {"overrides": {}}}, "risk_tiers": {}}
    result = classify_sector("BTC/USD", config)
    assert result == "crypto"


def test_assign_risk_tier_meme(tracker_config):
    assert assign_risk_tier("meme", tracker_config) == "risk"


def test_assign_risk_tier_technology(tracker_config):
    assert assign_risk_tier("technology", tracker_config) == "neutral"


def test_assign_risk_tier_reits(tracker_config):
    assert assign_risk_tier("reits", tracker_config) == "safe"


def test_assign_risk_tier_unknown(tracker_config):
    assert assign_risk_tier("unknown_sector", tracker_config) == "neutral"


def test_get_allocation_basic(tracker_config):
    positions = [
        {"symbol": "PFE", "market_value": 5300.0, "avg_entry_price": 26.52, "current_price": 27.56, "qty": 194},
        {"symbol": "BTCUSD", "market_value": 99.0, "avg_entry_price": 75658, "current_price": 76000, "qty": 0.0013},
        {"symbol": "TRUMPUSD", "market_value": 100.0, "avg_entry_price": 2.84, "current_price": 2.90, "qty": 35},
    ]
    result = get_allocation(tracker_config, positions)
    assert "tiers" in result
    assert result["total_value"] == 5499.0
    assert "meme" in result["sectors"]


def test_get_allocation_drift_detection(tracker_config):
    positions = [
        {"symbol": "PFE", "market_value": 5000.0, "avg_entry_price": 26.52, "current_price": 27.56, "qty": 194},
    ]
    result = get_allocation(tracker_config, positions)
    assert result["tiers"]["safe"]["alert"] is True
    assert result["tiers"]["risk"]["alert"] is True


def test_get_allocation_empty_positions(tracker_config):
    result = get_allocation(tracker_config, [])
    assert result["total_value"] == 0
    assert result["tiers"]["safe"]["actual"] == 0
