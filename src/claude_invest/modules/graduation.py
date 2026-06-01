"""
Trade Graduation Engine
=======================
When a trading position hits RSI > 80 (sell trigger), checks if the stock
should graduate to core holdings instead of being sold.

Criteria: hold_days >= 5, gain >= 10%, sentiment > 0.15 with 3+ articles,
price above 20-day SMA.
"""
import logging
from datetime import datetime, timezone

from ruamel.yaml import YAML

from claude_invest.modules.db import Database
from claude_invest.modules.notify import send_alert
from claude_invest.modules.sentiment import analyze_sentiment
from claude_invest.modules.technicals import analyze_technicals

logger = logging.getLogger(__name__)


def _get_hold_days(symbol: str, db: Database) -> int:
    """Get days since first buy of this symbol in current position."""
    trades = db.get_trades(symbol=symbol, limit=100)
    buys = [t for t in trades if t["side"] == "buy"]
    if not buys:
        return 0
    # Oldest buy (last in list since ordered DESC)
    oldest_buy = buys[-1]
    buy_dt = datetime.fromisoformat(oldest_buy["timestamp"])
    if buy_dt.tzinfo is None:
        buy_dt = buy_dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - buy_dt).days


def check_graduation(symbol: str, config: dict, db: Database, portfolio: dict) -> dict:
    """Check if a trading position should graduate to core holdings.

    Returns:
        {"decision": "graduate"|"sell", "reason": str, "criteria": dict}
    """
    grad_cfg = config.get("graduation", {})
    min_hold_days = grad_cfg.get("min_hold_days", 5)
    min_gain_pct = grad_cfg.get("min_gain_pct", 0.10)
    min_sentiment = grad_cfg.get("min_sentiment", 0.15)
    min_articles = grad_cfg.get("min_articles", 3)

    # Find position in portfolio
    position = None
    for p in portfolio.get("positions", []):
        if p["symbol"] == symbol:
            position = p
            break

    if not position:
        return {"decision": "sell", "reason": "Position not found in portfolio", "criteria": {}}

    # Criterion 1: Hold duration
    hold_days = _get_hold_days(symbol, db)
    if hold_days < min_hold_days:
        return {
            "decision": "sell",
            "reason": f"Insufficient hold days: {hold_days} < {min_hold_days}",
            "criteria": {"hold_days": hold_days, "min_required": min_hold_days},
        }

    # Criterion 2: Profit threshold
    gain_pct = position["unrealized_pl"] / (position["qty"] * position["avg_entry_price"])
    if gain_pct < min_gain_pct:
        return {
            "decision": "sell",
            "reason": f"Insufficient gain: {gain_pct:.1%} < {min_gain_pct:.0%}",
            "criteria": {"gain_pct": gain_pct, "min_required": min_gain_pct},
        }

    # Criterion 3: Sentiment
    try:
        sentiment = analyze_sentiment(symbol)
    except Exception as e:
        logger.warning("Sentiment check failed for %s: %s", symbol, e)
        return {"decision": "sell", "reason": f"Sentiment check failed: {e}", "criteria": {}}

    score = sentiment.get("score", 0)
    articles = sentiment.get("article_count", 0)
    if score < min_sentiment or articles < min_articles:
        return {
            "decision": "sell",
            "reason": f"Low sentiment: score={score:.2f} (need {min_sentiment}), articles={articles} (need {min_articles})",
            "criteria": {"sentiment_score": score, "article_count": articles},
        }

    # Criterion 4: Price above SMA20
    try:
        tech = analyze_technicals(symbol)
    except Exception as e:
        logger.warning("Technicals check failed for %s: %s", symbol, e)
        return {"decision": "sell", "reason": f"Technicals check failed: {e}", "criteria": {}}

    current_price = tech.get("current_price", 0)
    sma_20 = tech.get("sma_20", 0)
    if sma_20 and current_price < sma_20:
        return {
            "decision": "sell",
            "reason": f"Price below SMA20: ${current_price:.2f} < ${sma_20:.2f} (trend weakening)",
            "criteria": {"price": current_price, "sma_20": sma_20},
        }

    # ALL CRITERIA PASS -> Graduate
    criteria = {
        "hold_days": hold_days,
        "gain_pct": gain_pct,
        "sentiment_score": score,
        "article_count": articles,
        "price": current_price,
        "sma_20": sma_20,
    }

    return {"decision": "graduate", "reason": "All graduation criteria met", "criteria": criteria}


def execute_graduation(symbol: str, config: dict, db: Database, portfolio: dict, config_path: str) -> dict:
    """Execute the graduation: add to buy_list, record in DB.

    Returns:
        dict with graduation details
    """
    grad_cfg = config.get("graduation", {})
    probation_weight = grad_cfg.get("probation_weight", 0.035)

    # Find position details
    position = None
    for p in portfolio.get("positions", []):
        if p["symbol"] == symbol:
            position = p
            break

    if not position:
        return {"error": "Position not found"}

    entry_price = position["avg_entry_price"]
    graduation_price = position["current_price"]
    hold_days = _get_hold_days(symbol, db)
    gain_pct = position["unrealized_pl"] / (position["qty"] * entry_price)

    # Get sentiment for record
    try:
        sentiment = analyze_sentiment(symbol)
        sentiment_score = sentiment.get("score", 0)
    except Exception:
        sentiment_score = None

    # Record in DB
    db.insert_graduation({
        "symbol": symbol,
        "entry_price": entry_price,
        "graduation_price": graduation_price,
        "hold_days": hold_days,
        "gain_pct": gain_pct,
        "sentiment_score": sentiment_score,
    })

    # Update settings.yaml - add to buy_list at probation weight
    _add_to_buy_list(config_path, symbol, "general", probation_weight)

    logger.info(
        "GRADUATED %s: held %d days, +%.1f%%, sentiment %.2f. Added to core at %.1f%% weight.",
        symbol, hold_days, gain_pct * 100, sentiment_score or 0, probation_weight * 100,
    )
    send_alert(
        f"GRADUATED {symbol}: held {hold_days}d, +{gain_pct*100:.1f}%, "
        f"sentiment {sentiment_score or 0:.2f}. Added to core at {probation_weight*100:.1f}% weight.",
        "graduation",
    )

    return {
        "symbol": symbol,
        "entry_price": entry_price,
        "graduation_price": graduation_price,
        "hold_days": hold_days,
        "gain_pct": gain_pct,
        "sentiment_score": sentiment_score,
        "status": "probation",
        "weight": probation_weight,
    }


def _add_to_buy_list(config_path: str, symbol: str, sector: str, weight: float):
    """Add a symbol to core_holdings.buy_list in settings.yaml."""
    yaml = YAML()
    yaml.preserve_quotes = True

    with open(config_path, "r") as f:
        data = yaml.load(f)

    buy_list = data.get("core_holdings", {}).get("buy_list", [])

    # Check if already in list
    existing_symbols = {item["symbol"] for item in buy_list}
    if symbol in existing_symbols:
        return

    # Add new entry
    buy_list.append({"symbol": symbol, "sector": sector, "weight": float(weight)})
    data["core_holdings"]["buy_list"] = buy_list

    with open(config_path, "w") as f:
        yaml.dump(data, f)
