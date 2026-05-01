"""
Volatility Scanner — ranks high-ATR stock candidates for the scalp engine.

Public API:
    scan_volatile_stocks(config: dict) -> list[dict]
"""

import os
from datetime import datetime, timedelta, timezone

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from dotenv import load_dotenv

load_dotenv()


def _get_alpaca_client() -> StockHistoricalDataClient:
    return StockHistoricalDataClient(
        os.environ["ALPACA_API_KEY"],
        os.environ["ALPACA_SECRET_KEY"],
    )


def _compute_atr_pct(ticker: str, lookback_days: int, client: StockHistoricalDataClient) -> float:
    """Return ATR as a fraction of price over lookback_days daily bars."""
    start = datetime.now(timezone.utc) - timedelta(days=lookback_days + 5)
    req = StockBarsRequest(symbol_or_symbols=ticker, timeframe=TimeFrame.Day, start=start)
    bars = client.get_stock_bars(req).df.reset_index()
    bars.columns = [c.lower() for c in bars.columns]
    if len(bars) < 2:
        return 0.0
    tr = (bars["high"] - bars["low"]).abs()
    atr = tr.rolling(min(14, len(tr))).mean().iloc[-1]
    price = float(bars["close"].iloc[-1])
    return float(atr / price) if price else 0.0


def _compute_volume_ratio(ticker: str, lookback_days: int, client: StockHistoricalDataClient) -> float:
    """Return today's volume divided by the 20-day average daily volume."""
    start = datetime.now(timezone.utc) - timedelta(days=lookback_days + 5)
    req = StockBarsRequest(symbol_or_symbols=ticker, timeframe=TimeFrame.Day, start=start)
    bars = client.get_stock_bars(req).df.reset_index()
    bars.columns = [c.lower() for c in bars.columns]
    if len(bars) < 2:
        return 1.0
    avg_volume = float(bars["volume"].iloc[:-1].mean())
    today_volume = float(bars["volume"].iloc[-1])
    return round(today_volume / avg_volume, 2) if avg_volume else 1.0


def _compute_intraday_change(ticker: str, client: StockHistoricalDataClient) -> float:
    """Return % change from yesterday's close to today's latest trade."""
    start = datetime.now(timezone.utc) - timedelta(days=5)
    req = StockBarsRequest(symbol_or_symbols=ticker, timeframe=TimeFrame.Day, start=start)
    bars = client.get_stock_bars(req).df.reset_index()
    bars.columns = [c.lower() for c in bars.columns]
    if len(bars) < 2:
        return 0.0
    prev_close = float(bars["close"].iloc[-2])
    latest_close = float(bars["close"].iloc[-1])
    return round((latest_close - prev_close) / prev_close, 4) if prev_close else 0.0


def _fetch_stock_metrics(ticker: str, scalper_config: dict) -> dict:
    """Fetch ATR%, intraday change, and volume ratio for a single ticker."""
    client = _get_alpaca_client()
    lookback = scalper_config.get("discovery", {}).get("lookback_days", 20)
    atr_pct = _compute_atr_pct(ticker, lookback, client)
    intraday_change = _compute_intraday_change(ticker, client)
    volume_ratio = _compute_volume_ratio(ticker, lookback, client)
    return {
        "ticker": ticker,
        "atr_pct": round(atr_pct, 4),
        "intraday_change": intraday_change,
        "volume_ratio": volume_ratio,
    }


def _score(metrics: dict) -> float:
    """Composite score: (atr_pct * 0.5) + (abs(intraday_change) * 0.3) + (volume_ratio * 0.2)."""
    return (
        metrics["atr_pct"] * 0.5
        + abs(metrics["intraday_change"]) * 0.3
        + metrics["volume_ratio"] * 0.2
    )


def _discover_volatile_stocks(scalper_config: dict) -> list[str]:
    """
    Return a list of ticker symbols discovered via a broad scan.

    Currently returns an empty list — discovery via pre-defined broader universe
    can be wired in here. The interface is extracted so it can be mocked in tests.
    """
    # Future: query Alpaca screener / pre-defined universe and filter by ATR%.
    return []


def scan_volatile_stocks(config: dict) -> list[dict]:
    """
    Return a ranked list of volatile stock candidates.

    Args:
        config: full settings dict (reads from config["volatility_scalper"])

    Returns:
        List of dicts with keys: ticker, atr_pct, intraday_change,
        volume_ratio, source ("curated" | "discovered"), rank (1-indexed).
    """
    scalper_cfg = config.get("volatility_scalper", {})
    discovery_cfg = scalper_cfg.get("discovery", {})
    min_atr_pct = discovery_cfg.get("min_atr_pct", 0.04)
    discovery_enabled = discovery_cfg.get("enabled", False)

    curated_tickers: list[str] = scalper_cfg.get("watchlist", [])
    discovered_tickers: list[str] = (
        _discover_volatile_stocks(scalper_cfg) if discovery_enabled else []
    )

    # Remove duplicates: curated takes priority
    all_tickers = list(curated_tickers) + [
        t for t in discovered_tickers if t not in curated_tickers
    ]

    candidates: list[dict] = []
    for ticker in all_tickers:
        metrics = _fetch_stock_metrics(ticker, scalper_cfg)
        source = "curated" if ticker in curated_tickers else "discovered"

        # Filter discovered tickers below ATR threshold; always include curated
        if source == "discovered" and metrics["atr_pct"] < min_atr_pct:
            continue

        candidates.append({**metrics, "source": source})

    # Sort: curated first (preserving score order within curated), then discovered by score
    curated_sorted = sorted(
        [c for c in candidates if c["source"] == "curated"],
        key=_score,
        reverse=True,
    )
    discovered_sorted = sorted(
        [c for c in candidates if c["source"] == "discovered"],
        key=_score,
        reverse=True,
    )

    ranked = curated_sorted + discovered_sorted
    for i, item in enumerate(ranked, start=1):
        item["rank"] = i

    return ranked
