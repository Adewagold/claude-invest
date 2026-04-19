import pytest
from unittest.mock import MagicMock, patch
from claude_invest.modules.scanner import scan_market, score_ticker


def test_score_ticker_both_signals():
    result = score_ticker(volume_ratio=3.0, sentiment_score=0.5, news_count=3)
    assert result["flagged"] is True
    assert result["combined_score"] > 0


def test_score_ticker_volume_only():
    """Volume spike alone should not flag — needs two-signal confirmation."""
    result = score_ticker(volume_ratio=3.0, sentiment_score=0.1, news_count=1)
    assert result["flagged"] is False


def test_score_ticker_sentiment_only():
    """Sentiment alone should not flag — needs volume confirmation."""
    result = score_ticker(volume_ratio=1.0, sentiment_score=0.6, news_count=5)
    assert result["flagged"] is False


def test_score_ticker_below_thresholds():
    result = score_ticker(volume_ratio=1.2, sentiment_score=0.1, news_count=0)
    assert result["flagged"] is False


@patch("claude_invest.modules.scanner._get_most_active_tickers")
@patch("claude_invest.modules.scanner._get_snapshot")
@patch("claude_invest.modules.scanner.analyze_sentiment")
def test_scan_market_returns_ranked_candidates(mock_sentiment, mock_snapshot, mock_active):
    mock_active.return_value = ["AAPL", "TSLA", "NVDA"]

    mock_snapshot.side_effect = lambda t: {"volume_ratio": 3.0 if t != "TSLA" else 1.0}
    mock_sentiment.side_effect = lambda t: {
        "ticker": t,
        "score": 0.6 if t != "TSLA" else 0.1,
        "article_count": 3 if t != "TSLA" else 0,
    }

    config = {
        "discovery": {
            "min_relative_volume": 2.0,
            "min_news_count": 2,
            "sentiment_threshold": 0.3,
        }
    }

    results = scan_market(config)

    flagged = [r for r in results if r["flagged"]]
    assert len(flagged) == 2  # AAPL and NVDA pass, TSLA doesn't
    assert all(r["ticker"] in ("AAPL", "NVDA") for r in flagged)
