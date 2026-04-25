"""
Pattern Analyzer: analyzes completed trade pairs across 5 dimensions.

Dimensions:
  1. signal_combos   - grouped by signal_combo field
  2. time_of_day     - entry hour bucketed into market session windows
  3. hold_duration   - exit - entry duration bucketed by trade style
  4. market_regime   - RSI-based volatility proxy
  5. asset_class     - crypto vs stock, crossed with strategy_id

Also produces cross-dimensional 2-way combos with 3+ trades.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _confidence(total: int) -> str:
    if total < 5:
        return "insufficient"
    if total < 10:
        return "low"
    return "high"


def _bucket_stats(trades: list[dict]) -> dict:
    wins = sum(1 for t in trades if t.get("win"))
    losses = len(trades) - wins
    total = len(trades)
    win_rate = wins / total if total else 0.0
    avg_pnl = sum(t.get("pnl", 0) for t in trades) / total if total else 0.0
    return {
        "wins": wins,
        "losses": losses,
        "total": total,
        "win_rate": round(win_rate, 4),
        "avg_pnl": round(avg_pnl, 4),
        "confidence": _confidence(total),
    }


def _time_of_day_bucket(hour: int, minute: int = 0) -> str:
    """Map an hour (0-23) to a named market session bucket."""
    # Represent as total minutes from midnight for cleaner comparisons
    t = hour * 60 + minute
    if 9 * 60 <= t < 9 * 60 + 30:          # 09:00–09:29
        return "pre_market"
    if 9 * 60 + 30 <= t < 10 * 60 + 30:    # 09:30–10:30
        return "market_open"
    if 10 * 60 + 30 <= t < 15 * 60:        # 10:30–15:00
        return "midday"
    if 15 * 60 <= t < 16 * 60:             # 15:00–16:00
        return "market_close"
    if 16 * 60 <= t < 20 * 60:             # 16:00–20:00
        return "after_hours"
    # everything else (20:00–09:00)
    return "crypto_overnight"


def _hold_duration_bucket(minutes: float) -> str:
    if minutes < 15:
        return "scalp"
    if minutes < 60:
        return "intraday"
    if minutes < 1440:       # < 24 h
        return "swing_short"
    if minutes < 7200:       # < 5 d
        return "swing_long"
    return "position"


def _market_regime(rsi: float) -> str:
    if rsi < 30 or rsi > 70:
        return "high_volatility"
    if 40 <= rsi <= 60:
        return "low_volatility"
    return "normal"


def _asset_class(ticker: str) -> str:
    return "crypto" if "/" in ticker else "stock"


def _parse_dt(s: str) -> datetime:
    # Handle both 'Z' suffix and naive ISO strings
    s = s.rstrip("Z")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime: {s!r}")


# ---------------------------------------------------------------------------
# Cross-dimensional insight helpers
# ---------------------------------------------------------------------------

def _cross_insight(label: str, trades: list[dict], key_a: str, key_b: str) -> dict:
    stats = _bucket_stats(trades)
    actionable = (
        stats["win_rate"] >= 0.6 and stats["confidence"] != "insufficient"
    )
    return {
        "insight": label,
        "dimension_a": key_a,
        "dimension_b": key_b,
        **stats,
        "actionable": actionable,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_patterns(matched_trades: list[dict]) -> dict:
    """
    Analyze completed trade pairs across 5 dimensions.

    Parameters
    ----------
    matched_trades:
        List of trade dicts, each representing a closed position.

    Returns
    -------
    dict with keys: generated_at, total_trades, overall_win_rate,
    signal_combos, time_of_day, hold_duration, market_regime,
    asset_class, cross_dimensional.
    """
    total = len(matched_trades)
    overall_win_rate = (
        sum(1 for t in matched_trades if t.get("win")) / total if total else 0.0
    )

    if total == 0:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_trades": 0,
            "overall_win_rate": 0,
            "signal_combos": [],
            "time_of_day": [],
            "hold_duration": [],
            "market_regime": [],
            "asset_class": [],
            "cross_dimensional": [],
        }

    # ------------------------------------------------------------------
    # 1. Signal combos
    # ------------------------------------------------------------------
    combo_groups: dict[str, list[dict]] = defaultdict(list)
    for t in matched_trades:
        combo_groups[t.get("signal_combo", "unknown")].append(t)

    signal_combos = []
    for combo, group in combo_groups.items():
        signal_combos.append({"signal_combo": combo, **_bucket_stats(group)})
    signal_combos.sort(key=lambda x: -x["total"])

    # ------------------------------------------------------------------
    # 2. Time-of-day
    # ------------------------------------------------------------------
    tod_groups: dict[str, list[dict]] = defaultdict(list)
    for t in matched_trades:
        dt = _parse_dt(t["entry_time"])
        bucket = _time_of_day_bucket(dt.hour, dt.minute)
        tod_groups[bucket].append(t)

    time_of_day = [
        {"bucket": bucket, **_bucket_stats(group)}
        for bucket, group in tod_groups.items()
    ]
    time_of_day.sort(key=lambda x: -x["total"])

    # ------------------------------------------------------------------
    # 3. Hold duration
    # ------------------------------------------------------------------
    hold_groups: dict[str, list[dict]] = defaultdict(list)
    for t in matched_trades:
        entry_dt = _parse_dt(t["entry_time"])
        exit_dt = _parse_dt(t["exit_time"])
        minutes = (exit_dt - entry_dt).total_seconds() / 60
        bucket = _hold_duration_bucket(minutes)
        hold_groups[bucket].append(t)

    hold_duration = [
        {"bucket": bucket, **_bucket_stats(group)}
        for bucket, group in hold_groups.items()
    ]
    hold_duration.sort(key=lambda x: -x["total"])

    # ------------------------------------------------------------------
    # 4. Market regime (RSI proxy)
    # ------------------------------------------------------------------
    regime_groups: dict[str, list[dict]] = defaultdict(list)
    for t in matched_trades:
        rsi = t.get("entry_signals", {}).get("rsi", 50)
        regime = _market_regime(float(rsi))
        regime_groups[regime].append(t)

    market_regime = [
        {"regime": regime, **_bucket_stats(group)}
        for regime, group in regime_groups.items()
    ]
    market_regime.sort(key=lambda x: -x["total"])

    # ------------------------------------------------------------------
    # 5. Asset class × strategy_id
    # ------------------------------------------------------------------
    asset_groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for t in matched_trades:
        ac = _asset_class(t.get("ticker", ""))
        sid = t.get("strategy_id", "unknown")
        asset_groups[(ac, sid)].append(t)

    asset_class = [
        {"asset_class": ac, "strategy_id": sid, **_bucket_stats(group)}
        for (ac, sid), group in asset_groups.items()
    ]
    asset_class.sort(key=lambda x: -x["total"])

    # ------------------------------------------------------------------
    # 6. Cross-dimensional analysis
    # ------------------------------------------------------------------
    # Precompute per-trade dimension labels
    trade_dims: list[dict[str, str]] = []
    for t in matched_trades:
        dt = _parse_dt(t["entry_time"])
        exit_dt = _parse_dt(t["exit_time"])
        minutes = (exit_dt - dt).total_seconds() / 60
        trade_dims.append({
            "strategy": t.get("strategy_id", "unknown"),
            "time": _time_of_day_bucket(dt.hour, dt.minute),
            "asset": _asset_class(t.get("ticker", "")),
        })

    cross_combos: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    pairs = [
        ("strategy", "time"),
        ("strategy", "asset"),
        ("time", "asset"),
    ]
    for trade, dims in zip(matched_trades, trade_dims):
        for key_a, key_b in pairs:
            label = f"{key_a}={dims[key_a]} × {key_b}={dims[key_b]}"
            cross_combos[(key_a, key_b, dims[key_a], dims[key_b])].append(trade)

    cross_dimensional = []
    for (key_a, key_b, val_a, val_b), group in cross_combos.items():
        if len(group) < 3:
            continue
        label = f"{key_a}={val_a} × {key_b}={val_b}"
        cross_dimensional.append(
            _cross_insight(label, group, key_a, key_b)
        )
    cross_dimensional.sort(key=lambda x: -x["total"])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_trades": total,
        "overall_win_rate": round(overall_win_rate, 4),
        "signal_combos": signal_combos,
        "time_of_day": time_of_day,
        "hold_duration": hold_duration,
        "market_regime": market_regime,
        "asset_class": asset_class,
        "cross_dimensional": cross_dimensional,
    }
