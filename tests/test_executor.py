import pytest
from unittest.mock import MagicMock, patch
from claude_invest.modules.executor import execute_order


def _mock_order(order_id, symbol, side, qty, status):
    order = MagicMock()
    order.id = order_id
    order.symbol = symbol
    order.side = side
    order.qty = str(qty)
    order.filled_avg_price = "150.00"
    order.status = status
    order.submitted_at = "2026-04-18T10:00:00Z"
    return order


@patch("claude_invest.modules.executor._get_trading_client")
def test_execute_buy_order(mock_client_fn):
    client = MagicMock()
    client.submit_order.return_value = _mock_order(
        "order-1", "AAPL", "buy", 5, "accepted"
    )
    mock_client_fn.return_value = client

    result = execute_order(symbol="AAPL", side="buy", qty=5)

    assert result["order_id"] == "order-1"
    assert result["symbol"] == "AAPL"
    assert result["side"] == "buy"
    assert result["status"] == "accepted"
    client.submit_order.assert_called_once()


@patch("claude_invest.modules.executor._get_trading_client")
def test_execute_sell_order(mock_client_fn):
    client = MagicMock()
    client.submit_order.return_value = _mock_order(
        "order-2", "TSLA", "sell", 3, "accepted"
    )
    mock_client_fn.return_value = client

    result = execute_order(symbol="TSLA", side="sell", qty=3)

    assert result["order_id"] == "order-2"
    assert result["side"] == "sell"


@patch("claude_invest.modules.executor._get_trading_client")
def test_execute_order_crypto(mock_client_fn):
    client = MagicMock()
    client.submit_order.return_value = _mock_order(
        "order-3", "BTC/USD", "buy", 0.001, "accepted"
    )
    mock_client_fn.return_value = client

    result = execute_order(symbol="BTC/USD", side="buy", qty=0.001)

    assert result["symbol"] == "BTC/USD"
    assert result["status"] == "accepted"


@patch("claude_invest.modules.executor._get_trading_client")
def test_execute_order_failure(mock_client_fn):
    client = MagicMock()
    client.submit_order.side_effect = Exception("Insufficient buying power")
    mock_client_fn.return_value = client

    result = execute_order(symbol="AAPL", side="buy", qty=5)

    assert result["status"] == "error"
    assert "Insufficient buying power" in result["error"]
