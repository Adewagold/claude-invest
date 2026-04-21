import json
import os
import pytest
from claude_invest.modules.watchlist import (
    load_watchlist,
    save_watchlist,
    add_to_watchlist,
    remove_from_watchlist,
    check_watchlist,
)


@pytest.fixture
def wl_path(tmp_path):
    return str(tmp_path / "watchlist.json")


def test_load_empty(wl_path):
    result = load_watchlist(wl_path)
    assert result == []


def test_add_and_load(wl_path):
    result = add_to_watchlist("NVDA", "AI play", wl_path)
    assert result["status"] == "added"

    tickers = load_watchlist(wl_path)
    assert len(tickers) == 1
    assert tickers[0]["symbol"] == "NVDA"


def test_add_duplicate(wl_path):
    add_to_watchlist("NVDA", "", wl_path)
    result = add_to_watchlist("NVDA", "", wl_path)
    assert result["status"] == "exists"


def test_remove(wl_path):
    add_to_watchlist("NVDA", "", wl_path)
    result = remove_from_watchlist("NVDA", wl_path)
    assert result["status"] == "removed"
    assert load_watchlist(wl_path) == []


def test_remove_not_found(wl_path):
    result = remove_from_watchlist("XYZ", wl_path)
    assert result["status"] == "not_found"


def test_check_watchlist_filters_held():
    tickers = [
        {"symbol": "NVDA", "note": "", "added": "2026-04-21"},
        {"symbol": "BTC/USD", "note": "", "added": "2026-04-21"},
    ]
    portfolio_symbols = ["BTCUSD", "PFE"]
    result = check_watchlist(tickers, portfolio_symbols)
    assert result[0]["held"] is False  # NVDA not held
    assert result[1]["held"] is True   # BTC/USD held as BTCUSD
