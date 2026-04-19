import os

from alpaca.trading.client import TradingClient
from dotenv import load_dotenv

load_dotenv()


def _get_trading_client() -> TradingClient:
    return TradingClient(
        api_key=os.environ["ALPACA_API_KEY"],
        secret_key=os.environ["ALPACA_SECRET_KEY"],
        paper=os.environ.get("ALPACA_BASE_URL", "").startswith("https://paper"),
    )


def get_portfolio() -> dict:
    client = _get_trading_client()
    account = client.get_account()
    positions_raw = client.get_all_positions()

    equity = float(account.equity)
    last_equity = float(account.last_equity)

    positions = []
    for p in positions_raw:
        positions.append({
            "symbol": p.symbol,
            "qty": float(p.qty),
            "avg_entry_price": float(p.avg_entry_price),
            "current_price": float(p.current_price),
            "unrealized_pl": float(p.unrealized_pl),
            "market_value": float(p.market_value),
        })

    return {
        "equity": equity,
        "cash": float(account.cash),
        "buying_power": float(account.buying_power),
        "daily_pnl": round(equity - last_equity, 2),
        "positions": positions,
        "position_count": len(positions),
    }
