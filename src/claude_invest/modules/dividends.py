"""Dividend tracker for core holdings."""

import os
from datetime import datetime, timedelta
from alpaca.trading.client import TradingClient
from dotenv import load_dotenv

from claude_invest.modules.db import Database

load_dotenv()


def get_dividend_history(db: Database, days: int = 90) -> list[dict]:
    """Get dividend payments from Alpaca account activities.

    Alpaca paper trading simulates dividends. Query account activities
    for dividend type entries.
    """
    try:
        client = TradingClient(
            api_key=os.environ["ALPACA_API_KEY"],
            secret_key=os.environ["ALPACA_SECRET_KEY"],
            paper=True,
        )
        activities = client.get_account_activities(activity_types=["DIV"])

        dividends = []
        for act in activities:
            dividends.append({
                "symbol": str(act.symbol) if hasattr(act, 'symbol') else "unknown",
                "amount": float(act.net_amount) if hasattr(act, 'net_amount') else float(act.qty) * float(act.price) if hasattr(act, 'qty') else 0,
                "date": str(act.date) if hasattr(act, 'date') else str(act.transaction_time),
                "qty": float(act.qty) if hasattr(act, 'qty') else 0,
                "per_share": float(act.price) if hasattr(act, 'price') else 0,
            })

        return dividends
    except Exception as e:
        return []


def get_dividend_summary(db: Database, positions: list[dict]) -> dict:
    """Get dividend summary for all positions.

    Returns:
        dict with total_dividends, by_symbol breakdown, annual_yield estimate
    """
    history = get_dividend_history(db)

    by_symbol = {}
    total = 0.0
    for div in history:
        symbol = div["symbol"]
        if symbol not in by_symbol:
            by_symbol[symbol] = {"total": 0.0, "payments": 0, "last_date": None}
        by_symbol[symbol]["total"] += div["amount"]
        by_symbol[symbol]["payments"] += 1
        by_symbol[symbol]["last_date"] = div["date"]
        total += div["amount"]

    # Calculate estimated annual yield for held positions
    position_dividends = []
    total_portfolio_value = sum(p.get("market_value", 0) for p in positions)

    for pos in positions:
        symbol = pos.get("symbol", "")
        if "/" in symbol:  # Skip crypto
            continue
        sym_data = by_symbol.get(symbol, {"total": 0.0, "payments": 0, "last_date": None})
        est_annual = sym_data["total"] * (4 / max(sym_data["payments"], 1)) if sym_data["payments"] > 0 else 0
        position_dividends.append({
            "symbol": symbol,
            "dividends_received": round(sym_data["total"], 4),
            "payment_count": sym_data["payments"],
            "last_payment": sym_data["last_date"],
            "est_annual_dividend": round(est_annual, 4),
            "market_value": pos.get("market_value", 0),
        })

    return {
        "total_dividends_received": round(total, 4),
        "dividend_positions": position_dividends,
        "total_portfolio_value": round(total_portfolio_value, 2),
        "portfolio_yield": round(total / total_portfolio_value * 100, 2) if total_portfolio_value > 0 else 0,
    }
