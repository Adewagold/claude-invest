import json
from datetime import datetime, timezone

from claude_invest.modules.db import Database


def parse_signal_combo(snapshot: dict) -> str:
    parts = []

    rsi = snapshot.get("rsi")
    if rsi is not None:
        if rsi < 30:
            parts.append("rsi_0_30")
        elif rsi < 50:
            parts.append("rsi_30_50")
        elif rsi < 70:
            parts.append("rsi_50_70")
        else:
            parts.append("rsi_70_100")

    macd = snapshot.get("macd")
    macd_sig = snapshot.get("macd_signal")
    if macd is not None and macd_sig is not None:
        if macd > macd_sig:
            parts.append("macd_above_signal")
        else:
            parts.append("macd_below_signal")

    trend = snapshot.get("trend")
    if trend:
        parts.append(f"trend_{trend}")

    sentiment = snapshot.get("sentiment")
    if sentiment is not None:
        if sentiment > 0.3:
            parts.append("sent_positive")
        elif sentiment < -0.2:
            parts.append("sent_negative")
        else:
            parts.append("sent_neutral")

    return " + ".join(sorted(parts)) if parts else "unknown"


def _match_trades(db: Database) -> list[dict]:
    trades = db.get_trades(limit=500)
    decisions = db.get_decisions(limit=500)

    buy_decisions = [d for d in decisions if d["action"] == "buy"]
    sell_decisions = [d for d in decisions if d["action"] == "sell"]

    matched = []
    for buy in buy_decisions:
        ticker = buy["ticker"]
        buy_time = buy["timestamp"]

        sell = None
        for s in sell_decisions:
            if s["ticker"] == ticker and s["timestamp"] >= buy_time:
                sell = s
                break

        try:
            entry_signals = json.loads(buy.get("signals_snapshot", "{}"))
        except (json.JSONDecodeError, TypeError):
            entry_signals = {}

        entry_price = entry_signals.get("price", 0)

        if sell:
            try:
                exit_signals = json.loads(sell.get("signals_snapshot", "{}"))
            except (json.JSONDecodeError, TypeError):
                exit_signals = {}
            exit_price = exit_signals.get("price", 0)
            pnl = exit_price - entry_price if entry_price > 0 else 0
            status = "closed"
        else:
            exit_price = 0
            pnl = 0
            status = "open"

        matched.append({
            "ticker": ticker,
            "entry_time": buy_time,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": pnl,
            "win": pnl > 0,
            "status": status,
            "signal_combo": parse_signal_combo(entry_signals),
            "entry_signals": entry_signals,
            "reasoning": buy.get("reasoning", ""),
        })

    return matched


def score_patterns(db: Database) -> list[dict]:
    matched = _match_trades(db)
    closed = [m for m in matched if m["status"] == "closed"]

    combos: dict[str, dict] = {}
    for trade in closed:
        combo = trade["signal_combo"]
        if combo not in combos:
            combos[combo] = {"wins": 0, "losses": 0, "total_pnl": 0.0, "trades": []}
        if trade["win"]:
            combos[combo]["wins"] += 1
        else:
            combos[combo]["losses"] += 1
        combos[combo]["total_pnl"] += trade["pnl"]
        combos[combo]["trades"].append(trade["ticker"])

    patterns = []
    for combo, data in combos.items():
        total = data["wins"] + data["losses"]
        win_rate = data["wins"] / total if total > 0 else 0
        confidence = "high" if total >= 3 else "low"
        patterns.append({
            "signal_combo": combo,
            "wins": data["wins"],
            "losses": data["losses"],
            "total": total,
            "win_rate": round(win_rate, 4),
            "avg_pnl": round(data["total_pnl"] / total, 4) if total > 0 else 0,
            "confidence": confidence,
            "tickers": data["trades"],
        })

    patterns.sort(key=lambda x: x["win_rate"], reverse=True)
    return patterns


def analyze_day(db: Database, date: str | None = None) -> dict:
    matched = _match_trades(db)
    closed = [m for m in matched if m["status"] == "closed"]

    wins = sum(1 for t in closed if t["win"])
    losses = sum(1 for t in closed if not t["win"])
    total = wins + losses
    total_pnl = sum(t["pnl"] for t in closed)

    patterns = score_patterns(db)

    mistakes = []
    for t in closed:
        if not t["win"] and t["entry_signals"].get("rsi", 0) > 70:
            mistakes.append(
                f"Bought {t['ticker']} at RSI {t['entry_signals']['rsi']:.1f} — lost"
            )

    return {
        "date": date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / total, 4) if total > 0 else 0,
        "total_pnl": round(total_pnl, 4),
        "patterns": patterns,
        "mistakes": mistakes,
        "open_positions": [m for m in matched if m["status"] == "open"],
    }
