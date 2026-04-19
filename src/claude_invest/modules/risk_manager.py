from claude_invest.modules.db import Database


class RiskManager:
    def __init__(self, config: dict, db: Database):
        self.config = config
        self.db = db
        self.capital = config["capital"]
        self.max_positions = config["max_positions"]
        self.max_per_ticker = config["max_per_ticker"]
        self.position_size_pct = config["position_size_pct"]
        self.daily_loss_limit = config["daily_loss_limit"]
        self.pdt_tracking = config["pdt_tracking"]

    def calculate_position_size(self, price: float) -> int:
        target_dollars = self.capital * self.position_size_pct
        max_dollars = self.capital * self.max_per_ticker
        dollars = min(target_dollars, max_dollars)
        return int(dollars / price)

    def check_trade(self, symbol: str, qty: int, price: float, portfolio: dict) -> dict:
        # Check daily loss limit
        if portfolio["daily_pnl"] <= self.daily_loss_limit:
            return {"approved": False, "reason": "Daily loss limit reached"}

        # Check max positions
        if portfolio["position_count"] >= self.max_positions:
            return {"approved": False, "reason": "Max positions reached"}

        # Check per-ticker exposure
        existing_exposure = sum(
            p["market_value"]
            for p in portfolio["positions"]
            if p["symbol"] == symbol
        )
        new_exposure = existing_exposure + (qty * price)
        max_exposure = self.capital * self.max_per_ticker

        if new_exposure > max_exposure:
            return {
                "approved": False,
                "reason": f"Ticker exposure would be ${new_exposure:.0f}, max is ${max_exposure:.0f}",
            }

        return {"approved": True, "reason": "Trade within risk limits"}

    def check_pdt_allowed(self) -> bool:
        if not self.pdt_tracking:
            return True
        count = self.db.get_day_trade_count(days=5)
        return count < 3
