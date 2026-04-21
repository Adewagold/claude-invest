import json
import pytest
from claude_invest.modules.db import Database
from claude_invest.modules.learner import (
    parse_signal_combo,
    analyze_day,
    score_patterns,
)


@pytest.fixture
def seeded_db(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()

    # Winning trade: MACD crossover + RSI 45 + neutral trend
    db.insert_decision({
        "ticker": "BTC/USD",
        "action": "buy",
        "reasoning": "MACD crossover, RSI 45",
        "signals_snapshot": json.dumps({
            "rsi": 45, "macd": -200, "macd_signal": -250,
            "trend": "neutral", "sentiment": 0.1, "price": 75000,
        }),
    })
    db.insert_decision({
        "ticker": "BTC/USD",
        "action": "sell",
        "reasoning": "Taking profit",
        "signals_snapshot": json.dumps({"price": 76000}),
    })
    db.insert_trade({
        "symbol": "BTC/USD", "side": "buy", "qty": 0.001,
        "price": 75000, "order_id": "t1", "trade_type": "swing", "status": "filled",
    })
    db.insert_trade({
        "symbol": "BTC/USD", "side": "sell", "qty": 0.001,
        "price": 76000, "order_id": "t2", "trade_type": "swing", "status": "filled",
    })

    # Losing trade: RSI > 70 + gap up
    db.insert_decision({
        "ticker": "CMND",
        "action": "buy",
        "reasoning": "FDA catalyst",
        "signals_snapshot": json.dumps({
            "rsi": 74.5, "macd": 0.13, "macd_signal": 0.06,
            "trend": "bullish", "sentiment": 0.2, "price": 1.45,
        }),
    })
    db.insert_decision({
        "ticker": "CMND",
        "action": "sell",
        "reasoning": "Stop loss",
        "signals_snapshot": json.dumps({"price": 1.30}),
    })
    db.insert_trade({
        "symbol": "CMND", "side": "buy", "qty": 80,
        "price": 1.45, "order_id": "t3", "trade_type": "day", "status": "filled",
    })
    db.insert_trade({
        "symbol": "CMND", "side": "sell", "qty": 80,
        "price": 1.30, "order_id": "t4", "trade_type": "day", "status": "filled",
    })

    return db


def test_parse_signal_combo():
    snapshot = {"rsi": 45, "macd": -200, "macd_signal": -250, "trend": "neutral", "sentiment": 0.1}
    combo = parse_signal_combo(snapshot)
    assert "rsi_30_50" in combo
    assert "macd_above_signal" in combo
    assert "trend_neutral" in combo


def test_parse_signal_combo_overbought():
    snapshot = {"rsi": 74.5, "macd": 0.13, "macd_signal": 0.06, "trend": "bullish", "sentiment": 0.2}
    combo = parse_signal_combo(snapshot)
    assert "rsi_70_100" in combo
    assert "macd_above_signal" in combo
    assert "trend_bullish" in combo


def test_score_patterns(seeded_db):
    patterns = score_patterns(seeded_db)
    assert len(patterns) >= 2
    rsi_30_50 = [p for p in patterns if "rsi_30_50" in p["signal_combo"]]
    if rsi_30_50:
        assert rsi_30_50[0]["wins"] >= 1
    rsi_70_100 = [p for p in patterns if "rsi_70_100" in p["signal_combo"]]
    if rsi_70_100:
        assert rsi_70_100[0]["losses"] >= 1


def test_analyze_day(seeded_db):
    report = analyze_day(seeded_db)
    assert "total_trades" in report
    assert "wins" in report
    assert "losses" in report
    assert "win_rate" in report
    assert "patterns" in report
    assert "total_pnl" in report
    assert report["total_trades"] >= 2
