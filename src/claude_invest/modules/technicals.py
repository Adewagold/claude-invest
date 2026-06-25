import os

import pandas as pd
import ta
from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

_TIMEFRAME_MAP = {
    "1Hour": TimeFrame.Hour,
    "1Day": TimeFrame.Day,
    "15Min": TimeFrame(15, TimeFrameUnit.Minute),
    "5Min": TimeFrame(5, TimeFrameUnit.Minute),
    "1Min": TimeFrame.Minute,
}


def _normalize_crypto_ticker(ticker: str) -> str:
    """Convert BTCUSD -> BTC/USD so the crypto client is used."""
    if "/" in ticker:
        return ticker
    if ticker.upper().endswith("USD") and len(ticker) > 3:
        base = ticker[:-3]
        return f"{base}/USD"
    return ticker


def _get_bars(ticker: str, days: int = 60, timeframe: str = "1Hour") -> pd.DataFrame:
    api_key = os.environ["ALPACA_API_KEY"]
    secret_key = os.environ["ALPACA_SECRET_KEY"]
    start = datetime.now(timezone.utc) - timedelta(days=days)
    tf = _TIMEFRAME_MAP.get(timeframe, TimeFrame.Hour)
    ticker = _normalize_crypto_ticker(ticker)

    if "/" in ticker:
        client = CryptoHistoricalDataClient(api_key, secret_key)
        request = CryptoBarsRequest(
            symbol_or_symbols=ticker, timeframe=tf, start=start
        )
        bars = client.get_crypto_bars(request)
    else:
        client = StockHistoricalDataClient(api_key, secret_key)
        request = StockBarsRequest(
            symbol_or_symbols=ticker, timeframe=tf, start=start
        )
        bars = client.get_stock_bars(request)

    df = bars.df.reset_index()
    df.columns = [c.lower() for c in df.columns]
    return df


def compute_indicators(df: pd.DataFrame) -> dict:
    close = df["close"]
    high = df["high"]
    low = df["low"]

    rsi = ta.momentum.rsi(close, window=14)
    macd_line = ta.trend.macd(close)
    macd_signal = ta.trend.macd_signal(close)
    sma_20 = ta.trend.sma_indicator(close, window=20)
    sma_50 = ta.trend.sma_indicator(close, window=50)

    current_price = float(close.iloc[-1])
    current_sma_20 = float(sma_20.iloc[-1]) if pd.notna(sma_20.iloc[-1]) else None
    current_sma_50 = float(sma_50.iloc[-1]) if pd.notna(sma_50.iloc[-1]) else None

    # Determine trend
    if current_sma_20 and current_sma_50:
        if current_price > current_sma_20 > current_sma_50:
            trend = "bullish"
        elif current_price < current_sma_20 < current_sma_50:
            trend = "bearish"
        else:
            trend = "neutral"
    else:
        trend = "neutral"

    return {
        "current_price": current_price,
        "rsi": round(float(rsi.iloc[-1]), 2) if pd.notna(rsi.iloc[-1]) else None,
        "macd": round(float(macd_line.iloc[-1]), 4) if pd.notna(macd_line.iloc[-1]) else None,
        "macd_signal": round(float(macd_signal.iloc[-1]), 4) if pd.notna(macd_signal.iloc[-1]) else None,
        "sma_20": round(current_sma_20, 2) if current_sma_20 else None,
        "sma_50": round(current_sma_50, 2) if current_sma_50 else None,
        "trend": trend,
    }


def analyze_technicals(ticker: str, timeframe: str = "1Hour") -> dict:
    df = _get_bars(ticker, timeframe=timeframe)
    indicators = compute_indicators(df)
    indicators["ticker"] = ticker
    return indicators
