import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from claude_invest.modules.technicals import analyze_technicals, compute_indicators


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
