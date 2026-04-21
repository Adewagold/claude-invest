from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from claude_invest.config.loader import load_config
from claude_invest.modules.db import Database
from claude_invest.modules.portfolio import get_portfolio
from claude_invest.modules.learner import analyze_day
from claude_invest.modules.portfolio_tracker import get_allocation
from claude_invest.modules.strategy import load_lessons

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

    return app


if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
