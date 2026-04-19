import pytest
from unittest.mock import MagicMock, patch
from claude_invest.modules.portfolio import get_portfolio


def _mock_account():
    account = MagicMock()
    account.equity = "5200.00"
    account.cash = "4100.00"
    account.buying_power = "8200.00"
    account.portfolio_value = "5200.00"
    account.last_equity = "5150.00"
    return account


def _mock_position(symbol, qty, avg_price, current_price, unrealized_pl):
    pos = MagicMock()
    pos.symbol = symbol
    pos.qty = qty
    pos.avg_entry_price = avg_price
    pos.current_price = current_price
    pos.unrealized_pl = unrealized_pl
    pos.market_value = str(float(qty) * float(current_price))
    return pos


@patch("claude_invest.modules.portfolio._get_trading_client")
def test_get_portfolio_returns_state(mock_client_fn):
    client = MagicMock()
    client.get_account.return_value = _mock_account()
    client.get_all_positions.return_value = [
        _mock_position("AAPL", "5", "150.00", "155.00", "25.00"),
        _mock_position("BTC/USD", "0.01", "60000.00", "62000.00", "20.00"),
    ]
    mock_client_fn.return_value = client

    result = get_portfolio()

    assert result["equity"] == 5200.00
    assert result["cash"] == 4100.00
    assert result["daily_pnl"] == 50.00
    assert len(result["positions"]) == 2
    assert result["positions"][0]["symbol"] == "AAPL"
    assert result["positions"][1]["symbol"] == "BTC/USD"


@patch("claude_invest.modules.portfolio._get_trading_client")
def test_get_portfolio_empty_positions(mock_client_fn):
    client = MagicMock()
    client.get_account.return_value = _mock_account()
    client.get_all_positions.return_value = []
    mock_client_fn.return_value = client

    result = get_portfolio()

    assert result["positions"] == []
    assert result["position_count"] == 0
