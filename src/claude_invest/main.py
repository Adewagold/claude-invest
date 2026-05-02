import json
import sys
import uuid
from collections import defaultdict

from claude_invest.config.loader import load_config
from claude_invest.modules.db import Database
from claude_invest.modules.portfolio import get_portfolio
from claude_invest.modules.scanner import scan_market
from claude_invest.modules.sentiment import analyze_sentiment
from claude_invest.modules.technicals import analyze_technicals
from claude_invest.modules.risk_manager import RiskManager
from claude_invest.modules.executor import execute_order
from claude_invest.modules.learner import analyze_day, score_patterns
from claude_invest.modules.portfolio_tracker import get_allocation
from claude_invest.modules.strategy import update_lessons, build_strategy_brief, load_lessons
from claude_invest.modules.watchlist import load_watchlist, add_to_watchlist, remove_from_watchlist, check_watchlist
from claude_invest.modules.strategy_engine import get_active_strategies, get_all_strategy_performance

DB_PATH = "claude_invest.db"
LESSONS_DIR = "lessons"


def _output(data: dict):
    print(json.dumps(data, indent=2, default=str))


def cmd_portfolio():
    result = get_portfolio()
    db = Database(DB_PATH)
    db.initialize()
    db.insert_portfolio_snapshot({
        "total_value": result["equity"],
        "cash": result["cash"],
        "positions_value": result["equity"] - result["cash"],
        "daily_pnl": result["daily_pnl"],
    })
    db.close()
    _output(result)


def cmd_scan():
    config = load_config()
    results = scan_market(config)
    db = Database(DB_PATH)
    db.initialize()
    for r in results:
        db.insert_discovery({
            "ticker": r["ticker"],
            "volume_score": r["volume_ratio"],
            "news_score": r.get("sentiment_score", 0),
            "sentiment": r.get("sentiment_score", 0),
            "action_taken": "flagged" if r["flagged"] else "skipped",
        })
    db.close()
    _output({"candidates": results})


def cmd_analyze(ticker: str):
    sentiment = analyze_sentiment(ticker)
    technicals = analyze_technicals(ticker)
    db = Database(DB_PATH)
    db.initialize()
    db.insert_signal({
        "ticker": ticker,
        "sentiment_score": sentiment["score"],
        "rsi": technicals.get("rsi"),
        "macd": technicals.get("macd"),
        "volume_ratio": None,
        "trend": technicals.get("trend"),
    })
    db.close()
    _output({
        "ticker": ticker,
        "sentiment": sentiment,
        "technicals": technicals,
    })


def cmd_risk_check(ticker: str, qty: float, price: float):
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    risk_mgr = RiskManager(config, db)
    portfolio = get_portfolio()
    result = risk_mgr.check_trade(ticker, qty, price, portfolio)
    result["position_size_suggested"] = risk_mgr.calculate_position_size(price)
    result["pdt_allowed"] = risk_mgr.check_pdt_allowed()
    db.close()
    _output(result)


def cmd_execute(side: str, ticker: str, qty: float, position_id: str | None = None):
    result = execute_order(symbol=ticker, side=side, qty=qty)
    db = Database(DB_PATH)
    db.initialize()
    if result["status"] != "error":
        db.insert_trade({
            "symbol": ticker, "side": side, "qty": qty,
            "price": result.get("filled_price") or 0,
            "order_id": result["order_id"],
            "trade_type": "market",
            "status": result["status"],
            "position_id": position_id,
        })
    db.close()
    _output(result)


def cmd_log_decision(payload_json: str):
    payload = json.loads(payload_json)
    db = Database(DB_PATH)
    db.initialize()
    if payload.get("action") == "buy" and "position_id" not in payload:
        payload["position_id"] = str(uuid.uuid4())
    db.insert_decision(payload)
    db.close()
    _output({"status": "logged", "decision": payload})


def cmd_review_day(date: str | None = None):
    config = load_config()
    from claude_invest.config.loader import DEFAULT_CONFIG_PATH
    db = Database(DB_PATH)
    db.initialize()

    from claude_invest.modules.learner import _match_trades
    matched = _match_trades(db)
    closed = [m for m in matched if m["status"] == "closed"]

    from claude_invest.modules.pattern_analyzer import analyze_patterns
    learning_report = analyze_patterns(closed)

    trades_by_strategy = defaultdict(list)
    for t in closed:
        sid = t.get("strategy_id") or "unknown"
        trades_by_strategy[sid].append(t)

    from claude_invest.modules.optimizer import (
        evaluate_parameters, apply_change, check_evaluation_windows, can_apply_more_changes
    )
    reverted = check_evaluation_windows(db, dict(trades_by_strategy), DEFAULT_CONFIG_PATH)
    proposals = evaluate_parameters(dict(trades_by_strategy), config)

    applied = []
    proposed = []
    for p in proposals:
        if p["auto_applied"] and can_apply_more_changes(db):
            apply_change(config_path=str(DEFAULT_CONFIG_PATH), db=db, **p)
            applied.append(p)
        else:
            p["auto_applied"] = False
            db.insert_change_log(p)
            proposed.append(p)

    dimension_insights = {}
    if learning_report["time_of_day"]:
        best_time = max(learning_report["time_of_day"], key=lambda x: x.get("win_rate", 0))
        if best_time.get("total", 0) >= 5:
            dimension_insights["best_time"] = best_time
    if learning_report["hold_duration"]:
        best_dur = max(learning_report["hold_duration"], key=lambda x: x.get("win_rate", 0))
        if best_dur.get("total", 0) >= 5:
            dimension_insights["best_duration"] = best_dur

    try:
        from claude_invest.modules.portfolio import get_portfolio
        portfolio = get_portfolio()
        allocation = get_allocation(config, portfolio["positions"])
    except Exception:
        allocation = {"tiers": {}, "total_value": 0}

    active_changes = db.get_active_changes()

    report = analyze_day(db, date)
    update_lessons(LESSONS_DIR, report["patterns"], report["date"])
    brief = build_strategy_brief(
        LESSONS_DIR, allocation,
        dimension_insights=dimension_insights,
        active_changes=active_changes,
        proposed_changes=proposed,
    )

    _write_daily_report(report, learning_report, applied, proposed, reverted)

    report["learning_report"] = learning_report
    report["applied_changes"] = applied
    report["proposed_changes"] = proposed
    report["reverted_changes"] = reverted
    report["allocation"] = allocation
    report["strategy_brief"] = brief
    db.close()
    _output(report)


def _write_daily_report(report: dict, learning_report: dict,
                        applied: list, proposed: list, reverted: list):
    import os
    date = report.get("date", "unknown")
    daily_path = os.path.join(LESSONS_DIR, "daily", f"{date}.md")
    os.makedirs(os.path.dirname(daily_path), exist_ok=True)

    lines = [f"# Daily Learning Report — {date}", ""]
    lines.append("## Performance Summary")
    lines.append(f"- Trades closed: {report['total_trades']} ({report['wins']}W/{report['losses']}L)")
    lines.append(f"- Total P&L: ${report['total_pnl']:.2f}")
    lines.append(f"- Win rate: {report['win_rate']:.0%}")
    lines.append("")

    lines.append("## Dimension Analysis")
    if learning_report.get("time_of_day"):
        lines.append("### Time-of-Day")
        lines.append("| Window | W/L | Avg P&L | Win Rate |")
        lines.append("|--------|-----|---------|----------|")
        for b in learning_report["time_of_day"]:
            lines.append(f"| {b['bucket']} | {b['wins']}W/{b['losses']}L | ${b['avg_pnl']:.2f} | {b['win_rate']:.0%} |")
        lines.append("")

    if learning_report.get("hold_duration"):
        lines.append("### Hold Duration")
        lines.append("| Bucket | W/L | Avg P&L | Win Rate |")
        lines.append("|--------|-----|---------|----------|")
        for b in learning_report["hold_duration"]:
            lines.append(f"| {b['bucket']} | {b['wins']}W/{b['losses']}L | ${b['avg_pnl']:.2f} | {b['win_rate']:.0%} |")
        lines.append("")

    if learning_report.get("asset_class"):
        lines.append("### Asset Class x Strategy")
        lines.append("| Class | Strategy | W/L | Win Rate |")
        lines.append("|-------|----------|-----|----------|")
        for a in learning_report["asset_class"]:
            lines.append(f"| {a['asset_class']} | {a['strategy_id']} | {a['wins']}W/{a['losses']}L | {a['win_rate']:.0%} |")
        lines.append("")

    if applied or proposed or reverted:
        lines.append("## Parameter Changes")
        for c in applied:
            lines.append(f"- AUTO-APPLIED: {c['parameter_path']}: {c['old_value']} → {c['new_value']} ({c['reason']})")
        for c in proposed:
            lines.append(f"- PROPOSED: {c['parameter_path']}: {c['old_value']} → {c['new_value']} ({c['reason']})")
        for c in reverted:
            lines.append(f"- REVERTED: {c.get('parameter_path', 'unknown')} (failed evaluation)")
        lines.append("")

    with open(daily_path, "w") as f:
        f.write("\n".join(lines))


def cmd_learning_report():
    db = Database(DB_PATH)
    db.initialize()
    from claude_invest.modules.learner import _match_trades
    from claude_invest.modules.pattern_analyzer import analyze_patterns
    matched = _match_trades(db)
    closed = [m for m in matched if m["status"] == "closed"]
    report = analyze_patterns(closed)
    db.close()
    _output(report)


def cmd_change_log():
    db = Database(DB_PATH)
    db.initialize()
    changes = db.get_change_log()
    db.close()
    _output({"changes": changes, "count": len(changes)})


def cmd_revert_change(change_id: int):
    db = Database(DB_PATH)
    db.initialize()
    from claude_invest.config.loader import DEFAULT_CONFIG_PATH
    from claude_invest.modules.optimizer import apply_change
    changes = db.get_change_log()
    change = next((c for c in changes if c["id"] == change_id), None)
    if change:
        apply_change(
            config_path=str(DEFAULT_CONFIG_PATH),
            db=db,
            parameter_path=change["parameter_path"],
            old_value=change["new_value"],
            new_value=change["old_value"],
            reason="Manual revert",
            trade_count=change.get("trade_count", 0),
            auto_applied=False,
        )
        db.revert_change(change_id, reason="Manual revert")
        _output({"status": "reverted", "change_id": change_id})
    else:
        _output({"error": f"Change {change_id} not found"})
    db.close()


def cmd_allocation():
    config = load_config()
    from claude_invest.modules.portfolio import get_portfolio
    portfolio = get_portfolio()
    allocation = get_allocation(config, portfolio["positions"])
    _output(allocation)


def cmd_lessons():
    lessons = load_lessons(LESSONS_DIR)
    _output(lessons)


def cmd_watchlist():
    tickers = load_watchlist()
    portfolio = get_portfolio()
    portfolio_symbols = [p["symbol"] for p in portfolio["positions"]]
    checked = check_watchlist(tickers, portfolio_symbols)
    _output({"watchlist": checked, "count": len(checked)})


def cmd_watchlist_add(symbol: str, note: str = ""):
    result = add_to_watchlist(symbol, note)
    _output(result)


def cmd_watchlist_remove(symbol: str):
    result = remove_from_watchlist(symbol)
    _output(result)


def cmd_strategies():
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    results = get_all_strategy_performance(db, config)
    strategies = get_active_strategies(config)
    db.close()
    _output({
        "strategies": results,
        "active_count": len(strategies),
    })


def cmd_core_status():
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    from claude_invest.modules.core_engine import get_core_status
    from claude_invest.modules.portfolio import get_portfolio
    portfolio = get_portfolio()
    status = get_core_status(config, db, portfolio)
    db.close()
    _output(status)


def cmd_core_cycle():
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    from claude_invest.modules.core_engine import run_core_cycle
    result = run_core_cycle(config, db)
    db.close()
    _output(result)


def cmd_core_buy(symbol: str):
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    from claude_invest.modules.core_engine import run_core_cycle
    # Override: force buy this symbol by running cycle with just this stock
    from claude_invest.modules.technicals import analyze_technicals
    from claude_invest.modules.executor import execute_order
    from claude_invest.modules.risk_manager import RiskManager
    risk_mgr = RiskManager(config, db)
    qty = risk_mgr.calculate_core_position_size(
        analyze_technicals(symbol)["current_price"], config)
    if qty > 0:
        result = execute_order(symbol=symbol, side="buy", qty=qty)
        if result.get("status") != "error":
            db.insert_core_buy({
                "symbol": symbol, "qty": qty,
                "price": result.get("filled_price") or analyze_technicals(symbol)["current_price"],
                "cost_basis": qty * (result.get("filled_price") or 0),
                "order_id": result.get("order_id"),
            })
        _output(result)
    else:
        _output({"error": "Position size too small"})
    db.close()


def cmd_core_add(symbol: str, sector: str, weight: float):
    from ruamel.yaml import YAML
    from claude_invest.config.loader import DEFAULT_CONFIG_PATH
    yaml = YAML()
    yaml.preserve_quotes = True
    with open(DEFAULT_CONFIG_PATH) as f:
        config = yaml.load(f)
    buy_list = config.get("core_holdings", {}).get("buy_list", [])
    # Check if already exists
    if any(item["symbol"] == symbol for item in buy_list):
        _output({"error": f"{symbol} already in buy list"})
        return
    buy_list.append({"symbol": symbol, "sector": sector, "weight": weight})
    config["core_holdings"]["buy_list"] = buy_list
    with open(DEFAULT_CONFIG_PATH, "w") as f:
        yaml.dump(config, f)
    _output({"status": "added", "symbol": symbol, "sector": sector, "weight": weight})


def cmd_core_remove(symbol: str):
    from ruamel.yaml import YAML
    from claude_invest.config.loader import DEFAULT_CONFIG_PATH
    yaml = YAML()
    yaml.preserve_quotes = True
    with open(DEFAULT_CONFIG_PATH) as f:
        config = yaml.load(f)
    buy_list = config.get("core_holdings", {}).get("buy_list", [])
    new_list = [item for item in buy_list if item["symbol"] != symbol]
    if len(new_list) == len(buy_list):
        _output({"error": f"{symbol} not found in buy list"})
        return
    config["core_holdings"]["buy_list"] = new_list
    with open(DEFAULT_CONFIG_PATH, "w") as f:
        yaml.dump(config, f)
    _output({"status": "removed", "symbol": symbol, "note": "Will be sold on next core cycle"})


def cmd_core_rebalance():
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    from claude_invest.modules.core_engine import rebalance_core
    from claude_invest.modules.portfolio import get_portfolio
    portfolio = get_portfolio()
    result = rebalance_core(config, db, portfolio)
    db.close()
    _output({"rebalanced": result})


def cmd_scalp_cycle():
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    from claude_invest.modules.scalp_engine import run_scalp_cycle
    result = run_scalp_cycle(config, db)
    db.close()
    _output(result)


def cmd_scalp_scan():
    config = load_config()
    from claude_invest.modules.volatility_scanner import scan_volatile_stocks
    candidates = scan_volatile_stocks(config)
    _output({"candidates": candidates, "count": len(candidates)})


def cmd_scalp_status():
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    from claude_invest.modules.scalp_engine import check_scalp_exits
    from claude_invest.modules.portfolio import get_portfolio
    portfolio = get_portfolio()
    # Get scalp positions (filter by strategy)
    scalp_positions = [p for p in portfolio.get("positions", []) if p.get("symbol") in config.get("volatility_scalper", {}).get("watchlist", [])]
    db.close()
    _output({"scalp_positions": scalp_positions, "count": len(scalp_positions)})


def cmd_trailing_status():
    from claude_invest.modules.trailing_stop import get_all_peaks
    from claude_invest.modules.portfolio import get_portfolio
    portfolio = get_portfolio()
    peaks = get_all_peaks()
    status = []
    for p in portfolio["positions"]:
        symbol = p["symbol"]
        peak = peaks.get(symbol, p["current_price"])
        drop = (peak - p["current_price"]) / peak if peak > 0 else 0
        status.append({
            "symbol": symbol,
            "current": p["current_price"],
            "entry": p["avg_entry_price"],
            "peak": peak,
            "drop_from_peak": round(drop, 4),
        })
    _output({"trailing_stops": status})


def main():
    if len(sys.argv) < 2:
        _output({"error": "Usage: claude-invest <command> [args]", "commands": [
            "portfolio", "scan", "analyze <ticker>", "risk-check <ticker> <qty> <price>",
            "execute <buy|sell> <ticker> <qty>", "log-decision <json>",
            "review-day [date]", "allocation", "lessons",
            "watchlist", "watchlist-add <symbol> [note]", "watchlist-remove <symbol>",
            "strategies",
            "learning-report", "change-log", "revert-change <change_id>",
            "core-status", "core-cycle", "core-buy <symbol>",
            "core-add <symbol> <sector> <weight>", "core-remove <symbol>", "core-rebalance",
            "scalp-cycle", "scalp-scan", "scalp-status",
            "trailing-status",
        ]})
        sys.exit(1)

    command = sys.argv[1]

    if command == "portfolio":
        cmd_portfolio()
    elif command == "scan":
        cmd_scan()
    elif command == "analyze" and len(sys.argv) >= 3:
        cmd_analyze(sys.argv[2])
    elif command == "risk-check" and len(sys.argv) >= 5:
        cmd_risk_check(sys.argv[2], float(sys.argv[3]), float(sys.argv[4]))
    elif command == "execute" and len(sys.argv) >= 5:
        cmd_execute(sys.argv[2], sys.argv[3], float(sys.argv[4]))
    elif command == "log-decision" and len(sys.argv) >= 3:
        cmd_log_decision(sys.argv[2])
    elif command == "review-day":
        cmd_review_day(sys.argv[2] if len(sys.argv) >= 3 else None)
    elif command == "allocation":
        cmd_allocation()
    elif command == "lessons":
        cmd_lessons()
    elif command == "watchlist":
        cmd_watchlist()
    elif command == "watchlist-add" and len(sys.argv) >= 3:
        note = sys.argv[3] if len(sys.argv) >= 4 else ""
        cmd_watchlist_add(sys.argv[2], note)
    elif command == "watchlist-remove" and len(sys.argv) >= 3:
        cmd_watchlist_remove(sys.argv[2])
    elif command == "strategies":
        cmd_strategies()
    elif command == "learning-report":
        cmd_learning_report()
    elif command == "change-log":
        cmd_change_log()
    elif command == "revert-change" and len(sys.argv) >= 3:
        cmd_revert_change(int(sys.argv[2]))
    elif command == "core-status":
        cmd_core_status()
    elif command == "core-cycle":
        cmd_core_cycle()
    elif command == "core-buy" and len(sys.argv) >= 3:
        cmd_core_buy(sys.argv[2])
    elif command == "core-add" and len(sys.argv) >= 5:
        cmd_core_add(sys.argv[2], sys.argv[3], float(sys.argv[4]))
    elif command == "core-remove" and len(sys.argv) >= 3:
        cmd_core_remove(sys.argv[2])
    elif command == "core-rebalance":
        cmd_core_rebalance()
    elif command == "scalp-cycle":
        cmd_scalp_cycle()
    elif command == "scalp-scan":
        cmd_scalp_scan()
    elif command == "scalp-status":
        cmd_scalp_status()
    elif command == "trailing-status":
        cmd_trailing_status()
    else:
        _output({"error": f"Unknown command or missing args: {command}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
