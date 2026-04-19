import json
import subprocess
import sys

import pytest
from unittest.mock import patch, MagicMock
from claude_invest.config.loader import load_config
from claude_invest.modules.db import Database
from claude_invest.modules.risk_manager import RiskManager


def test_full_decision_pipeline(tmp_db_path, sample_config):
    """Simulate a full poll cycle: portfolio -> scan -> analyze -> risk check -> execute."""
    config, _ = sample_config
    db = Database(tmp_db_path)
    db.initialize()

    # 1. Portfolio state
    portfolio = {
        "equity": 5000, "cash": 4800, "buying_power": 9600,
        "daily_pnl": 25.0, "positions": [], "position_count": 0,
    }
    db.insert_portfolio_snapshot({
        "total_value": portfolio["equity"], "cash": portfolio["cash"],
        "positions_value": 200, "daily_pnl": portfolio["daily_pnl"],
    })

    # 2. Simulate scanner finding a candidate
    db.insert_discovery({
        "ticker": "AAPL", "volume_score": 3.5, "news_score": 0.7,
        "sentiment": 0.65, "action_taken": "flagged",
    })

    # 3. Simulate signal analysis
    db.insert_signal({
        "ticker": "AAPL", "sentiment_score": 0.65, "rsi": 42.0,
        "macd": 1.5, "volume_ratio": 3.5, "trend": "bullish",
    })

    # 4. Risk check
    risk_mgr = RiskManager(config, db)
    trade_check = risk_mgr.check_trade("AAPL", 1, 150.0, portfolio)
    assert trade_check["approved"] is True

    # 5. Simulate trade execution
    db.insert_trade({
        "symbol": "AAPL", "side": "buy", "qty": 1, "price": 150.0,
        "order_id": "int-test-1", "trade_type": "swing", "status": "filled",
    })

    # 6. Log decision
    db.insert_decision({
        "ticker": "AAPL", "action": "buy",
        "reasoning": "Strong bullish signals: RSI 42, positive sentiment 0.65, volume 3.5x",
        "signals_snapshot": json.dumps({"rsi": 42, "sentiment": 0.65, "trend": "bullish"}),
    })

    # Verify full state
    trades = db.get_trades(symbol="AAPL")
    assert len(trades) == 1
    decisions = db.get_decisions()
    assert len(decisions) == 1
    assert "bullish" in decisions[0]["reasoning"]
    signals = db.get_signals(ticker="AAPL")
    assert signals[0]["trend"] == "bullish"

    db.close()


def test_risk_blocks_when_limits_exceeded(tmp_db_path, sample_config):
    """Verify the system stops trading when risk limits are hit."""
    config, _ = sample_config
    db = Database(tmp_db_path)
    db.initialize()
    risk_mgr = RiskManager(config, db)

    # Daily loss exceeded
    portfolio_loss = {
        "equity": 4800, "daily_pnl": -200,
        "position_count": 2, "positions": [],
    }
    result = risk_mgr.check_trade("AAPL", 1, 150.0, portfolio_loss)
    assert result["approved"] is False

    # Max positions hit
    portfolio_full = {
        "equity": 5000, "daily_pnl": 0,
        "position_count": 8, "positions": [],
    }
    result = risk_mgr.check_trade("AAPL", 1, 150.0, portfolio_full)
    assert result["approved"] is False

    # PDT limit
    db.record_day_trade("dt1")
    db.record_day_trade("dt2")
    db.record_day_trade("dt3")
    assert risk_mgr.check_pdt_allowed() is False

    db.close()
