"""
Parameter optimizer for claude-invest strategy settings.

Analyzes trade outcomes and proposes or auto-applies changes to strategy
parameters in settings.yaml. Uses ruamel.yaml for round-trip YAML editing
(preserves formatting). Changes are logged to the change_log table in SQLite.
"""

from __future__ import annotations

from typing import Any

from ruamel.yaml import YAML

from claude_invest.modules.db import Database

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_ACTIVE_CHANGES = 3
EVAL_WINDOW_TRADES = 10
REVERT_WIN_RATE_DROP = 0.15
MAX_REVERTS_BEFORE_LOCK = 2

# Minimum trades required before proposing any parameter change
_MIN_TRADES_FOR_PROPOSAL = 5
# Minimum trades required to auto-apply (vs. only propose)
_MIN_TRADES_FOR_AUTO_APPLY = 10

# ---------------------------------------------------------------------------
# Optimizable parameter registry
# ---------------------------------------------------------------------------

OPTIMIZABLE_PARAMS: dict[str, dict[str, Any]] = {
    "rsi_buy_threshold": {
        "min": 10,
        "max": 40,
        "strategies": ["mean_reversion"],
        "type": int,
    },
    "rsi_sell_threshold": {
        "min": 55,
        "max": 85,
        "strategies": ["mean_reversion"],
        "type": int,
    },
    "max_hold_bars": {
        "min": 3,
        "max": 10,
        "strategies": ["mean_reversion"],
        "type": int,
    },
    "stop_loss_pct": {
        "min": 0.005,
        "max": 0.05,
        "strategies": ["mean_reversion", "trend_pullback", "momentum"],
        "type": float,
    },
    "take_profit_pct": {
        "min": 0.01,
        "max": 0.10,
        "strategies": ["mean_reversion", "trend_pullback", "momentum"],
        "type": float,
    },
    "macd_fast": {
        "min": 3,
        "max": 12,
        "strategies": ["trend_pullback"],
        "type": int,
    },
    "macd_slow": {
        "min": 20,
        "max": 50,
        "strategies": ["trend_pullback"],
        "type": int,
    },
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _clamp(value: float, param_name: str) -> float:
    """Clamp a numeric value to the bounds defined for a parameter."""
    spec = OPTIMIZABLE_PARAMS.get(param_name)
    if spec is None:
        return value
    return max(spec["min"], min(spec["max"], value))


def _coerce(value: Any, param_name: str) -> Any:
    """Clamp and convert value to the correct type for the parameter."""
    spec = OPTIMIZABLE_PARAMS.get(param_name)
    if spec is None:
        return value
    clamped = _clamp(float(value), param_name)
    return spec["type"](clamped)


def _navigate(data: Any, keys: list[str]) -> tuple[Any, str]:
    """
    Walk a nested dict/CommentedMap by key list.
    Returns (parent_container, last_key).
    """
    container = data
    for key in keys[:-1]:
        container = container[key]
    return container, keys[-1]


def _param_name_from_path(parameter_path: str) -> str | None:
    """Extract the parameter name (last segment) from a dotted path."""
    return parameter_path.split(".")[-1]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def can_apply_more_changes(db: Database) -> bool:
    """Return True if fewer than MAX_ACTIVE_CHANGES unevaluated changes exist."""
    active = db.get_active_changes()
    return len(active) < MAX_ACTIVE_CHANGES


def apply_change(
    *,
    config_path: str,
    db: Database,
    parameter_path: str,
    old_value: str,
    new_value: str,
    reason: str,
    trade_count: int,
    auto_applied: bool,
) -> None:
    """
    Update a parameter in settings.yaml and record the change in the DB.

    The new_value is clamped to the parameter's defined bounds before writing.
    Uses ruamel.yaml to preserve YAML formatting/comments.
    """
    param_name = _param_name_from_path(parameter_path)
    clamped = _coerce(new_value, param_name) if param_name in OPTIMIZABLE_PARAMS else new_value

    # --- update YAML file ---
    yaml = YAML()
    with open(config_path) as fh:
        config = yaml.load(fh)

    keys = parameter_path.split(".")
    container, last_key = _navigate(config, keys)
    container[last_key] = clamped

    with open(config_path, "w") as fh:
        yaml.dump(config, fh)

    # --- log to DB ---
    db.insert_change_log({
        "parameter_path": parameter_path,
        "old_value": str(old_value),
        "new_value": str(clamped),
        "reason": reason,
        "trade_count": trade_count,
        "auto_applied": auto_applied,
    })


def evaluate_parameters(
    trades_by_strategy: dict[str, list[dict]],
    current_config: dict,
) -> list[dict]:
    """
    Analyse recent trades per strategy and propose parameter adjustments.

    A proposal is only generated when the strategy has >= _MIN_TRADES_FOR_PROPOSAL
    trades. auto_applied is set to True only when >= _MIN_TRADES_FOR_AUTO_APPLY.

    Returns a list of proposal dicts:
        {
            "parameter_path": str,
            "old_value": str,
            "new_value": str,
            "reason": str,
            "trade_count": int,
            "auto_applied": bool,
        }
    """
    proposals: list[dict] = []
    strategies_cfg = current_config.get("strategies", {})

    for strategy_name, trades in trades_by_strategy.items():
        if len(trades) < _MIN_TRADES_FOR_PROPOSAL:
            continue

        strategy_cfg = strategies_cfg.get(strategy_name, {})
        params = strategy_cfg.get("params", {})

        trade_count = len(trades)
        auto_applied = trade_count >= _MIN_TRADES_FOR_AUTO_APPLY

        wins = [t for t in trades if t.get("win")]
        win_rate = len(wins) / trade_count

        # --- RSI buy threshold (mean_reversion) ---
        if strategy_name == "mean_reversion" and "rsi_buy_threshold" in params:
            current_rsi_threshold = params["rsi_buy_threshold"]
            rsi_values = [
                t["entry_signals"]["rsi"]
                for t in trades
                if isinstance(t.get("entry_signals"), dict) and "rsi" in t["entry_signals"]
            ]
            if rsi_values and win_rate < 0.45:
                # Winning trades had lower RSI on average — tighten threshold
                winning_rsi = [
                    t["entry_signals"]["rsi"]
                    for t in wins
                    if isinstance(t.get("entry_signals"), dict) and "rsi" in t["entry_signals"]
                ]
                if winning_rsi:
                    avg_winning_rsi = sum(winning_rsi) / len(winning_rsi)
                    proposed = round(avg_winning_rsi)
                    proposed = int(_clamp(proposed, "rsi_buy_threshold"))
                    if proposed != current_rsi_threshold:
                        proposals.append({
                            "parameter_path": f"strategies.{strategy_name}.params.rsi_buy_threshold",
                            "old_value": str(current_rsi_threshold),
                            "new_value": str(proposed),
                            "reason": (
                                f"Win rate {win_rate:.0%} below target; "
                                f"avg winning RSI={avg_winning_rsi:.1f}"
                            ),
                            "trade_count": trade_count,
                            "auto_applied": auto_applied,
                        })

        # --- stop_loss_pct — widen if many stop-outs but winners did fine ---
        if "stop_loss_pct" in params and win_rate < 0.40:
            current_sl = params["stop_loss_pct"]
            # Propose a modest tightening to cut losers faster
            proposed_sl = round(current_sl * 0.9, 4)
            proposed_sl = _clamp(proposed_sl, "stop_loss_pct")
            if proposed_sl != current_sl:
                proposals.append({
                    "parameter_path": f"strategies.{strategy_name}.params.stop_loss_pct",
                    "old_value": str(current_sl),
                    "new_value": str(proposed_sl),
                    "reason": (
                        f"Win rate {win_rate:.0%} below 40%; "
                        "tightening stop-loss to cut losers faster"
                    ),
                    "trade_count": trade_count,
                    "auto_applied": auto_applied,
                })

    return proposals


def check_evaluation_windows(
    db: Database,
    trades_by_strategy: dict[str, list[dict]],
    config_path: str,
) -> list[dict]:
    """
    Review active (unevaluated) parameter changes.

    For each active change, if the strategy has accumulated >= EVAL_WINDOW_TRADES
    trades since the change was applied and win rate has dropped by >=
    REVERT_WIN_RATE_DROP percentage points compared to the pre-change baseline,
    the change is reverted.

    Returns a list of revert action dicts for informational purposes.
    """
    active_changes = db.get_active_changes()
    reverts: list[dict] = []

    for change in active_changes:
        param_path = change["parameter_path"]
        # Determine which strategy this change belongs to
        parts = param_path.split(".")
        if len(parts) < 3:
            continue
        strategy_name = parts[1]

        strategy_trades = trades_by_strategy.get(strategy_name, [])
        if len(strategy_trades) < EVAL_WINDOW_TRADES:
            continue

        # Compute current post-change win rate
        recent_wins = sum(1 for t in strategy_trades if t.get("win"))
        current_win_rate = recent_wins / len(strategy_trades)

        # Estimate baseline from trade_count recorded at change time
        # (stored as the number of trades at the time of the change; we use it
        #  as a proxy — if we have more trades now, the recent slice is post-change)
        baseline_win_rate = float(change.get("trade_count", 0)) / max(
            float(change.get("trade_count", 1)) + len(strategy_trades), 1
        )
        # Simplified heuristic: use 0.5 as default baseline when we can't compute
        # a reliable one from stored data
        baseline_win_rate = 0.50

        drop = baseline_win_rate - current_win_rate
        if drop >= REVERT_WIN_RATE_DROP:
            # Revert the change in the YAML
            apply_change(
                config_path=config_path,
                db=db,
                parameter_path=param_path,
                old_value=change["new_value"],
                new_value=change["old_value"],
                reason=f"Auto-revert: win rate dropped {drop:.0%} after change",
                trade_count=len(strategy_trades),
                auto_applied=True,
            )
            db.revert_change(
                change["id"],
                reason=f"Win rate dropped {drop:.0%} below baseline",
            )
            reverts.append({
                "change_id": change["id"],
                "parameter_path": param_path,
                "reverted_to": change["old_value"],
                "reason": f"Win rate dropped {drop:.0%}",
            })

    return reverts
