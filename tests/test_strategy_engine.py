import json
import pytest
from claude_invest.modules.strategy_engine import (
    get_active_strategies,
    get_strategy_capital,
    tag_decision,
    get_strategy_performance,
    get_all_strategy_performance,
)
from claude_invest.modules.db import Database


@pytest.fixture
def strat_config(sample_config):
    config, _ = sample_config
    config["strategies"] = {
        "active": ["mean_reversion", "momentum"],
        "mean_reversion": {
            "name": "RSI(2) Mean Reversion",
            "enabled": True,
            "capital_pct": 0.50,
            "params": {"rsi_period": 2, "rsi_buy_threshold": 25},
        },
        "momentum": {
            "name": "Momentum",
            "enabled": True,
            "capital_pct": 0.50,
            "params": {"rsi_entry_min": 30},
        },
        "disabled_strat": {
            "name": "Disabled",
            "enabled": False,
            "capital_pct": 0.0,
        },
    }
    return config


def test_get_active_strategies(strat_config):
    strategies = get_active_strategies(strat_config)
    assert len(strategies) == 2
    assert strategies[0]["id"] == "mean_reversion"
    assert strategies[1]["id"] == "momentum"


def test_get_strategy_capital(strat_config):
    capital = get_strategy_capital(strat_config, "mean_reversion")
    assert capital == 2500.0  # 50% of 5000


def test_tag_decision(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()

    decision = {
        "ticker": "AAPL",
        "action": "buy",
        "reasoning": "RSI(2) < 25",
        "signals_snapshot": json.dumps({"rsi": 20}),
    }
    tag_decision(db, decision, "mean_reversion")

    decisions = db.get_decisions()
    assert len(decisions) == 1
    snap = json.loads(decisions[0]["signals_snapshot"])
    assert snap["strategy_id"] == "mean_reversion"
    db.close()


def test_get_strategy_performance(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()

    db.insert_trade({
        "symbol": "AAPL", "side": "buy", "qty": 1, "price": 100,
        "order_id": "t1", "trade_type": "mean_reversion", "status": "filled",
    })
    db.insert_trade({
        "symbol": "AAPL", "side": "sell", "qty": 1, "price": 105,
        "order_id": "t2", "trade_type": "mean_reversion", "status": "filled",
    })
    db.insert_trade({
        "symbol": "BTC", "side": "buy", "qty": 1, "price": 100,
        "order_id": "t3", "trade_type": "momentum", "status": "filled",
    })

    perf = get_strategy_performance(db, "mean_reversion")
    assert perf["total_trades"] == 1  # 1 buy
    assert perf["sells"] == 1
    assert perf["realized_pnl"] == 5.0

    perf2 = get_strategy_performance(db, "momentum")
    assert perf2["total_trades"] == 1
    assert perf2["sells"] == 0
    db.close()


def test_get_all_strategy_performance(tmp_db_path, strat_config):
    db = Database(tmp_db_path)
    db.initialize()
    results = get_all_strategy_performance(db, strat_config)
    assert len(results) == 2
    assert results[0]["name"] == "RSI(2) Mean Reversion"
    db.close()
