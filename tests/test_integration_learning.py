import json
import os
import pytest
from claude_invest.modules.db import Database
from claude_invest.modules.learner import _match_trades, analyze_day, score_patterns
from claude_invest.modules.pattern_analyzer import analyze_patterns
from claude_invest.modules.strategy import update_lessons, build_strategy_brief


@pytest.fixture
def full_db(tmp_db_path):
    """DB with 6 closed trades (4 wins, 2 losses) across strategies."""
    db = Database(tmp_db_path)
    db.initialize()

    trades_data = [
        ("AAPL", 180, 185, 35, 0.5, 0.3, "bullish", 0.4, "mean_reversion", "pos-1"),
        ("MSFT", 400, 410, 28, 0.3, 0.1, "neutral", 0.3, "mean_reversion", "pos-2"),
        ("BTC/USD", 75000, 76000, 45, -200, -250, "neutral", 0.1, "momentum", "pos-3"),
        ("NVDA", 900, 920, 38, 2.0, 1.5, "bullish", 0.5, "trend_pullback", "pos-4"),
        ("ETH/USD", 2300, 2280, 55, -5, -3, "bearish", 0.05, "momentum", "pos-5"),
        ("TSLA", 250, 240, 72, 3.0, 2.8, "bullish", 0.2, "mean_reversion", "pos-6"),
    ]

    for ticker, entry_p, exit_p, rsi, macd, macd_sig, trend, sent, strategy, pid in trades_data:
        db.insert_decision({
            "ticker": ticker, "action": "buy", "reasoning": f"test buy {ticker}",
            "signals_snapshot": json.dumps({
                "rsi": rsi, "macd": macd, "macd_signal": macd_sig,
                "trend": trend, "sentiment": sent, "price": entry_p,
                "strategy_id": strategy,
            }),
            "position_id": pid,
        })
        db.insert_decision({
            "ticker": ticker, "action": "sell", "reasoning": f"test sell {ticker}",
            "signals_snapshot": json.dumps({"price": exit_p}),
            "position_id": pid,
        })
        db.insert_trade({
            "symbol": ticker, "side": "buy", "qty": 1, "price": entry_p,
            "order_id": f"o-{pid}-buy", "trade_type": strategy, "status": "filled",
            "position_id": pid,
        })
        db.insert_trade({
            "symbol": ticker, "side": "sell", "qty": 1, "price": exit_p,
            "order_id": f"o-{pid}-sell", "trade_type": strategy, "status": "filled",
            "position_id": pid,
        })

    return db


def test_full_learning_pipeline(full_db, tmp_path):
    lessons_dir = str(tmp_path / "lessons")
    os.makedirs(os.path.join(lessons_dir, "daily"), exist_ok=True)

    # Step 1: Match trades
    matched = _match_trades(full_db)
    closed = [m for m in matched if m["status"] == "closed"]
    assert len(closed) == 6

    # Step 2: Analyze patterns
    report = analyze_patterns(closed)
    assert report["total_trades"] == 6
    assert abs(report["overall_win_rate"] - 4/6) < 0.02
    assert len(report["signal_combos"]) >= 1
    assert len(report["time_of_day"]) >= 1
    assert len(report["hold_duration"]) >= 1
    assert len(report["asset_class"]) >= 1

    # Step 3: Score patterns for lessons
    patterns = score_patterns(full_db)
    assert len(patterns) >= 1

    # Step 4: Update lessons
    update_lessons(lessons_dir, patterns, "2026-04-25")
    assert os.path.exists(os.path.join(lessons_dir, "lessons.json"))

    # Step 5: Build enhanced brief
    allocation = {"tiers": {}, "total_value": 5000}
    dimension_insights = {}
    if report["time_of_day"]:
        best = max(report["time_of_day"], key=lambda x: x.get("win_rate", 0))
        dimension_insights["best_time"] = best

    brief = build_strategy_brief(lessons_dir, allocation, dimension_insights=dimension_insights)
    assert isinstance(brief, str)
    assert len(brief) > 50

    # Verify asset class detection
    crypto_class = [a for a in report["asset_class"] if a["asset_class"] == "crypto"]
    stock_class = [a for a in report["asset_class"] if a["asset_class"] == "stock"]
    assert len(crypto_class) >= 1
    assert len(stock_class) >= 1
