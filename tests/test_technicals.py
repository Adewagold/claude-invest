import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from claude_invest.modules.technicals import analyze_technicals, compute_indicators, _get_bars


def _make_price_df(prices: list[float]) -> pd.DataFrame:
    """Create a DataFrame mimicking OHLCV bar data."""
    n = len(prices)
    return pd.DataFrame({
        "open": prices,
        "high": [p * 1.02 for p in prices],
        "low": [p * 0.98 for p in prices],
        "close": prices,
        "volume": [1000000] * n,
    })


def test_compute_indicators_returns_all_fields():
    # Need at least 26 bars for MACD, 14 for RSI
    np.random.seed(42)
    prices = list(np.cumsum(np.random.randn(50)) + 100)
    df = _make_price_df(prices)

    result = compute_indicators(df)

    assert "rsi" in result
    assert "macd" in result
    assert "macd_signal" in result
    assert "sma_20" in result
    assert "sma_50" in result
    assert "trend" in result
    assert result["rsi"] is not None


def test_compute_indicators_uptrend():
    # Steadily rising prices
    prices = [100 + i * 0.5 for i in range(50)]
    df = _make_price_df(prices)

    result = compute_indicators(df)

    assert result["trend"] == "bullish"


def test_compute_indicators_downtrend():
    # Steadily falling prices
    prices = [150 - i * 0.5 for i in range(50)]
    df = _make_price_df(prices)

    result = compute_indicators(df)

    assert result["trend"] == "bearish"


@patch("claude_invest.modules.technicals._get_bars")
def test_analyze_technicals_returns_full_signal(mock_get_bars):
    np.random.seed(42)
    prices = list(np.cumsum(np.random.randn(50)) + 100)
    mock_get_bars.return_value = _make_price_df(prices)

    result = analyze_technicals("AAPL")

    assert result["ticker"] == "AAPL"
    assert "rsi" in result
    assert "macd" in result
    assert "trend" in result
    assert "current_price" in result


def _make_fake_df(n=60):
    """Return a minimal OHLCV DataFrame with timestamp column."""
    rng = pd.date_range("2026-01-01", periods=n, freq="1h")
    data = {
        "timestamp": rng,
        "open": np.linspace(10, 20, n),
        "high": np.linspace(10.5, 20.5, n),
        "low": np.linspace(9.5, 19.5, n),
        "close": np.linspace(10, 20, n),
        "volume": [100_000] * n,
    }
    return pd.DataFrame(data)


@patch("claude_invest.modules.technicals._get_bars")
def test_analyze_technicals_default_timeframe(mock_get_bars):
    mock_get_bars.return_value = _make_fake_df()
    result = analyze_technicals("AAPL")
    mock_get_bars.assert_called_once_with("AAPL", timeframe="1Hour")
    assert "rsi" in result
    assert result["ticker"] == "AAPL"


@patch("claude_invest.modules.technicals._get_bars")
def test_analyze_technicals_15min_timeframe(mock_get_bars):
    mock_get_bars.return_value = _make_fake_df()
    result = analyze_technicals("MARA", timeframe="15Min")
    mock_get_bars.assert_called_once_with("MARA", timeframe="15Min")
    assert result["ticker"] == "MARA"


@patch("claude_invest.modules.technicals.StockHistoricalDataClient")
def test_get_bars_passes_timeframe_to_alpaca(mock_client_cls):
    """_get_bars must map timeframe string to correct Alpaca TimeFrame object."""
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    fake_bars = MagicMock()
    fake_bars.df = _make_fake_df().set_index("timestamp")
    mock_client.get_stock_bars.return_value = fake_bars

    _get_bars("MARA", timeframe="15Min")
    call_args = mock_client.get_stock_bars.call_args
    request = call_args[0][0]
    assert str(request.timeframe) == "15Min"
