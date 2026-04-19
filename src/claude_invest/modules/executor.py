import os

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from dotenv import load_dotenv

load_dotenv()


def _get_trading_client() -> TradingClient:
    return TradingClient(
        api_key=os.environ["ALPACA_API_KEY"],
        secret_key=os.environ["ALPACA_SECRET_KEY"],
        paper=os.environ.get("ALPACA_BASE_URL", "").startswith("https://paper"),
    )


def execute_order(symbol: str, side: str, qty: float) -> dict:
    try:
        client = _get_trading_client()

        order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL
        time_in_force = TimeInForce.GTC if "/" in symbol else TimeInForce.DAY

        request = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=order_side,
            time_in_force=time_in_force,
        )

        order = client.submit_order(request)

        return {
            "order_id": str(order.id),
            "symbol": order.symbol,
            "side": side,
            "qty": float(order.qty),
            "filled_price": float(order.filled_avg_price) if order.filled_avg_price else None,
            "status": str(order.status),
            "submitted_at": str(order.submitted_at),
        }

    except Exception as e:
        return {
            "order_id": None,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "status": "error",
            "error": str(e),
        }
