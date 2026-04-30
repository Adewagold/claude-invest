import json
from datetime import datetime, timezone
from claude_invest.config.loader import load_config
from claude_invest.modules.db import Database


def get_active_strategies(config: dict) -> list[dict]:
    """Return list of active strategy configs."""
    strategies_config = config.get("strategies", {})
    active_names = strategies_config.get("active", [])

    strategies = []
    for name in active_names:
        strat = strategies_config.get(name, {})
        if strat.get("enabled", True):
            strat["id"] = name
            strategies.append(strat)
    return strategies


def get_strategy_capital(config: dict, strategy_id: str) -> float:
    """Calculate capital allocated to a strategy."""
    total_capital = config.get("capital", 5000)
    capital_split = config.get("capital_split")
    if capital_split:
        trading_capital = total_capital * capital_split.get("trading", 1.0)
    else:
        trading_capital = total_capital
    strategies_config = config.get("strategies", {})
    strat = strategies_config.get(strategy_id, {})
    return trading_capital * strat.get("capital_pct", 0.33)


def tag_trade(db: Database, trade_data: dict, strategy_id: str):
    """Insert a trade tagged with strategy_id."""
    trade_data["trade_type"] = strategy_id
    db.insert_trade(trade_data)


def tag_decision(db: Database, decision_data: dict, strategy_id: str):
    """Insert a decision tagged with strategy_id."""
    # Embed strategy_id in the signals_snapshot
    try:
        snapshot = json.loads(decision_data.get("signals_snapshot", "{}"))
    except (json.JSONDecodeError, TypeError):
        snapshot = {}
    snapshot["strategy_id"] = strategy_id
    decision_data["signals_snapshot"] = json.dumps(snapshot)
    db.insert_decision(decision_data)


def get_strategy_performance(db: Database, strategy_id: str) -> dict:
    """Calculate performance metrics for a specific strategy."""
    trades = db.get_trades(limit=500)
    decisions = db.get_decisions(limit=500)

    # Filter trades by strategy (stored in trade_type field)
    strat_trades = [t for t in trades if t.get("trade_type") == strategy_id]

    buys = [t for t in strat_trades if t["side"] == "buy"]
    sells = [t for t in strat_trades if t["side"] == "sell"]

    total_bought = sum(t["qty"] * t["price"] for t in buys if t["price"])
    total_sold = sum(t["qty"] * t["price"] for t in sells if t["price"])

    realized_pnl = total_sold - total_bought if sells else 0
    trade_count = len(buys)

    # Count wins/losses from decisions
    strat_decisions = []
    for d in decisions:
        try:
            snap = json.loads(d.get("signals_snapshot", "{}"))
            if snap.get("strategy_id") == strategy_id:
                strat_decisions.append(d)
        except (json.JSONDecodeError, TypeError):
            pass

    buy_decisions = [d for d in strat_decisions if d["action"] == "buy"]
    sell_decisions = [d for d in strat_decisions if d["action"] == "sell"]

    return {
        "strategy_id": strategy_id,
        "total_trades": trade_count,
        "buys": len(buys),
        "sells": len(sells),
        "realized_pnl": round(realized_pnl, 2),
        "decisions_logged": len(strat_decisions),
    }


def get_all_strategy_performance(db: Database, config: dict) -> list[dict]:
    """Get performance for all active strategies."""
    strategies = get_active_strategies(config)
    results = []
    for strat in strategies:
        perf = get_strategy_performance(db, strat["id"])
        perf["name"] = strat.get("name", strat["id"])
        perf["capital_pct"] = strat.get("capital_pct", 0.33)
        perf["description"] = strat.get("description", "")
        perf["enabled"] = strat.get("enabled", True)
        results.append(perf)
    return results
