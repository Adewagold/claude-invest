import json
import os
import pytest
from claude_invest.modules.strategy import (
    update_lessons,
    build_strategy_brief,
    load_lessons,
)


@pytest.fixture
def lessons_dir(tmp_path):
    d = tmp_path / "lessons"
    d.mkdir()
    (d / "daily").mkdir()
    return str(d)


def test_update_lessons_creates_file(lessons_dir):
    patterns = [
        {
            "signal_combo": "macd_above_signal + rsi_30_50 + trend_neutral",
            "wins": 3, "losses": 0, "total": 3,
            "win_rate": 1.0, "avg_pnl": 1.5, "confidence": "high",
            "tickers": ["BTC/USD", "ETH/USD", "TRUMP/USD"],
        },
        {
            "signal_combo": "macd_above_signal + rsi_70_100 + trend_bullish",
            "wins": 0, "losses": 2, "total": 2,
            "win_rate": 0.0, "avg_pnl": -8.5, "confidence": "low",
            "tickers": ["CMND", "ATAI"],
        },
    ]
    update_lessons(lessons_dir, patterns, "2026-04-20")

    lessons_path = os.path.join(lessons_dir, "lessons.json")
    assert os.path.exists(lessons_path)

    data = json.loads(open(lessons_path).read())
    assert len(data["patterns"]) == 2
    assert data["last_updated"] == "2026-04-20"


def test_load_lessons_empty(lessons_dir):
    lessons = load_lessons(lessons_dir)
    assert lessons["patterns"] == []


def test_load_lessons_existing(lessons_dir):
    data = {"patterns": [{"signal_combo": "test", "wins": 1}], "last_updated": "2026-04-20"}
    with open(os.path.join(lessons_dir, "lessons.json"), "w") as f:
        json.dump(data, f)

    lessons = load_lessons(lessons_dir)
    assert len(lessons["patterns"]) == 1


def test_build_strategy_brief(lessons_dir):
    patterns = [
        {
            "signal_combo": "macd_above_signal + rsi_30_50",
            "wins": 4, "losses": 0, "total": 4,
            "win_rate": 1.0, "avg_pnl": 2.0, "confidence": "high",
        },
        {
            "signal_combo": "rsi_70_100",
            "wins": 0, "losses": 3, "total": 3,
            "win_rate": 0.0, "avg_pnl": -10.0, "confidence": "high",
        },
    ]
    update_lessons(lessons_dir, patterns, "2026-04-20")

    allocation = {
        "tiers": {
            "safe": {"target": 0.30, "actual": 0.0, "drift": -0.30, "alert": True},
            "neutral": {"target": 0.40, "actual": 0.80, "drift": 0.40, "alert": True},
            "risk": {"target": 0.30, "actual": 0.20, "drift": -0.10, "alert": False},
        },
        "total_value": 5500,
    }

    brief = build_strategy_brief(lessons_dir, allocation)

    assert "PREFER" in brief
    assert "AVOID" in brief
    assert "rsi_70_100" in brief
    assert isinstance(brief, str)
    assert len(brief) > 50

    brief_path = os.path.join(lessons_dir, "strategy-brief.md")
    assert os.path.exists(brief_path)
