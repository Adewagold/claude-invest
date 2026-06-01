import os

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from dotenv import load_dotenv

from claude_invest.modules.notify import send_alert

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

        result = {
            "order_id": str(order.id),
            "symbol": order.symbol,
            "side": side,
            "qty": float(order.qty),
            "filled_price": float(order.filled_avg_price) if order.filled_avg_price else None,
            "status": str(order.status),
            "submitted_at": str(order.submitted_at),
        }

        if result.get("status") != "error":
            category = "trade" if side == "buy" else "sell"
            filled = result.get("filled_price") or "market"
            send_alert(
                f"{side.upper()} {symbol} {qty} @ ${filled} | Status: {result.get('status')}",
                category,
            )

        return result

    except Exception as e:
        return {
            "order_id": None,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "status": "error",
            "error": str(e),
        }
