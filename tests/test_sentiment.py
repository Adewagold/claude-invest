import pytest
from unittest.mock import MagicMock, patch
from claude_invest.modules.sentiment import analyze_sentiment, score_headline


def test_score_headline_positive():
    score = score_headline("Apple reports record revenue beating all expectations")
    assert score > 0


def test_score_headline_negative():
    score = score_headline("Company faces massive lawsuit and regulatory investigation")
    assert score < 0


def test_score_headline_neutral():
    score = score_headline("Company schedules quarterly earnings call")
    assert -0.2 <= score <= 0.2


def _mock_news(headlines):
    articles = []
    for h in headlines:
        article = MagicMock()
        article.headline = h
        article.summary = h
        articles.append(article)
    return articles


@patch("claude_invest.modules.sentiment._get_news_client")
def test_analyze_sentiment_aggregates_scores(mock_client_fn):
    client = MagicMock()
    client.get_news.return_value = _mock_news([
        "Stock surges on incredible earnings beat",
        "Record profits drive shares higher",
        "Analysts raise price targets after strong quarter",
    ])
    mock_client_fn.return_value = client

    result = analyze_sentiment("AAPL")

    assert result["ticker"] == "AAPL"
    assert result["score"] > 0
    assert result["article_count"] == 3
    assert -1 <= result["score"] <= 1


@patch("claude_invest.modules.sentiment._get_news_client")
def test_analyze_sentiment_no_news(mock_client_fn):
    client = MagicMock()
    client.get_news.return_value = []
    mock_client_fn.return_value = client

    result = analyze_sentiment("XYZ")

    assert result["score"] == 0.0
    assert result["article_count"] == 0
