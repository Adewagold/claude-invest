from unittest.mock import patch, MagicMock
import pytest
from claude_invest.modules.volatility_scanner import scan_volatile_stocks


SCALPER_CONFIG = {
    "volatility_scalper": {
        "watchlist": ["MARA", "IONQ", "RIVN"],
        "discovery": {
            "enabled": True,
            "min_atr_pct": 0.04,
            "lookback_days": 20,
        },
        "params": {
            "bar_timeframe": "15Min",
        },
    }
}


def _mock_stock_data(ticker, atr_pct=0.05, intraday_change=-0.06, volume_ratio=2.0):
    return {
        "ticker": ticker,
        "atr_pct": atr_pct,
        "intraday_change": intraday_change,
        "volume_ratio": volume_ratio,
    }


@patch("claude_invest.modules.volatility_scanner._fetch_stock_metrics")
def test_scan_returns_list(mock_fetch):
    mock_fetch.side_effect = lambda ticker, cfg: _mock_stock_data(ticker)
    result = scan_volatile_stocks(SCALPER_CONFIG)
    assert isinstance(result, list)
    assert len(result) > 0


@patch("claude_invest.modules.volatility_scanner._fetch_stock_metrics")
def test_each_result_has_required_keys(mock_fetch):
    mock_fetch.side_effect = lambda ticker, cfg: _mock_stock_data(ticker)
    result = scan_volatile_stocks(SCALPER_CONFIG)
    required = {"ticker", "atr_pct", "intraday_change", "volume_ratio", "source", "rank"}
    for item in result:
        assert required <= set(item.keys()), f"Missing keys in {item}"


@patch("claude_invest.modules.volatility_scanner._fetch_stock_metrics")
def test_curated_tickers_present(mock_fetch):
    mock_fetch.side_effect = lambda ticker, cfg: _mock_stock_data(ticker)
    result = scan_volatile_stocks(SCALPER_CONFIG)
    tickers = [r["ticker"] for r in result]
    for t in ["MARA", "IONQ", "RIVN"]:
        assert t in tickers


@patch("claude_invest.modules.volatility_scanner._fetch_stock_metrics")
def test_curated_tickers_ranked_first(mock_fetch):
    """Curated tickers must appear before discovered ones regardless of score."""
    def side_effect(ticker, cfg):
        # Give discovered ticker a higher raw score than curated
        if ticker == "SOUN":
            return _mock_stock_data(ticker, atr_pct=0.99, intraday_change=-0.99, volume_ratio=9.9)
        return _mock_stock_data(ticker, atr_pct=0.05)
    mock_fetch.side_effect = side_effect

    config = {
        "volatility_scalper": {
            "watchlist": ["MARA"],
            "discovery": {"enabled": True, "min_atr_pct": 0.04, "lookback_days": 20},
            "params": {"bar_timeframe": "15Min"},
        }
    }

    with patch("claude_invest.modules.volatility_scanner._discover_volatile_stocks",
               return_value=["SOUN"]):
        result = scan_volatile_stocks(config)

    curated_positions = [i for i, r in enumerate(result) if r["source"] == "curated"]
    discovered_positions = [i for i, r in enumerate(result) if r["source"] == "discovered"]
    if curated_positions and discovered_positions:
        assert max(curated_positions) < min(discovered_positions)


@patch("claude_invest.modules.volatility_scanner._fetch_stock_metrics")
@patch("claude_invest.modules.volatility_scanner._discover_volatile_stocks")
def test_discovery_disabled_returns_only_curated(mock_discover, mock_fetch):
    mock_fetch.side_effect = lambda ticker, cfg: _mock_stock_data(ticker)
    config = {
        "volatility_scalper": {
            "watchlist": ["MARA", "IONQ"],
            "discovery": {"enabled": False, "min_atr_pct": 0.04, "lookback_days": 20},
            "params": {"bar_timeframe": "15Min"},
        }
    }
    result = scan_volatile_stocks(config)
    mock_discover.assert_not_called()
    assert all(r["source"] == "curated" for r in result)


@patch("claude_invest.modules.volatility_scanner._fetch_stock_metrics")
def test_low_atr_stocks_excluded_from_discovery(mock_fetch):
    """Stocks below min_atr_pct must be filtered out of discovered results."""
    def side_effect(ticker, cfg):
        if ticker == "LOW_ATR":
            return _mock_stock_data(ticker, atr_pct=0.01)  # below 0.04 threshold
        return _mock_stock_data(ticker, atr_pct=0.06)
    mock_fetch.side_effect = side_effect

    config = {
        "volatility_scalper": {
            "watchlist": ["MARA"],
            "discovery": {"enabled": True, "min_atr_pct": 0.04, "lookback_days": 20},
            "params": {"bar_timeframe": "15Min"},
        }
    }
    with patch("claude_invest.modules.volatility_scanner._discover_volatile_stocks",
               return_value=["LOW_ATR", "HIGH_ATR"]):
        result = scan_volatile_stocks(config)
    tickers = [r["ticker"] for r in result]
    assert "LOW_ATR" not in tickers


@patch("claude_invest.modules.volatility_scanner._fetch_stock_metrics")
def test_results_are_ranked_ascending(mock_fetch):
    mock_fetch.side_effect = lambda ticker, cfg: _mock_stock_data(ticker)
    result = scan_volatile_stocks(SCALPER_CONFIG)
    ranks = [r["rank"] for r in result]
    assert ranks == list(range(1, len(ranks) + 1))
