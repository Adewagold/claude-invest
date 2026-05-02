import pytest
from unittest.mock import patch, MagicMock
from claude_invest.modules.db import Database
from claude_invest.modules.dividends import get_dividend_summary


def test_dividend_summary_with_no_history(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    positions = [
        {"symbol": "JNJ", "market_value": 50, "current_price": 230},
        {"symbol": "BTC/USD", "market_value": 100, "current_price": 78000},
    ]
    with patch("claude_invest.modules.dividends.get_dividend_history", return_value=[]):
        result = get_dividend_summary(db, positions)
        assert result["total_dividends_received"] == 0
        assert len(result["dividend_positions"]) == 1  # crypto skipped
        assert result["dividend_positions"][0]["symbol"] == "JNJ"
    db.close()


def test_dividend_summary_with_history(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    positions = [
        {"symbol": "JNJ", "market_value": 50, "current_price": 230},
        {"symbol": "JPM", "market_value": 50, "current_price": 313},
    ]
    mock_history = [
        {"symbol": "JNJ", "amount": 0.25, "date": "2026-04-15", "qty": 0.217, "per_share": 1.15},
        {"symbol": "JPM", "amount": 0.18, "date": "2026-04-01", "qty": 0.159, "per_share": 1.13},
    ]
    with patch("claude_invest.modules.dividends.get_dividend_history", return_value=mock_history):
        result = get_dividend_summary(db, positions)
        assert result["total_dividends_received"] == 0.43
        assert len(result["dividend_positions"]) == 2
    db.close()
