import pytest
from claude_invest.modules.db import Database


@pytest.fixture
def db(tmp_db_path):
    database = Database(tmp_db_path)
    database.initialize()
    return database


def test_initialize_creates_tables(db):
    tables = db.list_tables()
    expected = {"trades", "positions", "signals", "decisions", "portfolio_snapshots", "discovery_log", "pdt_tracker", "change_log"}
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


def test_position_id_column_exists(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    conn = db._get_conn()
    cursor = conn.execute("PRAGMA table_info(decisions)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "position_id" in columns
    cursor = conn.execute("PRAGMA table_info(trades)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "position_id" in columns
    db.close()


def test_change_log_table_exists(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    tables = db.list_tables()
    assert "change_log" in tables
    db.close()


def test_insert_decision_with_position_id(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    db.insert_decision({
        "ticker": "BTC/USD", "action": "buy", "reasoning": "test",
        "signals_snapshot": "{}", "position_id": "pos-abc-123",
    })
    decisions = db.get_decisions(limit=1)
    assert decisions[0]["position_id"] == "pos-abc-123"
    db.close()


def test_insert_trade_with_position_id(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    db.insert_trade({
        "symbol": "BTC/USD", "side": "buy", "qty": 0.001, "price": 75000,
        "order_id": "t1", "trade_type": "mean_reversion", "status": "filled",
        "position_id": "pos-abc-123",
    })
    trades = db.get_trades(limit=1)
    assert trades[0]["position_id"] == "pos-abc-123"
    db.close()


def test_insert_change_log(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    db.insert_change_log({
        "parameter_path": "strategies.mean_reversion.params.rsi_buy_threshold",
        "old_value": "25", "new_value": "20",
        "reason": "12 trades show RSI<20 wins 75%",
        "trade_count": 12, "auto_applied": True,
    })
    changes = db.get_change_log()
    assert len(changes) == 1
    assert changes[0]["parameter_path"] == "strategies.mean_reversion.params.rsi_buy_threshold"
    assert changes[0]["auto_applied"] == 1
    db.close()


def test_get_matched_trades_by_position_id(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    db.insert_decision({
        "ticker": "BTC/USD", "action": "buy", "reasoning": "test",
        "signals_snapshot": '{"rsi": 45, "price": 75000}',
        "position_id": "pos-1",
    })
    db.insert_trade({
        "symbol": "BTC/USD", "side": "buy", "qty": 0.001,
        "price": 75000, "order_id": "t1", "trade_type": "momentum",
        "status": "filled", "position_id": "pos-1",
    })
    db.insert_decision({
        "ticker": "BTC/USD", "action": "sell", "reasoning": "take profit",
        "signals_snapshot": '{"rsi": 65, "price": 76000}',
        "position_id": "pos-1",
    })
    db.insert_trade({
        "symbol": "BTC/USD", "side": "sell", "qty": 0.001,
        "price": 76000, "order_id": "t2", "trade_type": "momentum",
        "status": "filled", "position_id": "pos-1",
    })
    matched = db.get_matched_trades()
    assert len(matched) == 1
    assert matched[0]["position_id"] == "pos-1"
    assert matched[0]["entry_price"] == 75000
    assert matched[0]["exit_price"] == 76000
    db.close()
