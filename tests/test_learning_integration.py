import json
import os
import pytest
from claude_invest.modules.db import Database
from claude_invest.modules.learner import analyze_day, score_patterns
from claude_invest.modules.portfolio_tracker import get_allocation
from claude_invest.modules.strategy import update_lessons, build_strategy_brief, load_lessons


def test_full_learning_pipeline(tmp_db_path, sample_config, tmp_path):
    config, _ = sample_config
    db = Database(tmp_db_path)
    db.initialize()
    lessons_dir = str(tmp_path / "lessons")
    os.makedirs(os.path.join(lessons_dir, "daily"), exist_ok=True)

    # Simulate trades
    db.insert_decision({
        "ticker": "AAPL", "action": "buy", "reasoning": "Strong signals",
        "signals_snapshot": json.dumps({"rsi": 45, "macd": 1, "macd_signal": 0, "trend": "bullish", "sentiment": 0.5, "price": 150}),
    })
    db.insert_decision({
        "ticker": "AAPL", "action": "sell", "reasoning": "Target hit",
        "signals_snapshot": json.dumps({"price": 160}),
    })
    db.insert_trade({"symbol": "AAPL", "side": "buy", "qty": 1, "price": 150, "order_id": "i1", "trade_type": "swing", "status": "filled"})
    db.insert_trade({"symbol": "AAPL", "side": "sell", "qty": 1, "price": 160, "order_id": "i2", "trade_type": "swing", "status": "filled"})

    # 1. Analyze
    report = analyze_day(db)
    assert report["wins"] >= 1
    assert report["total_pnl"] > 0

    # 2. Score patterns
    patterns = score_patterns(db)
    assert len(patterns) >= 1

    # 3. Update lessons
    update_lessons(lessons_dir, patterns, "2026-04-20")
    lessons = load_lessons(lessons_dir)
    assert len(lessons["patterns"]) >= 1

    # 4. Build strategy brief
    positions = [{"symbol": "AAPL", "market_value": 160, "avg_entry_price": 150, "current_price": 160, "qty": 1}]
    allocation = get_allocation(config, positions)
    brief = build_strategy_brief(lessons_dir, allocation)

    assert isinstance(brief, str)
    assert len(brief) > 50
    assert os.path.exists(os.path.join(lessons_dir, "strategy-brief.md"))
    assert os.path.exists(os.path.join(lessons_dir, "daily", "2026-04-20.md"))

    db.close()


def test_allocation_with_mixed_portfolio(sample_config):
    config, _ = sample_config
    positions = [
        {"symbol": "PFE", "market_value": 5300, "avg_entry_price": 26.52, "current_price": 27.56, "qty": 194},
        {"symbol": "SNDK", "market_value": 920, "avg_entry_price": 913, "current_price": 920, "qty": 1},
        {"symbol": "BTCUSD", "market_value": 99, "avg_entry_price": 75658, "current_price": 76000, "qty": 0.001},
        {"symbol": "ETHUSD", "market_value": 98, "avg_entry_price": 2337, "current_price": 2320, "qty": 0.042},
        {"symbol": "TRUMPUSD", "market_value": 100, "avg_entry_price": 2.84, "current_price": 2.90, "qty": 35},
    ]
    allocation = get_allocation(config, positions)

    assert allocation["total_value"] == 6517
    assert allocation["tiers"]["neutral"]["actual"] > 0.5  # PFE + SNDK dominate
    assert allocation["tiers"]["risk"]["actual"] > 0  # crypto + meme
    assert allocation["tiers"]["safe"]["actual"] == 0  # no safe assets
    assert allocation["tiers"]["safe"]["alert"] is True  # 0% vs 30% target
