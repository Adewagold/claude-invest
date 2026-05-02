"""Earnings calendar — checks if a stock has upcoming earnings."""

from claude_invest.modules.sentiment import analyze_sentiment


def check_earnings_soon(ticker: str, days_ahead: int = 3) -> dict:
    """Check if a stock has earnings coming up within N days.

    Uses sentiment/news analysis to detect earnings-related headlines.
    Not perfect but catches most cases.

    Returns:
        dict with has_earnings_soon (bool), earnings_headline_count (int), headlines, recommendation
    """
    sentiment = analyze_sentiment(ticker)

    earnings_keywords = [
        "earnings", "quarterly", "q1", "q2", "q3", "q4",
        "revenue", "eps", "guidance", "outlook",
        "beat", "miss", "results", "report",
    ]

    earnings_headlines = []
    for h in sentiment.get("headlines", []):
        headline_lower = h["headline"].lower()
        if any(kw in headline_lower for kw in earnings_keywords):
            earnings_headlines.append(h["headline"])

    return {
        "ticker": ticker,
        "has_earnings_soon": len(earnings_headlines) > 0,
        "earnings_headline_count": len(earnings_headlines),
        "earnings_headlines": earnings_headlines[:5],
        "recommendation": _get_recommendation(len(earnings_headlines), ticker),
    }


def _get_recommendation(headline_count: int, ticker: str) -> str:
    if headline_count >= 3:
        return (
            f"HIGH RISK: {ticker} likely has earnings very soon. "
            "Consider reducing position or setting tight stops."
        )
    elif headline_count >= 1:
        return f"WATCH: {ticker} may have upcoming earnings. Monitor closely."
    return f"No earnings signals detected for {ticker}."


def check_portfolio_earnings(positions: list[dict]) -> list[dict]:
    """Check all portfolio positions for upcoming earnings.

    Args:
        positions: List of position dicts with 'symbol' key

    Returns:
        List of positions with earnings info, sorted by risk (highest first)
    """
    results = []
    for pos in positions:
        symbol = pos.get("symbol", "")
        if "/" in symbol:  # Skip crypto
            continue
        try:
            earnings = check_earnings_soon(symbol)
            earnings["current_value"] = pos.get("market_value", 0)
            earnings["unrealized_pl"] = pos.get("unrealized_pl", 0)
            results.append(earnings)
        except Exception:
            continue

    # Sort by headline count (most likely earnings first)
    results.sort(key=lambda x: x["earnings_headline_count"], reverse=True)
    return results
