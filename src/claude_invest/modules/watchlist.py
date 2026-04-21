import json
import os
from datetime import datetime, timezone

WATCHLIST_PATH = "watchlist.json"


def load_watchlist(path: str = WATCHLIST_PATH) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path) as f:
        data = json.load(f)
    return data.get("tickers", [])


def save_watchlist(tickers: list[dict], path: str = WATCHLIST_PATH):
    with open(path, "w") as f:
        json.dump({"tickers": tickers}, f, indent=2)


def add_to_watchlist(symbol: str, note: str = "", path: str = WATCHLIST_PATH) -> dict:
    tickers = load_watchlist(path)
    # Check if already exists
    existing = [t for t in tickers if t["symbol"].upper() == symbol.upper()]
    if existing:
        return {"status": "exists", "symbol": symbol}

    entry = {
        "symbol": symbol.upper(),
        "note": note,
        "added": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    tickers.append(entry)
    save_watchlist(tickers, path)
    return {"status": "added", "entry": entry}


def remove_from_watchlist(symbol: str, path: str = WATCHLIST_PATH) -> dict:
    tickers = load_watchlist(path)
    before = len(tickers)
    tickers = [t for t in tickers if t["symbol"].upper() != symbol.upper()]
    if len(tickers) == before:
        return {"status": "not_found", "symbol": symbol}
    save_watchlist(tickers, path)
    return {"status": "removed", "symbol": symbol}


def check_watchlist(tickers: list[dict], portfolio_symbols: list[str]) -> list[dict]:
    """Filter watchlist to exclude tickers we already hold."""
    held = {s.upper().replace("/USD", "").replace("USD", "") for s in portfolio_symbols}
    results = []
    for t in tickers:
        base = t["symbol"].upper().replace("/USD", "").replace("USD", "")
        t["held"] = base in held
        results.append(t)
    return results
