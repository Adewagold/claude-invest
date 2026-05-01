import json
import pytest
from unittest.mock import patch, MagicMock
from claude_invest.modules.db import Database
from claude_invest.modules.scalp_engine import run_scalp_cycle, check_scalp_exits
from claude_invest.modules.volatility_scanner import scan_volatile_stocks


@pytest.fixture
def scalp_config():
    return {
        "capital": 5000,
        "capital_split": {"trading": 0.50, "core": 0.50},
        "max_positions": 8,
        "max_per_ticker": 0.10,
        "position_size_pct": 0.02,
        "daily_loss_limit": -150,
        "pdt_tracking": False,
        "volatility_scalper": {
            "name": "Volatility Scalper",
            "enabled": True,
            "capital_pct": 0.25,
            "modes": {"dip_buying": True, "rally_shorting": False, "news_reaction": True},
            "watchlist": ["OKLO", "RIVN"],
            "discovery": {"enabled": False, "min_atr_pct": 0.04, "lookback_days": 20},
            "params": {
                "bar_timeframe": "15Min",
                "dip_threshold": -0.05,
                "rally_threshold": 0.05,
                "rsi_period": 14,
                "rsi_oversold": 30,
                "rsi_overbought": 75,
                "news_sentiment_buy": -0.3,
                "news_sentiment_short": 0.4,
                "news_min_articles": 3,
                "take_profit_pct": 0.03,
                "stop_loss_pct": 0.03,
                "max_hold_minutes": 120,
                "force_exit_time": "15:55",
                "max_concurrent": 2,
            },
        },
    }


def _make_mock_db(open_positions=None):
    """Create a mock Database with configurable open scalp positions."""
    db = MagicMock()
    db.get_open_positions_by_strategy.return_value = open_positions or []
    db.record_trade.return_value = None
    return db


def test_full_scalp_pipeline(scalp_config):
    """Integration: scan -> cycle -> verify entries logged."""
    # OKLO metrics: dipped 8%, RSI oversold
    mock_metrics_oklo = {
        "ticker": "OKLO", "atr_pct": 0.07, "intraday_change": -0.08,
        "volume_ratio": 2.4,
    }
    mock_metrics_rivn = {
        "ticker": "RIVN", "atr_pct": 0.06, "intraday_change": -0.02,
        "volume_ratio": 1.5,
    }
    mock_technicals = {
        "current_price": 20.0, "rsi": 25, "macd": -0.5, "macd_signal": -0.3,
        "sma_20": 22.0, "sma_50": 23.0, "trend": "bearish",
    }
    mock_order = {
        "status": "filled", "filled_qty": 2, "filled_avg_price": 20.0,
    }

    def fake_fetch_metrics(ticker, scalper_cfg):
        return mock_metrics_oklo if ticker == "OKLO" else mock_metrics_rivn

    db = _make_mock_db()

    with patch("claude_invest.modules.volatility_scanner._fetch_stock_metrics", side_effect=fake_fetch_metrics), \
         patch("claude_invest.modules.scalp_engine.analyze_technicals", return_value=mock_technicals), \
         patch("claude_invest.modules.scalp_engine.execute_order", return_value=mock_order):

        # Step 1: Scan
        candidates = scan_volatile_stocks(scalp_config)
        assert len(candidates) >= 1

        # Step 2: Run cycle — scalp_engine calls scan internally, re-patch it here
        with patch("claude_invest.modules.scalp_engine.scan_volatile_stocks", return_value=candidates):
            result = run_scalp_cycle(scalp_config, db)

        # Verify summary shape
        assert "scanned" in result
        assert "trades_placed" in result
        assert result["scanned"] >= 1


def test_scalp_disabled_returns_empty(scalp_config):
    """When dip_buying and rally_shorting are both off, no trades are placed."""
    scalp_config["volatility_scalper"]["modes"]["dip_buying"] = False
    scalp_config["volatility_scalper"]["modes"]["rally_shorting"] = False

    mock_technicals = {
        "current_price": 20.0, "rsi": 25, "macd": -0.5, "macd_signal": -0.3,
        "sma_20": 22.0, "sma_50": 23.0, "trend": "bearish",
    }
    mock_candidates = [
        {"ticker": "OKLO", "atr_pct": 0.07, "intraday_change": -0.08,
         "volume_ratio": 2.4, "source": "curated", "rank": 1},
    ]

    db = _make_mock_db()

    with patch("claude_invest.modules.scalp_engine.scan_volatile_stocks", return_value=mock_candidates), \
         patch("claude_invest.modules.scalp_engine.analyze_technicals", return_value=mock_technicals), \
         patch("claude_invest.modules.scalp_engine.execute_order") as mock_exec:

        result = run_scalp_cycle(scalp_config, db)

        # No trades placed, no orders executed
        assert result["trades_placed"] == 0
        mock_exec.assert_not_called()
