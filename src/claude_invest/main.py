import json
import sys

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


def cmd_risk_check(ticker: str, qty: int, price: float):
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


def cmd_execute(side: str, ticker: str, qty: float):
    result = execute_order(symbol=ticker, side=side, qty=qty)
    db = Database(DB_PATH)
    db.initialize()
    if result["status"] != "error":
        db.insert_trade({
            "symbol": ticker,
            "side": side,
            "qty": qty,
            "price": result.get("filled_price") or 0,
            "order_id": result["order_id"],
            "trade_type": "market",
            "status": result["status"],
        })
    db.close()
    _output(result)


def cmd_log_decision(payload_json: str):
    payload = json.loads(payload_json)
    db = Database(DB_PATH)
    db.initialize()
    db.insert_decision(payload)
    db.close()
    _output({"status": "logged", "decision": payload})


def cmd_review_day(date: str | None = None):
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    report = analyze_day(db, date)
    from claude_invest.modules.portfolio import get_portfolio
    try:
        portfolio = get_portfolio()
        allocation = get_allocation(config, portfolio["positions"])
    except Exception:
        allocation = {"tiers": {}, "total_value": 0}
    update_lessons(LESSONS_DIR, report["patterns"], report["date"])
    brief = build_strategy_brief(LESSONS_DIR, allocation)
    report["allocation"] = allocation
    report["strategy_brief"] = brief
    db.close()
    _output(report)


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


def main():
    if len(sys.argv) < 2:
        _output({"error": "Usage: claude-invest <command> [args]", "commands": [
            "portfolio", "scan", "analyze <ticker>", "risk-check <ticker> <qty> <price>",
            "execute <buy|sell> <ticker> <qty>", "log-decision <json>",
            "review-day [date]", "allocation", "lessons",
            "watchlist", "watchlist-add <symbol> [note]", "watchlist-remove <symbol>",
            "strategies",
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
        cmd_risk_check(sys.argv[2], int(sys.argv[3]), float(sys.argv[4]))
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
    else:
        _output({"error": f"Unknown command or missing args: {command}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
