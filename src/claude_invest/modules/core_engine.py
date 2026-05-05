"""
Core Holdings Engine
====================
Manages long-term buy-and-hold positions using DCA with dip entries.
Uses sentiment-only exits and quarterly rebalancing.
NEVER sells on RSI/MACD technical signals.
"""
import logging
from datetime import datetime, timedelta, timezone

from claude_invest.modules.db import Database
from claude_invest.modules.executor import execute_order
from claude_invest.modules.portfolio import get_portfolio
from claude_invest.modules.risk_manager import RiskManager
from claude_invest.modules.technicals import analyze_technicals

logger = logging.getLogger(__name__)


def get_core_status(config: dict, db: Database, portfolio: dict) -> dict:
    """Return current state of core holdings.

    Returns:
        dict with keys:
          - core_capital: total capital allocated to core holdings
          - holdings: list of {symbol, cost_basis, qty, current_value, weight, target_weight, drift}
          - next_rebalance_date: ISO string of when rebalance is due
          - cash_remaining: cash left in core pool
    """
    core_cfg = config.get("core_holdings", {})
    capital_split = config.get("capital_split", {})
    core_capital = config["capital"] * capital_split.get("core", 0.0)

    buy_list = core_cfg.get("buy_list", [])
    buy_list_by_symbol = {item["symbol"]: item for item in buy_list}

    rebalance_interval_days = core_cfg.get("rebalance", {}).get("interval_days", 90)

    # Aggregate cost basis from core_buys
    all_core_buys = db.get_core_buys()
    cost_basis_by_symbol: dict[str, float] = {}
    qty_by_symbol: dict[str, float] = {}
    for buy in all_core_buys:
        sym = buy["symbol"]
        cost_basis_by_symbol[sym] = cost_basis_by_symbol.get(sym, 0.0) + buy["cost_basis"]
        qty_by_symbol[sym] = qty_by_symbol.get(sym, 0.0) + buy["qty"]

    # Match against live portfolio positions for current_value
    positions_by_symbol = {p["symbol"]: p for p in portfolio.get("positions", [])}

    # Determine current total core value from positions that appear in the buy_list
    total_core_value = 0.0
    holdings = []
    for symbol, bl_item in buy_list_by_symbol.items():
        pos = positions_by_symbol.get(symbol)
        current_value = pos["market_value"] if pos else 0.0
        total_core_value += current_value

    # Build holdings list with weight and drift
    for symbol, bl_item in buy_list_by_symbol.items():
        pos = positions_by_symbol.get(symbol)
        current_value = pos["market_value"] if pos else 0.0
        cost_basis = cost_basis_by_symbol.get(symbol, 0.0)
        qty = qty_by_symbol.get(symbol, 0.0)
        target_weight = bl_item.get("weight", 0.0)

        if total_core_value > 0:
            actual_weight = current_value / total_core_value
        else:
            actual_weight = 0.0

        drift = actual_weight - target_weight

        holdings.append({
            "symbol": symbol,
            "sector": bl_item.get("sector"),
            "target_weight": target_weight,
            "cost_basis": cost_basis,
            "qty": qty,
            "current_value": current_value,
            "weight": actual_weight,
            "drift": drift,
        })

    # Determine next rebalance date from the last rebalance log entry
    rebalance_log = db.get_rebalance_log(limit=1)
    if rebalance_log:
        last_rebalance_ts = rebalance_log[0]["timestamp"]
        last_rebalance_dt = datetime.fromisoformat(last_rebalance_ts)
        if last_rebalance_dt.tzinfo is None:
            last_rebalance_dt = last_rebalance_dt.replace(tzinfo=timezone.utc)
        next_rebalance_dt = last_rebalance_dt + timedelta(days=rebalance_interval_days)
    else:
        # If no rebalance has happened, schedule from now
        next_rebalance_dt = datetime.now(timezone.utc) + timedelta(days=rebalance_interval_days)

    cash_remaining = core_capital - total_core_value

    return {
        "core_capital": core_capital,
        "holdings": holdings,
        "next_rebalance_date": next_rebalance_dt.isoformat(),
        "cash_remaining": cash_remaining,
    }


def run_core_cycle(config: dict, db: Database) -> dict:
    """Main entry point called daily to manage core holdings.

    Evaluates each symbol in the buy_list for DCA or dip entry opportunities,
    executes orders, and runs exit checks.

    Returns:
        dict with summary of actions taken.
    """
    core_cfg = config.get("core_holdings", {})
    buy_list = core_cfg.get("buy_list", [])
    entry_cfg = core_cfg.get("entry", {})
    dca_interval_days = entry_cfg.get("dca_interval_days", 7)

    capital_split = config.get("capital_split", {})
    core_capital = config["capital"] * capital_split.get("core", 0.0)

    portfolio = get_portfolio()
    risk_manager = RiskManager(config, db)

    positions_by_symbol = {p["symbol"]: p for p in portfolio.get("positions", [])}

    # Calculate total core value for weight checks
    core_buy_symbols = {item["symbol"] for item in buy_list}
    total_core_value = sum(
        p["market_value"]
        for p in portfolio.get("positions", [])
        if p["symbol"] in core_buy_symbols
    )

    buys_executed = []
    buys_skipped = []

    for bl_item in buy_list:
        symbol = bl_item["symbol"]
        target_weight = bl_item.get("weight", 0.0)

        pos = positions_by_symbol.get(symbol)
        current_value = pos["market_value"] if pos else 0.0
        actual_weight = (current_value / total_core_value) if total_core_value > 0 else 0.0

        # Skip if already at or above target weight
        if actual_weight >= target_weight:
            buys_skipped.append({"symbol": symbol, "reason": "at_target_weight"})
            continue

        # Get technicals for dip detection
        try:
            tech = analyze_technicals(symbol)
        except Exception as e:
            logger.warning("Failed to get technicals for %s: %s", symbol, e)
            buys_skipped.append({"symbol": symbol, "reason": f"technicals_error: {e}"})
            continue

        current_price = tech.get("current_price")
        sma_50 = tech.get("sma_50")

        if not current_price:
            buys_skipped.append({"symbol": symbol, "reason": "no_price_data"})
            continue

        # Determine if we should buy
        dip_entry = sma_50 is not None and current_price < sma_50
        last_buy_ts = db.get_last_core_buy_date(symbol)

        if last_buy_ts is not None:
            last_buy_dt = datetime.fromisoformat(last_buy_ts)
            if last_buy_dt.tzinfo is None:
                last_buy_dt = last_buy_dt.replace(tzinfo=timezone.utc)
            days_since_buy = (datetime.now(timezone.utc) - last_buy_dt).days
            dca_due = days_since_buy >= dca_interval_days
        else:
            dca_due = True  # Never bought before

        if not dip_entry and not dca_due:
            buys_skipped.append({"symbol": symbol, "reason": "no_trigger"})
            continue

        reason = "dip_entry" if dip_entry else "dca_fallback"

        qty = risk_manager.calculate_core_position_size(current_price, config)
        if qty <= 0:
            buys_skipped.append({"symbol": symbol, "reason": "qty_zero"})
            continue

        order = execute_order(symbol, "buy", qty)

        if order.get("status") == "error":
            logger.error("Order failed for %s: %s", symbol, order.get("error"))
            buys_skipped.append({"symbol": symbol, "reason": f"order_error: {order.get('error')}"})
            continue

        filled_price = order.get("filled_price") or current_price
        cost_basis = qty * filled_price

        db.insert_core_buy({
            "symbol": symbol,
            "qty": qty,
            "price": filled_price,
            "cost_basis": cost_basis,
            "order_id": order.get("order_id"),
        })

        db.insert_decision({
            "ticker": symbol,
            "action": "core_buy",
            "reasoning": f"Core DCA: {reason}. Price={filled_price:.2f}, SMA50={sma_50}",
            "signals_snapshot": str(tech),
            "position_id": order.get("order_id"),
        })

        buys_executed.append({
            "symbol": symbol,
            "qty": qty,
            "price": filled_price,
            "reason": reason,
            "order_id": order.get("order_id"),
        })
        logger.info("Core buy: %s qty=%.4f price=%.2f reason=%s", symbol, qty, filled_price, reason)

    exits = check_core_exits(config, db, portfolio)

    # Run core guardian health checks
    from claude_invest.modules.core_guardian import check_core_health, update_peaks, check_probation_promotions

    core_symbols = {item["symbol"] for item in buy_list}
    update_peaks(db, portfolio, core_symbols)
    health = check_core_health(config, db, portfolio)
    promotions = check_probation_promotions(config, db, portfolio)

    return {
        "buys_executed": buys_executed,
        "buys_skipped": buys_skipped,
        "exits": exits,
        "core_capital": core_capital,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "guardian": health,
        "promotions": promotions,
    }


def check_core_exits(config: dict, db: Database, portfolio: dict) -> list[dict]:
    """Check exit conditions for core holdings.

    Exit conditions (NEVER on RSI/MACD):
    1. Symbol removed from buy_list
    2. Sustained negative sentiment (last N days below threshold)
    3. Position > max_position_pct of total core value

    Returns:
        list of dicts describing exits taken.
    """
    core_cfg = config.get("core_holdings", {})
    exit_cfg = core_cfg.get("exit", {})

    sell_on_signals = exit_cfg.get("sell_on_signals", False)
    sell_on_removal = exit_cfg.get("sell_on_removal", True)
    sentiment_threshold = exit_cfg.get("sentiment_exit_threshold", -0.3)
    sentiment_exit_days = exit_cfg.get("sentiment_exit_days", 5)
    max_position_pct = exit_cfg.get("max_position_pct", 0.20)

    # Enforce: never sell on RSI/MACD
    if sell_on_signals:
        logger.warning("sell_on_signals=True in config but core engine NEVER sells on signals. Ignoring.")

    buy_list = core_cfg.get("buy_list", [])
    buy_list_symbols = {item["symbol"] for item in buy_list}

    positions_by_symbol = {p["symbol"]: p for p in portfolio.get("positions", [])}

    # Total core value from positions that are (or were) in buy_list
    # Include current holdings even if removed, since we might sell them
    core_positions = {
        sym: pos for sym, pos in positions_by_symbol.items()
        if sym in buy_list_symbols or db.get_last_core_buy_date(sym) is not None
    }
    total_core_value = sum(p["market_value"] for p in core_positions.values())

    exits = []

    for symbol, pos in core_positions.items():
        current_value = pos["market_value"]
        current_price = pos["current_price"]
        qty = pos["qty"]

        # --- Exit condition 1: Symbol removed from buy_list ---
        if sell_on_removal and symbol not in buy_list_symbols:
            order = execute_order(symbol, "sell", qty)
            exit_record = {
                "symbol": symbol,
                "qty": qty,
                "price": current_price,
                "reason": "removed_from_buy_list",
                "order": order,
            }
            db.insert_decision({
                "ticker": symbol,
                "action": "core_sell",
                "reasoning": "Symbol removed from core buy_list",
                "position_id": order.get("order_id"),
            })
            exits.append(exit_record)
            logger.info("Core exit (removal): %s qty=%.4f", symbol, qty)
            continue

        # --- Exit condition 2: Sustained negative sentiment ---
        signals = db.get_signals(symbol, limit=sentiment_exit_days)
        if len(signals) >= sentiment_exit_days:
            scores = [s["sentiment_score"] for s in signals if s.get("sentiment_score") is not None]
            if scores and all(s < sentiment_threshold for s in scores):
                order = execute_order(symbol, "sell", qty)
                exit_record = {
                    "symbol": symbol,
                    "qty": qty,
                    "price": current_price,
                    "reason": "sustained_negative_sentiment",
                    "avg_sentiment": sum(scores) / len(scores),
                    "order": order,
                }
                db.insert_decision({
                    "ticker": symbol,
                    "action": "core_sell",
                    "reasoning": f"Sustained negative sentiment over {sentiment_exit_days} days. Avg={sum(scores)/len(scores):.3f}",
                    "position_id": order.get("order_id"),
                })
                exits.append(exit_record)
                logger.info("Core exit (sentiment): %s qty=%.4f", symbol, qty)
                continue

        # --- Exit condition 3: Position exceeds max_position_pct of core pool ---
        if total_core_value > 0:
            position_pct = current_value / total_core_value
            if position_pct > max_position_pct:
                # Trim to target weight or max_position_pct
                target_weight = next(
                    (item.get("weight", max_position_pct) for item in buy_list if item["symbol"] == symbol),
                    max_position_pct,
                )
                target_value = total_core_value * target_weight
                excess_value = current_value - target_value
                trim_qty = round(excess_value / current_price, 6)

                if trim_qty > 0:
                    order = execute_order(symbol, "sell", trim_qty)
                    exit_record = {
                        "symbol": symbol,
                        "qty": trim_qty,
                        "price": current_price,
                        "reason": "overweight_trim",
                        "position_pct": position_pct,
                        "max_position_pct": max_position_pct,
                        "order": order,
                    }
                    db.insert_decision({
                        "ticker": symbol,
                        "action": "core_trim",
                        "reasoning": f"Position {position_pct:.1%} exceeds max {max_position_pct:.1%}. Trimming {trim_qty:.4f} shares.",
                        "position_id": order.get("order_id"),
                    })
                    exits.append(exit_record)
                    logger.info("Core trim (overweight): %s qty=%.4f pct=%.1%", symbol, trim_qty, position_pct)

    return exits


def rebalance_core(config: dict, db: Database, portfolio: dict, dry_run: bool = False) -> list[dict]:
    """Quarterly rebalance of core holdings.

    Compares current weights to target weights and generates buy/sell orders
    to correct significant drift.

    Args:
        config: Application config dict.
        db: Database instance.
        portfolio: Current portfolio from get_portfolio().
        dry_run: If True, returns preview without executing orders.

    Returns:
        list of rebalance actions (executed or preview).
    """
    core_cfg = config.get("core_holdings", {})
    rebalance_cfg = core_cfg.get("rebalance", {})
    drift_threshold = rebalance_cfg.get("drift_threshold", 0.05)

    buy_list = core_cfg.get("buy_list", [])
    buy_list_by_symbol = {item["symbol"]: item for item in buy_list}

    positions_by_symbol = {p["symbol"]: p for p in portfolio.get("positions", [])}

    # Total core value for weight calculations
    buy_list_symbols = set(buy_list_by_symbol.keys())
    total_core_value = sum(
        p["market_value"]
        for p in portfolio.get("positions", [])
        if p["symbol"] in buy_list_symbols
    )

    if total_core_value == 0:
        logger.info("Rebalance: no core positions found, skipping.")
        return []

    actions = []

    for symbol, bl_item in buy_list_by_symbol.items():
        target_weight = bl_item.get("weight", 0.0)
        pos = positions_by_symbol.get(symbol)
        current_value = pos["market_value"] if pos else 0.0
        current_price = pos["current_price"] if pos else None
        current_qty = pos["qty"] if pos else 0.0

        actual_weight = current_value / total_core_value
        drift = actual_weight - target_weight

        if abs(drift) <= drift_threshold:
            continue

        if not current_price:
            logger.warning("Rebalance: no price for %s, skipping.", symbol)
            continue

        target_value = total_core_value * target_weight
        value_delta = target_value - current_value
        qty_delta = abs(value_delta) / current_price
        qty_delta = round(qty_delta, 6)

        if qty_delta <= 0:
            continue

        side = "buy" if value_delta > 0 else "sell"

        action = {
            "symbol": symbol,
            "side": side,
            "qty": qty_delta,
            "price": current_price,
            "old_weight": actual_weight,
            "new_weight": target_weight,
            "drift": drift,
            "reason": f"rebalance: drift {drift:+.1%} exceeds threshold {drift_threshold:.1%}",
            "dry_run": dry_run,
        }

        if not dry_run:
            order = execute_order(symbol, side, qty_delta)
            action["order"] = order
            action["order_id"] = order.get("order_id")

            db.insert_rebalance_log({
                "symbol": symbol,
                "action": side,
                "qty": qty_delta,
                "price": current_price,
                "reason": action["reason"],
                "old_weight": actual_weight,
                "new_weight": target_weight,
            })
            logger.info(
                "Rebalance %s %s: qty=%.4f old_weight=%.1%% new_weight=%.1%%",
                side, symbol, qty_delta, actual_weight * 100, target_weight * 100,
            )

        actions.append(action)

    return actions
