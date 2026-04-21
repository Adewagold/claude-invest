from datetime import datetime, timezone


CRYPTO_SYMBOLS = {"BTC", "ETH", "SOL", "DOGE", "SHIB", "PEPE", "BONK", "WIF",
                  "TRUMP", "LINK", "ADA", "AVAX", "DOT", "XRP", "LTC"}

SECTOR_KEYWORDS = {
    "healthcare": ["PFE", "JNJ", "UNH", "MRNA", "ABT", "LLY", "BMY"],
    "technology": ["AAPL", "MSFT", "NVDA", "SNDK", "INTC", "AMD", "GOOG", "META", "AMZN"],
    "energy": ["XOM", "CVX", "XLE", "OIL", "SCO", "USO"],
    "reits": ["O", "AMT", "SPG", "VNQ", "VICI"],
    "financial": ["JPM", "BAC", "GS", "V", "MA"],
}


def classify_sector(symbol: str, config: dict) -> str:
    overrides = config.get("portfolio", {}).get("sectors", {}).get("overrides", {})
    if symbol in overrides:
        return overrides[symbol]
    base = symbol.replace("/USD", "").replace("USD", "")
    # Also check base symbol against overrides (e.g. "TRUMPUSD" -> "TRUMP" -> matches "TRUMP/USD" override)
    for override_key, override_val in overrides.items():
        override_base = override_key.replace("/USD", "").replace("USD", "")
        if base == override_base:
            return override_val
    if base in CRYPTO_SYMBOLS:
        return "crypto"
    for sector, tickers in SECTOR_KEYWORDS.items():
        if base in tickers or symbol in tickers:
            return sector
    return "general"


def assign_risk_tier(sector: str, config: dict) -> str:
    risk_tiers = config.get("risk_tiers", {})
    for tier, sectors in risk_tiers.items():
        if sector in sectors:
            return tier
    return "neutral"


def get_allocation(config: dict, positions: list[dict]) -> dict:
    allocation_targets = config.get("portfolio", {}).get("allocation", {})
    drift_threshold = config.get("portfolio", {}).get("drift_threshold", 0.10)
    total_value = sum(p["market_value"] for p in positions)

    classified = []
    for p in positions:
        sector = classify_sector(p["symbol"], config)
        tier = assign_risk_tier(sector, config)
        classified.append({**p, "sector": sector, "tier": tier})

    tier_values = {"safe": 0.0, "neutral": 0.0, "risk": 0.0}
    for p in classified:
        tier_values[p["tier"]] = tier_values.get(p["tier"], 0) + p["market_value"]

    tiers = {}
    for tier_name in ["safe", "neutral", "risk"]:
        target = allocation_targets.get(tier_name, 0.33)
        actual = tier_values[tier_name] / total_value if total_value > 0 else 0
        drift = actual - target
        tiers[tier_name] = {
            "target": target,
            "actual": round(actual, 4),
            "drift": round(drift, 4),
            "value": round(tier_values[tier_name], 2),
            "alert": abs(drift) > drift_threshold,
        }

    sectors = {}
    for p in classified:
        if p["sector"] not in sectors:
            sectors[p["sector"]] = {"value": 0.0, "positions": []}
        sectors[p["sector"]]["value"] += p["market_value"]
        sectors[p["sector"]]["positions"].append(p["symbol"])
    for s in sectors.values():
        s["pct"] = round(s["value"] / total_value, 4) if total_value > 0 else 0
        s["value"] = round(s["value"], 2)

    time_horizon = {"short_term": [], "long_term": []}
    for p in classified:
        time_horizon["short_term"].append(p["symbol"])

    return {
        "total_value": round(total_value, 2),
        "tiers": tiers,
        "sectors": sectors,
        "positions": classified,
        "time_horizon": time_horizon,
    }
