import pytest
from unittest.mock import patch
from claude_invest.modules.earnings import check_earnings_soon, check_portfolio_earnings


def test_check_earnings_detects_keywords():
    mock_sentiment = {
        "ticker": "SNDK",
        "score": 0.2,
        "article_count": 3,
        "headlines": [
            {"headline": "Earnings Scheduled For April 30, 2026", "score": 0.0},
            {"headline": "SNDK Q2 Revenue Beats Estimates", "score": 0.3},
            {"headline": "AI Memory Demand Rising", "score": 0.1},
        ],
    }
    with patch("claude_invest.modules.earnings.analyze_sentiment", return_value=mock_sentiment):
        result = check_earnings_soon("SNDK")
        assert result["has_earnings_soon"] is True
        assert result["earnings_headline_count"] == 2
        assert "HIGH RISK" not in result["recommendation"]  # Only 2, need 3 for HIGH RISK
        assert "WATCH" in result["recommendation"]


def test_check_earnings_high_risk():
    mock_sentiment = {
        "ticker": "SNDK",
        "score": 0.2,
        "article_count": 5,
        "headlines": [
            {"headline": "Earnings Scheduled For April 30, 2026", "score": 0.0},
            {"headline": "SNDK Q2 Revenue Beats Estimates", "score": 0.3},
            {"headline": "SNDK EPS Guidance Raised", "score": 0.4},
            {"headline": "Quarterly Results Beat", "score": 0.2},
        ],
    }
    with patch("claude_invest.modules.earnings.analyze_sentiment", return_value=mock_sentiment):
        result = check_earnings_soon("SNDK")
        assert result["has_earnings_soon"] is True
        assert result["earnings_headline_count"] == 4
        assert "HIGH RISK" in result["recommendation"]


def test_check_earnings_no_earnings():
    mock_sentiment = {
        "ticker": "AAPL",
        "score": 0.1,
        "article_count": 2,
        "headlines": [
            {"headline": "Apple Launches New iPhone", "score": 0.2},
            {"headline": "Tech Stocks Rally", "score": 0.1},
        ],
    }
    with patch("claude_invest.modules.earnings.analyze_sentiment", return_value=mock_sentiment):
        result = check_earnings_soon("AAPL")
        assert result["has_earnings_soon"] is False
        assert result["earnings_headline_count"] == 0
        assert "No earnings signals" in result["recommendation"]


def test_check_portfolio_earnings_skips_crypto():
    positions = [
        {"symbol": "BTC/USD", "market_value": 100},
        {"symbol": "AAPL", "market_value": 50},
    ]
    mock_sentiment = {
        "ticker": "AAPL", "score": 0.1, "article_count": 0, "headlines": [],
    }
    with patch("claude_invest.modules.earnings.analyze_sentiment", return_value=mock_sentiment):
        results = check_portfolio_earnings(positions)
        symbols = [r["ticker"] for r in results]
        assert "BTC/USD" not in symbols
        assert "AAPL" in symbols


def test_check_portfolio_earnings_sorted_by_risk():
    positions = [
        {"symbol": "LOW_RISK", "market_value": 100},
        {"symbol": "HIGH_RISK", "market_value": 200},
    ]

    def mock_sentiment(ticker):
        if ticker == "HIGH_RISK":
            return {
                "ticker": ticker, "score": 0.1, "article_count": 4,
                "headlines": [
                    {"headline": "earnings report", "score": 0.0},
                    {"headline": "quarterly results", "score": 0.1},
                    {"headline": "revenue beat", "score": 0.2},
                    {"headline": "eps guidance", "score": 0.3},
                ],
            }
        return {"ticker": ticker, "score": 0.1, "article_count": 0, "headlines": []}

    with patch("claude_invest.modules.earnings.analyze_sentiment", side_effect=mock_sentiment):
        results = check_portfolio_earnings(positions)
        assert results[0]["ticker"] == "HIGH_RISK"
        assert results[1]["ticker"] == "LOW_RISK"


def test_check_portfolio_earnings_includes_position_data():
    positions = [{"symbol": "TSLA", "market_value": 1500.0, "unrealized_pl": 250.0}]
    mock_sentiment = {
        "ticker": "TSLA", "score": 0.1, "article_count": 1,
        "headlines": [{"headline": "Tesla earnings beat", "score": 0.3}],
    }
    with patch("claude_invest.modules.earnings.analyze_sentiment", return_value=mock_sentiment):
        results = check_portfolio_earnings(positions)
        assert results[0]["current_value"] == 1500.0
        assert results[0]["unrealized_pl"] == 250.0
