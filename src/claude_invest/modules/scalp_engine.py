"""
Scalp Engine — entry and exit logic for the Volatility Scalper strategy.

Public API:
    run_scalp_cycle(config: dict, db) -> dict
    check_scalp_exits(config: dict, db) -> list[dict]
"""

import uuid
from datetime import datetime, timezone, timedelta

from claude_invest.modules.technicals import analyze_technicals
from claude_invest.modules.executor import execute_order
from claude_invest.modules.volatility_scanner import scan_volatile_stocks

STRATEGY_ID = "volatility_scalper"


def _current_et_time() -> datetime:
    """Return current UTC time (stub target for test mocking of force-exit clock)."""
    return datetime.now(timezone.utc)


def get_current_price(ticker: str) -> float:
    """Fetch the latest price for a ticker via Alpaca snapshot."""
    import os
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest
    from dotenv import load_dotenv
    load_dotenv()
    client = StockHistoricalDataClient(
        os.environ["ALPACA_API_KEY"],
        os.environ["ALPACA_SECRET_KEY"],
    )
    req = StockLatestQuoteRequest(symbol_or_symbols=ticker)
    quote = client.get_stock_latest_quote(req)
    return float(quote[ticker].ask_price or quote[ticker].bid_price)


def _calculate_shares(config: dict, price: float) -> int:
    """Return whole-share count based on volatility_scalper capital allocation."""
    total_capital = config.get("capital", 5000)
    trading_pct = config.get("capital_split", {}).get("trading", 0.5)
    scalper_pct = config["volatility_scalper"]["capital_pct"]
    max_concurrent = config["volatility_scalper"]["params"]["max_concurrent"]
    per_trade_capital = (total_capital * trading_pct * scalper_pct) / max_concurrent
    return max(1, int(per_trade_capital / price))


def _check_dip_buy_signal(metrics: dict, technicals: dict, params: dict) -> bool:
    intraday_change = metrics.get("intraday_change", 0)
    rsi = technicals.get("rsi") or 100
    return (
        intraday_change <= params["dip_threshold"]
        and rsi < params["rsi_oversold"]
    )


def _check_rally_short_signal(metrics: dict, technicals: dict, params: dict) -> bool:
    intraday_change = metrics.get("intraday_change", 0)
    rsi = technicals.get("rsi") or 0
    return (
        intraday_change >= params["rally_threshold"]
        and rsi > params["rsi_overbought"]
    )


def run_scalp_cycle(config: dict, db) -> dict:
    """
    Run one full scalp cycle: scan candidates, evaluate setups, place trades.

    Returns:
        dict with keys: scanned, signals_found, trades_placed, skipped_reason
    """
    scalper_cfg = config["volatility_scalper"]
    params = scalper_cfg["params"]
    modes = scalper_cfg.get("modes", {})
    max_concurrent = params["max_concurrent"]

    summary = {
        "scanned": 0,
        "signals_found": 0,
        "trades_placed": 0,
        "skipped_reason": [],
    }

    candidates = scan_volatile_stocks(config)
    summary["scanned"] = len(candidates)

    # Count existing open scalp positions
    open_positions = db.get_open_positions_by_strategy(STRATEGY_ID)
    open_tickers = {p["ticker"] for p in open_positions}

    for candidate in candidates:
        ticker = candidate["ticker"]

        # Concurrency guard
        if len(open_positions) >= max_concurrent:
            summary["skipped_reason"].append(
                f"{ticker}: max_concurrent ({max_concurrent}) reached"
            )
            continue

        # Already holding this ticker
        if ticker in open_tickers:
            summary["skipped_reason"].append(f"{ticker}: already holding position")
            continue

        technicals = analyze_technicals(ticker, timeframe=params["bar_timeframe"])

        signal = None
        side = None

        if modes.get("dip_buying") and _check_dip_buy_signal(candidate, technicals, params):
            signal = "dip_buying"
            side = "buy"
        elif modes.get("rally_shorting") and _check_rally_short_signal(candidate, technicals, params):
            signal = "rally_shorting"
            side = "sell_short"

        if not signal:
            summary["skipped_reason"].append(f"{ticker}: no signal")
            continue

        summary["signals_found"] += 1
        price = technicals["current_price"]
        shares = _calculate_shares(config, price)

        order_result = execute_order(ticker, side, shares)
        if order_result.get("status") == "filled":
            db.record_trade({
                "id": str(uuid.uuid4()),
                "ticker": ticker,
                "action": side,
                "shares": shares,
                "price": order_result.get("filled_avg_price", price),
                "strategy_id": STRATEGY_ID,
                "entry_mode": signal,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            open_positions.append({"ticker": ticker})
            open_tickers.add(ticker)
            summary["trades_placed"] += 1

    return summary


def check_scalp_exits(config: dict, db) -> list[dict]:
    """
    Check all open scalp positions for exit conditions.

    Priority order: force_exit > take_profit > stop_loss > max_hold

    Returns:
        List of dicts with: ticker, exit_reason, pnl_pct
    """
    params = config["volatility_scalper"]["params"]
    take_profit_pct = params["take_profit_pct"]
    stop_loss_pct = params["stop_loss_pct"]
    max_hold_minutes = params["max_hold_minutes"]
    force_exit_time_str = params["force_exit_time"]  # "15:55"
    force_hour, force_minute = map(int, force_exit_time_str.split(":"))

    now = _current_et_time()
    force_exit = now.hour > force_hour or (now.hour == force_hour and now.minute >= force_minute)

    open_positions = db.get_open_positions_by_strategy(STRATEGY_ID)
    closed = []

    for position in open_positions:
        ticker = position["ticker"]
        entry_price = position["entry_price"]
        side = position.get("side", "long")
        shares = position.get("shares", 0)
        entry_time = datetime.fromisoformat(position["entry_time"])

        current_price = get_current_price(ticker)
        if side == "long":
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - current_price) / entry_price

        age_minutes = (now - entry_time).total_seconds() / 60

        exit_reason = None

        if force_exit:
            exit_reason = "force_exit"
        elif pnl_pct >= take_profit_pct:
            exit_reason = "take_profit"
        elif pnl_pct <= -stop_loss_pct:
            exit_reason = "stop_loss"
        elif age_minutes >= max_hold_minutes:
            exit_reason = "max_hold"

        if exit_reason:
            close_side = "sell" if side == "long" else "buy_to_cover"
            execute_order(ticker, close_side, shares)
            db.close_position(ticker, STRATEGY_ID, exit_reason)
            closed.append({
                "ticker": ticker,
                "exit_reason": exit_reason,
                "pnl_pct": round(pnl_pct, 4),
            })

    return closed
