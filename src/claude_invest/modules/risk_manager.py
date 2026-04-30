from claude_invest.modules.db import Database


class RiskManager:
    def __init__(self, config: dict, db: Database):
        self.config = config
        self.db = db
        self.total_capital = config["capital"]
        capital_split = config.get("capital_split")
        if capital_split:
            self.trading_capital = self.total_capital * capital_split.get("trading", 1.0)
            self.core_capital = self.total_capital * capital_split.get("core", 0.0)
        else:
            self.trading_capital = self.total_capital
            self.core_capital = 0
        self.max_positions = config["max_positions"]
        self.max_per_ticker = config["max_per_ticker"]
        self.position_size_pct = config["position_size_pct"]
        self.daily_loss_limit = config["daily_loss_limit"]
        self.pdt_tracking = config["pdt_tracking"]

    def calculate_position_size(self, price: float) -> int:
        target_dollars = self.trading_capital * self.position_size_pct
        max_dollars = self.trading_capital * self.max_per_ticker
        dollars = min(target_dollars, max_dollars)
        return int(dollars / price)

    def calculate_core_position_size(self, price: float, config: dict) -> float:
        core_config = config.get("core_holdings", {})
        max_per_buy = core_config.get("entry", {}).get("max_per_buy", 0.02)
        dollars = self.core_capital * max_per_buy
        return round(dollars / price, 6) if price > 0 else 0

    def check_trade(self, symbol: str, qty, price: float, portfolio: dict, strategy_type: str = "trading") -> dict:
        # Daily loss limit applies to both pools
        if portfolio["daily_pnl"] <= self.daily_loss_limit:
            return {"approved": False, "reason": "Daily loss limit reached"}

        if portfolio["position_count"] >= self.max_positions:
            return {"approved": False, "reason": "Max positions reached"}

        if strategy_type == "core_holdings":
            return self._check_core_trade(symbol, qty, price, portfolio)
        return self._check_trading_trade(symbol, qty, price, portfolio)

    def _check_trading_trade(self, symbol: str, qty, price: float, portfolio: dict) -> dict:
        existing_exposure = sum(
            p["market_value"] for p in portfolio["positions"] if p["symbol"] == symbol
        )
        new_exposure = existing_exposure + (qty * price)
        max_exposure = self.trading_capital * self.max_per_ticker
        if new_exposure > max_exposure:
            return {"approved": False, "reason": f"Ticker exposure would be ${new_exposure:.0f}, max is ${max_exposure:.0f}"}
        return {"approved": True, "reason": "Trade within risk limits"}

    def _check_core_trade(self, symbol: str, qty, price: float, portfolio: dict) -> dict:
        core_config = self.config.get("core_holdings", {})
        max_per_buy = core_config.get("entry", {}).get("max_per_buy", 0.02)
        trade_value = qty * price
        max_trade = self.core_capital * max_per_buy
        if trade_value > max_trade * 1.1:  # 10% buffer for price movement
            return {"approved": False, "reason": f"Core trade ${trade_value:.0f} exceeds max ${max_trade:.0f}"}
        return {"approved": True, "reason": "Core trade within limits"}

    def check_pdt_allowed(self) -> bool:
        if not self.pdt_tracking:
            return True
        count = self.db.get_day_trade_count(days=5)
        return count < 3
