import os
from datetime import datetime, timedelta, timezone

from alpaca.data.historical.news import NewsClient
from alpaca.data.requests import NewsRequest
from dotenv import load_dotenv
from textblob import TextBlob

load_dotenv()

# Financial domain keywords to augment TextBlob's general-purpose lexicon,
# which lacks coverage for business/market vocabulary.
_POSITIVE_KEYWORDS = {
    "beat", "beats", "beating", "record", "surge", "surges", "surging",
    "profit", "profits", "revenue", "growth", "strong", "raise", "raises",
    "upgrade", "upgrades", "higher", "gain", "gains", "rally", "bullish",
    "outperform", "exceed", "exceeds", "exceeded", "boost", "boosts",
    "recovery", "rebound", "expansion",
}
_NEGATIVE_KEYWORDS = {
    "lawsuit", "investigation", "fraud", "scandal", "loss", "losses",
    "downgrade", "downgrades", "decline", "declines", "fell", "drop",
    "drops", "miss", "misses", "missed", "cut", "cuts", "layoff", "layoffs",
    "bankruptcy", "warning", "recall", "fine", "penalty", "charges",
    "regulatory", "probe", "violation", "default", "shortfall",
}
_KEYWORD_WEIGHT = 0.15


def _get_news_client() -> NewsClient:
    return NewsClient(
        api_key=os.environ["ALPACA_API_KEY"],
        secret_key=os.environ["ALPACA_SECRET_KEY"],
    )


def score_headline(text: str) -> float:
    """Score a text string on a -1.0 (negative) to +1.0 (positive) scale.

    Uses TextBlob as the base NLP scorer and augments with a financial-domain
    keyword list to handle market/business vocabulary not in TextBlob's lexicon.
    """
    base_score = TextBlob(text).sentiment.polarity

    words = set(text.lower().split())
    pos_hits = len(words & _POSITIVE_KEYWORDS)
    neg_hits = len(words & _NEGATIVE_KEYWORDS)
    keyword_boost = (pos_hits - neg_hits) * _KEYWORD_WEIGHT

    combined = base_score + keyword_boost
    return round(max(-1.0, min(1.0, combined)), 4)


def analyze_sentiment(ticker: str, lookback_hours: int = 24) -> dict:
    """Fetch recent news for a ticker and return an aggregate sentiment score.

    Returns a dict with keys:
        ticker        - the input ticker symbol
        score         - average sentiment score clamped to [-1, 1]
        article_count - number of articles analysed
        headlines     - list of {headline, score} dicts
    """
    client = _get_news_client()
    start = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    request = NewsRequest(
        symbols=ticker,
        start=start,
        limit=20,
        sort="desc",
    )
    articles = client.get_news(request)

    if not articles:
        return {
            "ticker": ticker,
            "score": 0.0,
            "article_count": 0,
            "headlines": [],
        }

    scores = []
    headlines = []
    for article in articles:
        text = (
            f"{article.headline}. {article.summary}"
            if article.summary
            else article.headline
        )
        s = score_headline(text)
        scores.append(s)
        headlines.append({"headline": article.headline, "score": s})

    avg_score = round(sum(scores) / len(scores), 4)

    return {
        "ticker": ticker,
        "score": max(-1.0, min(1.0, avg_score)),
        "article_count": len(articles),
        "headlines": headlines,
    }
