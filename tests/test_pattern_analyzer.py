import json
import pytest
from datetime import datetime, timedelta
from claude_invest.modules.pattern_analyzer import analyze_patterns


def _make_trade(ticker, entry_price, exit_price, entry_rsi, entry_macd,
                entry_macd_signal, trend, sentiment, strategy_id,
                entry_hour=10, hold_minutes=60, position_id="pos-1"):
    entry_time = datetime(2026, 4, 25, entry_hour, 0).isoformat()
    exit_time = (datetime(2026, 4, 25, entry_hour, 0) + timedelta(minutes=hold_minutes)).isoformat()
    return {
        "position_id": position_id,
        "ticker": ticker,
        "entry_time": entry_time,
        "exit_time": exit_time,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "pnl": exit_price - entry_price,
        "win": exit_price > entry_price,
        "status": "closed",
        "signal_combo": f"rsi_30_50 + macd_above_signal + trend_{trend}",
        "entry_signals": {
            "rsi": entry_rsi, "macd": entry_macd,
            "macd_signal": entry_macd_signal, "trend": trend,
            "sentiment": sentiment, "price": entry_price,
        },
        "exit_signals": {"price": exit_price},
        "strategy_id": strategy_id,
        "reasoning": "test",
    }


def test_analyze_patterns_returns_all_dimensions():
    trades = [
        _make_trade("BTC/USD", 75000, 76000, 45, -200, -250, "neutral", 0.1, "momentum",
                     entry_hour=10, hold_minutes=60, position_id="p1"),
        _make_trade("AAPL", 180, 185, 35, 0.5, 0.3, "bullish", 0.4, "mean_reversion",
                     entry_hour=9, hold_minutes=30, position_id="p2"),
        _make_trade("ETH/USD", 2300, 2280, 55, -5, -3, "bearish", 0.05, "momentum",
                     entry_hour=22, hold_minutes=120, position_id="p3"),
    ]
    report = analyze_patterns(trades)
    assert "generated_at" in report
    assert "total_trades" in report
    assert report["total_trades"] == 3
    assert "overall_win_rate" in report
    assert "signal_combos" in report
    assert "time_of_day" in report
    assert "hold_duration" in report
    assert "market_regime" in report
    assert "asset_class" in report
    assert "cross_dimensional" in report


def test_time_of_day_bucketing():
    trades = [
        _make_trade("AAPL", 180, 185, 35, 0.5, 0.3, "bullish", 0.4, "mean_reversion",
                     entry_hour=9, hold_minutes=30, position_id="p1"),
        _make_trade("AAPL", 180, 175, 55, 0.5, 0.3, "bullish", 0.4, "mean_reversion",
                     entry_hour=12, hold_minutes=30, position_id="p2"),
    ]
    report = analyze_patterns(trades)
    buckets = {b["bucket"]: b for b in report["time_of_day"]}
    # 9:00 with 30min hold = market_open (9:30-10:30) window
    assert any(b["wins"] >= 1 for b in report["time_of_day"])
    assert any(b["losses"] >= 1 for b in report["time_of_day"])


def test_hold_duration_bucketing():
    trades = [
        _make_trade("AAPL", 180, 185, 35, 0.5, 0.3, "bullish", 0.4, "mean_reversion",
                     hold_minutes=10, position_id="p1"),
        _make_trade("AAPL", 180, 185, 35, 0.5, 0.3, "bullish", 0.4, "mean_reversion",
                     hold_minutes=120, position_id="p2"),
    ]
    report = analyze_patterns(trades)
    buckets = {b["bucket"]: b for b in report["hold_duration"]}
    assert "scalp" in buckets
    assert "swing_short" in buckets


def test_asset_class_detection():
    trades = [
        _make_trade("BTC/USD", 75000, 76000, 45, -200, -250, "neutral", 0.1, "momentum",
                     position_id="p1"),
        _make_trade("AAPL", 180, 185, 35, 0.5, 0.3, "bullish", 0.4, "mean_reversion",
                     position_id="p2"),
    ]
    report = analyze_patterns(trades)
    classes = {(a["asset_class"], a["strategy_id"]): a for a in report["asset_class"]}
    assert ("crypto", "momentum") in classes
    assert ("stock", "mean_reversion") in classes


def test_confidence_levels():
    trades = [
        _make_trade("AAPL", 180, 185, 35, 0.5, 0.3, "bullish", 0.4, "mean_reversion",
                     position_id=f"p{i}")
        for i in range(5)
    ]
    report = analyze_patterns(trades)
    for combo in report["signal_combos"]:
        if combo["total"] >= 5 and combo["total"] < 10:
            assert combo["confidence"] == "low"


def test_empty_trades():
    report = analyze_patterns([])
    assert report["total_trades"] == 0
    assert report["overall_win_rate"] == 0
    assert report["signal_combos"] == []
