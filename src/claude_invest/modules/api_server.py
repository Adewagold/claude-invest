from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from claude_invest.config.loader import load_config
from claude_invest.modules.db import Database
from claude_invest.modules.portfolio import get_portfolio
from claude_invest.modules.learner import analyze_day
from claude_invest.modules.portfolio_tracker import get_allocation
from claude_invest.modules.strategy import load_lessons
from claude_invest.modules.watchlist import load_watchlist, add_to_watchlist, remove_from_watchlist
from claude_invest.modules.strategy_engine import get_active_strategies, get_all_strategy_performance

DEFAULT_DB_PATH = "claude_invest.db"


def create_app(db_path: str = DEFAULT_DB_PATH) -> FastAPI:
    app = FastAPI(title="Claude Invest API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_db() -> Database:
        db = Database(db_path)
        db.initialize()
        return db

    @app.get("/api/trades")
    def get_trades(limit: int = 100):
        db = get_db()
        result = db.get_trades(limit=limit)
        db.close()
        return result

    @app.get("/api/decisions")
    def get_decisions(limit: int = 50):
        db = get_db()
        result = db.get_decisions(limit=limit)
        db.close()
        return result

    @app.get("/api/portfolio")
    def get_portfolio_snapshots(limit: int = 100):
        db = get_db()
        result = db.get_portfolio_snapshots(limit=limit)
        db.close()
        return result

    @app.get("/api/discovery")
    def get_discovery(limit: int = 50):
        db = get_db()
        result = db.get_discovery_log(limit=limit)
        db.close()
        return result

    @app.get("/api/signals/{ticker}")
    def get_signals(ticker: str, limit: int = 50):
        db = get_db()
        result = db.get_signals(ticker=ticker, limit=limit)
        db.close()
        return result

    @app.get("/api/positions")
    def get_positions():
        return get_portfolio()

    @app.get("/api/config")
    def get_config():
        return load_config()

    @app.put("/api/config")
    def update_config(new_config: dict):
        import yaml
        from claude_invest.config.loader import DEFAULT_CONFIG_PATH
        with open(DEFAULT_CONFIG_PATH, "w") as f:
            yaml.dump(new_config, f, default_flow_style=False)
        return {"status": "updated"}

    @app.get("/api/stats")
    def get_stats():
        db = get_db()
        snapshots = db.get_portfolio_snapshots(limit=30)
        db.close()
        if not snapshots:
            return {"daily_pnl": 0, "total_snapshots": 0}
        return {
            "latest_value": snapshots[0]["total_value"],
            "latest_daily_pnl": snapshots[0]["daily_pnl"],
            "total_snapshots": len(snapshots),
        }

    @app.get("/api/review-day")
    def api_review_day(date: str | None = None):
        db = get_db()
        report = analyze_day(db, date)
        db.close()
        return report

    @app.get("/api/allocation")
    def api_allocation():
        config = load_config()
        portfolio_data = get_portfolio()
        allocation = get_allocation(config, portfolio_data["positions"])
        return allocation

    @app.get("/api/lessons")
    def api_lessons():
        return load_lessons("lessons")

    @app.get("/api/strategy-brief")
    def api_strategy_brief():
        import os
        path = os.path.join("lessons", "strategy-brief.md")
        if os.path.exists(path):
            with open(path) as f:
                return {"brief": f.read()}
        return {"brief": "No strategy brief yet. Run review-day first."}

    @app.get("/api/watchlist")
    def api_watchlist():
        return {"watchlist": load_watchlist(), "count": len(load_watchlist())}

    @app.post("/api/watchlist")
    def api_watchlist_add(body: dict):
        symbol = body.get("symbol", "")
        note = body.get("note", "")
        return add_to_watchlist(symbol, note)

    @app.delete("/api/watchlist/{symbol}")
    def api_watchlist_remove(symbol: str):
        return remove_from_watchlist(symbol)

    @app.get("/api/strategies")
    def api_strategies():
        config = load_config()
        db = get_db()
        results = get_all_strategy_performance(db, config)
        db.close()
        return {"strategies": results}

    @app.get("/api/learning/report")
    def api_learning_report():
        db = get_db()
        from claude_invest.modules.learner import _match_trades
        from claude_invest.modules.pattern_analyzer import analyze_patterns
        matched = _match_trades(db)
        closed = [m for m in matched if m["status"] == "closed"]
        report = analyze_patterns(closed)
        db.close()
        return report

    @app.get("/api/learning/changes")
    def api_learning_changes():
        db = get_db()
        changes = db.get_change_log()
        db.close()
        return {"changes": changes}

    @app.get("/api/learning/performance")
    def api_learning_performance():
        db = get_db()
        from claude_invest.modules.learner import _match_trades
        from collections import defaultdict
        matched = _match_trades(db)
        closed = [m for m in matched if m["status"] == "closed"]
        daily = defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0.0})
        for t in closed:
            date = (t.get("entry_time") or "")[:10]
            if t["win"]:
                daily[date]["wins"] += 1
            else:
                daily[date]["losses"] += 1
            daily[date]["pnl"] += t["pnl"]
        series = [
            {"date": d, "wins": v["wins"], "losses": v["losses"],
             "pnl": round(v["pnl"], 2),
             "win_rate": round(v["wins"] / (v["wins"] + v["losses"]), 4) if (v["wins"] + v["losses"]) > 0 else 0}
            for d, v in sorted(daily.items())
        ]
        db.close()
        return {"series": series}

    @app.post("/api/learning/revert/{change_id}")
    def api_revert_change(change_id: int):
        db = get_db()
        changes = db.get_change_log()
        change = next((c for c in changes if c["id"] == change_id), None)
        if not change:
            db.close()
            return {"error": f"Change {change_id} not found"}
        db.revert_change(change_id, "Manual revert via dashboard")
        db.close()
        return {"status": "reverted", "change_id": change_id}

    @app.get("/api/core/status")
    def api_core_status():
        config = load_config()
        db = get_db()
        from claude_invest.modules.core_engine import get_core_status
        portfolio_data = get_portfolio()
        status = get_core_status(config, db, portfolio_data)
        db.close()
        return status

    @app.get("/api/core/schedule")
    def api_core_schedule():
        config = load_config()
        db = get_db()
        core_config = config.get("core_holdings", {})
        buy_list = core_config.get("buy_list", [])
        dca_interval = core_config.get("entry", {}).get("dca_interval_days", 7)
        schedule = []
        for item in buy_list:
            symbol = item["symbol"]
            last_buy = db.get_last_core_buy_date(symbol)
            if last_buy:
                from datetime import datetime, timedelta
                last_dt = datetime.fromisoformat(last_buy)
                next_buy = last_dt + timedelta(days=dca_interval)
                days_since = (datetime.utcnow() - last_dt).days
                due = days_since >= dca_interval
            else:
                next_buy = None
                days_since = None
                due = True
            schedule.append({
                "symbol": symbol,
                "sector": item.get("sector"),
                "weight": item.get("weight"),
                "last_buy_date": last_buy,
                "days_since_buy": days_since,
                "next_buy_date": next_buy.isoformat() if next_buy else "ASAP",
                "due": due,
            })
        db.close()
        return {"schedule": schedule}

    @app.get("/api/core/rebalance-preview")
    def api_core_rebalance_preview():
        config = load_config()
        db = get_db()
        from claude_invest.modules.core_engine import rebalance_core
        portfolio_data = get_portfolio()
        preview = rebalance_core(config, db, portfolio_data, dry_run=True)
        db.close()
        return {"preview": preview}

    @app.get("/api/scalp/candidates")
    def api_scalp_candidates():
        config = load_config()
        from claude_invest.modules.volatility_scanner import scan_volatile_stocks
        candidates = scan_volatile_stocks(config)
        return {"candidates": candidates}

    @app.get("/api/scalp/status")
    def api_scalp_status():
        portfolio_data = get_portfolio()
        config = load_config()
        watchlist = config.get("volatility_scalper", {}).get("watchlist", [])
        scalp_positions = [p for p in portfolio_data.get("positions", []) if p.get("symbol") in watchlist]
        return {"scalp_positions": scalp_positions}

    return app


if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
