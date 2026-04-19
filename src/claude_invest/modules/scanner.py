import os

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockSnapshotRequest, MostActivesRequest
from alpaca.data.historical.screener import ScreenerClient
from dotenv import load_dotenv

from claude_invest.modules.sentiment import analyze_sentiment

load_dotenv()

# Default thresholds — overridden by config
DEFAULT_MIN_VOLUME = 2.0
DEFAULT_MIN_NEWS = 2
DEFAULT_MIN_SENTIMENT = 0.3


def _get_most_active_tickers(top_n: int = 20) -> list[str]:
    api_key = os.environ["ALPACA_API_KEY"]
    secret_key = os.environ["ALPACA_SECRET_KEY"]
    client = ScreenerClient(api_key, secret_key)
    request = MostActivesRequest(top=top_n)
    response = client.get_most_actives(request)
    return [item.symbol for item in response.most_actives]


def _get_snapshot(ticker: str) -> dict:
    api_key = os.environ["ALPACA_API_KEY"]
    secret_key = os.environ["ALPACA_SECRET_KEY"]
    client = StockHistoricalDataClient(api_key, secret_key)
    snapshot = client.get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=ticker))

    if ticker not in snapshot:
        return {"volume_ratio": 0.0}

    snap = snapshot[ticker]

    # Handle both dict and object responses from alpaca-py
    if isinstance(snap, dict):
        daily_bar = snap.get("daily_bar", {})
        prev_bar = snap.get("previous_daily_bar", {})
        daily_vol = float(daily_bar.get("volume", 0)) if daily_bar else 0
        prev_vol = float(prev_bar.get("volume", 1)) if prev_bar else 1
    else:
        daily_vol = float(snap.daily_bar.volume) if snap.daily_bar else 0
        prev_vol = float(snap.previous_daily_bar.volume) if snap.previous_daily_bar else 1

    volume_ratio = daily_vol / prev_vol if prev_vol > 0 else 0.0

    return {"volume_ratio": round(volume_ratio, 2)}


def score_ticker(
    volume_ratio: float,
    sentiment_score: float,
    news_count: int,
    min_volume: float = DEFAULT_MIN_VOLUME,
    min_news: int = DEFAULT_MIN_NEWS,
    min_sentiment: float = DEFAULT_MIN_SENTIMENT,
) -> dict:
    volume_pass = volume_ratio >= min_volume
    sentiment_pass = sentiment_score >= min_sentiment and news_count >= min_news

    flagged = volume_pass and sentiment_pass
    combined_score = (volume_ratio * 0.4) + (sentiment_score * 0.6) if flagged else 0.0

    return {
        "flagged": flagged,
        "combined_score": round(combined_score, 4),
        "volume_ratio": volume_ratio,
        "sentiment_score": sentiment_score,
        "news_count": news_count,
    }


def scan_market(config: dict) -> list[dict]:
    disc = config.get("discovery", {})
    min_vol = disc.get("min_relative_volume", DEFAULT_MIN_VOLUME)
    min_news = disc.get("min_news_count", DEFAULT_MIN_NEWS)
    min_sent = disc.get("sentiment_threshold", DEFAULT_MIN_SENTIMENT)

    tickers = _get_most_active_tickers()
    results = []

    for ticker in tickers:
        snapshot = _get_snapshot(ticker)
        sentiment = analyze_sentiment(ticker)

        scored = score_ticker(
            volume_ratio=snapshot["volume_ratio"],
            sentiment_score=sentiment["score"],
            news_count=sentiment["article_count"],
            min_volume=min_vol,
            min_news=min_news,
            min_sentiment=min_sent,
        )
        scored["ticker"] = ticker
        results.append(scored)

    results.sort(key=lambda x: x["combined_score"], reverse=True)
    return results
