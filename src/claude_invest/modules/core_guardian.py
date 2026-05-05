"""
Core Guardian
=============
Intelligent exit logic for core holdings. Tracks peak prices, monitors
sustained drawdowns, and protects against losses without panic selling.

Uses market crash override (SPY > -10%) to suspend exits during corrections.
"""
import logging
from datetime import datetime, timezone

from claude_invest.modules.db import Database
from claude_invest.modules.executor import execute_order

logger = logging.getLogger(__name__)


def _days_since_peak(db: Database, symbol: str) -> int:
    """Days since the peak price was recorded."""
    peak = db.get_core_peak(symbol)
    if not peak:
        return 0
    peak_dt = datetime.fromisoformat(peak["peak_date"])
    if peak_dt.tzinfo is None:
        peak_dt = peak_dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - peak_dt).days


def update_peaks(db: Database, portfolio: dict, core_symbols: set):
    """Update peak prices for all core holdings. Only increases, never decreases."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for pos in portfolio.get("positions", []):
        if pos["symbol"] in core_symbols:
            db.upsert_core_peak(pos["symbol"], pos["current_price"], today)


def check_core_health(config: dict, db: Database, portfolio: dict) -> dict:
    """Run smart exit checks for all core holdings.

    Returns:
        {"warnings": [...], "trims": [...], "exits": [...], "crash_override": bool}
    """
    guardian_cfg = config.get("core_guardian", {})
    warning_drawdown = guardian_cfg.get("warning_drawdown", -0.15)
    reduce_drawdown = guardian_cfg.get("reduce_drawdown", -0.25)
    exit_drawdown = guardian_cfg.get("exit_drawdown", -0.35)
    warning_days = guardian_cfg.get("warning_days", 5)
    reduce_days = guardian_cfg.get("reduce_days", 10)
    crash_threshold = guardian_cfg.get("crash_override_threshold", -0.10)
    probation_factor = guardian_cfg.get("probation_tighter_factor", 0.67)

    core_cfg = config.get("core_holdings", {})
    buy_list_symbols = {item["symbol"] for item in core_cfg.get("buy_list", [])}

    warnings = []
    trims = []
    exits = []

    # Check SPY for market crash override
    spy_peak = db.get_core_peak("SPY")
    spy_pos = None
    for p in portfolio.get("positions", []):
        if p["symbol"] == "SPY":
            spy_pos = p
            break

    crash_override = False
    if spy_peak and spy_pos:
        spy_drawdown = (spy_pos["current_price"] - spy_peak["peak_price"]) / spy_peak["peak_price"]
        if spy_drawdown < crash_threshold:
            crash_override = True
            logger.info("CRASH OVERRIDE: SPY drawdown %.1f%% > %.1f%% threshold. Suspending exits.",
                       spy_drawdown * 100, crash_threshold * 100)

    if crash_override:
        return {"warnings": [], "trims": [], "exits": [], "crash_override": True}

    # Check each core holding
    for pos in portfolio.get("positions", []):
        symbol = pos["symbol"]
        if symbol not in buy_list_symbols or symbol == "SPY":
            continue

        peak = db.get_core_peak(symbol)
        if not peak:
            continue

        drawdown = (pos["current_price"] - peak["peak_price"]) / peak["peak_price"]
        days_since = _days_since_peak(db, symbol)

        # Check if this is a probationary stock (tighter thresholds)
        graduation = db.get_graduation_by_symbol(symbol)
        is_probation = graduation is not None and graduation["status"] == "probation"

        effective_warning = warning_drawdown * probation_factor if is_probation else warning_drawdown
        effective_reduce = reduce_drawdown * probation_factor if is_probation else reduce_drawdown
        effective_exit = exit_drawdown * probation_factor if is_probation else exit_drawdown

        # Tier 3: Full exit (-35% or -23% for probation)
        if drawdown <= effective_exit:
            qty = pos["qty"]
            order = execute_order(symbol, "sell", qty)
            exits.append({
                "symbol": symbol,
                "drawdown": drawdown,
                "days_since_peak": days_since,
                "qty": qty,
                "order": order,
                "probation": is_probation,
            })
            logger.info("CORE EXIT: %s drawdown %.1f%% (threshold %.1f%%). Full sell.",
                       symbol, drawdown * 100, effective_exit * 100)

            # If probation, demote
            if is_probation and graduation:
                db.update_graduation_status(graduation["id"], "demoted")
            continue

        # Tier 2: Reduce 50% (-25% sustained 10+ days, or -17% for probation)
        if drawdown <= effective_reduce and days_since >= reduce_days:
            qty_to_sell = pos["qty"] * 0.5
            order = execute_order(symbol, "sell", qty_to_sell)
            trims.append({
                "symbol": symbol,
                "drawdown": drawdown,
                "days_since_peak": days_since,
                "qty_sold": qty_to_sell,
                "order": order,
                "probation": is_probation,
            })
            logger.info("CORE REDUCE: %s drawdown %.1f%% for %d days. Selling 50%%.",
                       symbol, drawdown * 100, days_since)

            # If probation, demote
            if is_probation and graduation:
                db.update_graduation_status(graduation["id"], "demoted")
            continue

        # Tier 1: Warning (-15% sustained 5+ days, or -10% for probation)
        if drawdown <= effective_warning and days_since >= warning_days:
            warnings.append({
                "symbol": symbol,
                "drawdown": drawdown,
                "days_since_peak": days_since,
                "probation": is_probation,
            })
            logger.info("CORE WARNING: %s drawdown %.1f%% for %d days.",
                       symbol, drawdown * 100, days_since)

    return {
        "warnings": warnings,
        "trims": trims,
        "exits": exits,
        "crash_override": crash_override,
    }


def check_probation_promotions(config: dict, db: Database, portfolio: dict) -> list[dict]:
    """Check if any probationary stocks should be promoted to full weight.

    Criteria: 30+ days in probation without hitting -15% from graduation price.
    """
    grad_cfg = config.get("graduation", {})
    probation_days = grad_cfg.get("probation_days", 30)

    graduations = db.get_graduations(status="probation")
    promotions = []

    for grad in graduations:
        grad_dt = datetime.fromisoformat(grad["timestamp"])
        if grad_dt.tzinfo is None:
            grad_dt = grad_dt.replace(tzinfo=timezone.utc)

        days_in_probation = (datetime.now(timezone.utc) - grad_dt).days
        if days_in_probation < probation_days:
            continue

        # Check if position still exists and hasn't crashed
        symbol = grad["symbol"]
        peak = db.get_core_peak(symbol)
        pos = None
        for p in portfolio.get("positions", []):
            if p["symbol"] == symbol:
                pos = p
                break

        if not pos or not peak:
            continue

        drawdown = (pos["current_price"] - peak["peak_price"]) / peak["peak_price"]
        if drawdown > -0.15:  # Hasn't hit -15% from peak
            db.update_graduation_status(grad["id"], "promoted")
            promotions.append({
                "symbol": symbol,
                "days_in_probation": days_in_probation,
                "current_drawdown": drawdown,
            })
            logger.info("PROMOTED %s: %d days in probation, drawdown %.1f%%.",
                       symbol, days_in_probation, drawdown * 100)

    return promotions
