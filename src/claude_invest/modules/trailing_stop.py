"""Trailing stop manager — tracks peak prices and triggers exits when price drops from peak."""

from claude_invest.modules.db import Database


# In-memory peak price tracker (resets on restart — could persist to DB later)
_peak_prices: dict[str, float] = {}


def update_peak(symbol: str, current_price: float) -> float:
    """Update peak price for a symbol. Returns the current peak."""
    if symbol not in _peak_prices or current_price > _peak_prices[symbol]:
        _peak_prices[symbol] = current_price
    return _peak_prices[symbol]


def check_trailing_stop(symbol: str, current_price: float, entry_price: float,
                        trailing_pct: float = 0.05) -> dict:
    """Check if trailing stop is triggered.

    Args:
        symbol: Ticker symbol
        current_price: Current market price
        entry_price: Original entry price
        trailing_pct: Trailing stop percentage (default 5% from peak)

    Returns:
        dict with triggered (bool), peak_price, drop_from_peak_pct, reason
    """
    peak = update_peak(symbol, current_price)

    # Only activate trailing stop after position is profitable (above entry)
    if peak <= entry_price:
        return {
            "triggered": False,
            "peak_price": peak,
            "current_price": current_price,
            "drop_from_peak_pct": 0,
            "reason": "Not yet profitable — trailing stop inactive",
        }

    drop_from_peak = (peak - current_price) / peak
    triggered = drop_from_peak >= trailing_pct

    return {
        "triggered": triggered,
        "peak_price": peak,
        "current_price": current_price,
        "drop_from_peak_pct": round(drop_from_peak, 4),
        "reason": f"Trailing stop {'TRIGGERED' if triggered else 'active'}: peak ${peak:.2f}, drop {drop_from_peak:.1%} vs {trailing_pct:.0%} threshold",
    }


def check_partial_profit(symbol: str, current_price: float, entry_price: float,
                         levels: list[dict] | None = None) -> dict | None:
    """Check if any partial profit-taking level is hit.

    Default levels: take 25% at +10%, another 25% at +20%.

    Returns:
        dict with level info if a level is hit, None otherwise
    """
    if levels is None:
        levels = [
            {"profit_pct": 0.10, "sell_pct": 0.25, "label": "10% profit — sell 25%"},
            {"profit_pct": 0.20, "sell_pct": 0.25, "label": "20% profit — sell 25%"},
        ]

    current_profit_pct = (current_price - entry_price) / entry_price if entry_price > 0 else 0

    for level in levels:
        if current_profit_pct >= level["profit_pct"]:
            return {
                "hit": True,
                "profit_pct": current_profit_pct,
                "sell_pct": level["sell_pct"],
                "label": level["label"],
            }

    return None


def reset_peak(symbol: str):
    """Reset peak price tracking for a symbol (after selling)."""
    _peak_prices.pop(symbol, None)


def get_all_peaks() -> dict[str, float]:
    """Get all tracked peak prices."""
    return dict(_peak_prices)
