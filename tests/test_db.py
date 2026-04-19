import pytest
from claude_invest.modules.db import Database


@pytest.fixture
def db(tmp_db_path):
    database = Database(tmp_db_path)
    database.initialize()
    return database


def test_initialize_creates_tables(db):
    tables = db.list_tables()
    expected = {"trades", "positions", "signals", "decisions", "portfolio_snapshots", "discovery_log", "pdt_tracker"}
    assert expected == set(tables)


def test_insert_and_query_trade(db):
    trade = {
        "symbol": "AAPL",
        "side": "buy",
        "qty": 5,
        "price": 150.0,
        "order_id": "test-order-1",
        "trade_type": "swing",
        "status": "filled",
    }
    db.insert_trade(trade)
    trades = db.get_trades(symbol="AAPL")
    assert len(trades) == 1
    assert trades[0]["symbol"] == "AAPL"
    assert trades[0]["qty"] == 5


def test_insert_and_query_decision(db):
    decision = {
        "ticker": "TSLA",
        "action": "buy",
        "reasoning": "Strong momentum with positive sentiment",
        "signals_snapshot": '{"rsi": 45, "sentiment": 0.7}',
    }
    db.insert_decision(decision)
    decisions = db.get_decisions(limit=10)
    assert len(decisions) == 1
    assert decisions[0]["ticker"] == "TSLA"
    assert decisions[0]["action"] == "buy"


def test_insert_portfolio_snapshot(db):
    snapshot = {
        "total_value": 5200.0,
        "cash": 4100.0,
        "positions_value": 1100.0,
        "daily_pnl": 45.50,
    }
    db.insert_portfolio_snapshot(snapshot)
    snapshots = db.get_portfolio_snapshots(limit=1)
    assert len(snapshots) == 1
    assert snapshots[0]["total_value"] == 5200.0


def test_insert_and_query_signal(db):
    signal = {
        "ticker": "NVDA",
        "sentiment_score": 0.65,
        "rsi": 42.0,
        "macd": 1.5,
        "volume_ratio": 2.3,
        "trend": "bullish",
    }
    db.insert_signal(signal)
    signals = db.get_signals(ticker="NVDA")
    assert len(signals) == 1
    assert signals[0]["rsi"] == 42.0


def test_insert_discovery_log(db):
    entry = {
        "ticker": "AMD",
        "volume_score": 3.2,
        "news_score": 0.6,
        "sentiment": 0.45,
        "action_taken": "flagged",
    }
    db.insert_discovery(entry)
    logs = db.get_discovery_log(limit=10)
    assert len(logs) == 1
    assert logs[0]["ticker"] == "AMD"


def test_pdt_tracker(db):
    db.record_day_trade("trade-1")
    db.record_day_trade("trade-2")
    count = db.get_day_trade_count(days=5)
    assert count == 2
