# Phase 2: Core Holdings & Portfolio Structure — Design Spec

**Goal**: Add a long-term buy-and-hold portfolio tier alongside the existing day-trading system. Core holdings (NVDA, MSFT, GOOGL, etc.) use dollar-cost averaging on dips, never sell on technical signals, and rebalance quarterly.

**Approach**: Separate strategy engine (Approach A). Core holdings added as a new strategy type with its own capital pool, entry/exit logic, and scheduling. Reuses existing infrastructure (Alpaca API, SQLite, dashboard, strategy engine).

---

## 1. Capital Management

Two independent capital pools in `settings.yaml`:

```yaml
capital: 5000
capital_split:
  trading: 0.50    # $2,500 for active strategies (mean_reversion, trend_pullback, momentum)
  core: 0.50       # $2,500 for core holdings
```

- Trading pool: existing 3 strategies' `capital_pct` now applies to the trading pool, not total capital
- Core pool: feeds the core holdings strategy exclusively
- Risk manager checks the correct pool per trade type
- The split is configurable and can be adjusted as the learning engine reveals what performs better

### Capital Pool Calculation

```python
total_capital = config["capital"]  # 5000
trading_capital = total_capital * config["capital_split"]["trading"]  # 2500
core_capital = total_capital * config["capital_split"]["core"]  # 2500
```

Each trading strategy's capital:
```python
# Before: strategy capital = total_capital * strategy.capital_pct
# After:  strategy capital = trading_capital * strategy.capital_pct
mean_reversion_capital = trading_capital * 0.33  # ~$825
```

---

## 2. Core Holdings Configuration

New `core_holdings` section in `settings.yaml`:

```yaml
core_holdings:
  enabled: true
  max_positions: 15
  buy_list:
    - {symbol: NVDA, sector: tech, weight: 0.10}
    - {symbol: MSFT, sector: tech, weight: 0.10}
    - {symbol: GOOGL, sector: tech, weight: 0.10}
    - {symbol: AAPL, sector: tech, weight: 0.10}
    - {symbol: AMZN, sector: tech, weight: 0.10}
    - {symbol: META, sector: tech, weight: 0.10}
    - {symbol: AMD, sector: semiconductors, weight: 0.10}
    - {symbol: JPM, sector: finance, weight: 0.10}
    - {symbol: JNJ, sector: healthcare, weight: 0.10}
    - {symbol: SPY, sector: etf, weight: 0.10}
  entry:
    mode: dca_on_dip
    sma_period: 50
    dca_interval_days: 7
    max_per_buy: 0.02       # max 2% of core capital per buy ($50 at $2,500 pool)
  exit:
    sell_on_signals: false
    sell_on_removal: true
    sentiment_exit_threshold: -0.3
    sentiment_exit_days: 5
    max_position_pct: 0.20
  rebalance:
    interval_days: 90
    drift_threshold: 0.05
```

### Buy List Management

- `buy_list` is the source of truth for which stocks the system targets
- Weights must sum to 1.0 (validated on load)
- Adding a stock to the list makes it a buy candidate next cycle
- Removing a stock triggers a sell next cycle (if `sell_on_removal: true`)
- Managed via CLI commands (`core-add`, `core-remove`) or direct YAML edit

---

## 3. Core Holdings Engine (`core_engine.py`)

New module: `src/claude_invest/modules/core_engine.py`

### 3a. `run_core_cycle(config, db) -> dict`

Called daily at market open. Steps:

1. Load buy_list from config
2. Get current core holdings from portfolio (positions tagged `strategy_id: "core_holdings"`)
3. Calculate core capital pool: `total_capital * capital_split.core`
4. For each buy_list stock:
   a. If not held: check entry criteria
   b. If held but underweight (< target_weight - drift_threshold): check entry criteria
   c. If held and at/above target: skip
5. Entry criteria check:
   a. **Dip entry**: current price < SMA(50) → buy
   b. **DCA fallback**: last buy for this symbol was > `dca_interval_days` ago → buy regardless of price
   c. Skip if neither condition met
6. For each buy decision:
   a. Calculate position size: `min(target_weight * core_capital - current_value, max_per_buy * core_capital)`
   b. Calculate qty: `position_size / current_price`
   c. Execute buy via `executor.py`
   d. Tag trade: `strategy_id: "core_holdings"`, `position_id: <uuid>`
   e. Log decision with full reasoning

Returns: `{buys: [...], skips: [...], exits: [...], rebalances: [...]}`

### 3b. `check_core_exits(config, db) -> list[dict]`

Called alongside the core cycle. Checks three exit conditions:

1. **Removal exit**: Stock removed from buy_list → sell entire position
2. **Sentiment exit**: Sentiment score < -0.3 for `sentiment_exit_days` consecutive days (check signals table for the last N entries) → sell entire position
3. **Overweight trim**: Position value > `max_position_pct` of core portfolio → sell enough to bring back to target weight

Never sells on RSI, MACD, or any technical signal. The `sell_on_signals: false` config flag is checked and enforced.

### 3c. `rebalance_core(config, db) -> list[dict]`

Called every `rebalance.interval_days` (90 days). Steps:

1. Get current core holdings and their market values
2. Calculate current weight of each: `position_value / total_core_value`
3. Calculate target weight from buy_list config
4. For each stock where `abs(current_weight - target_weight) > drift_threshold`:
   a. If overweight: calculate shares to sell to reach target
   b. If underweight: calculate shares to buy to reach target
5. Execute rebalance trades
6. Log all rebalance decisions with "rebalance" tag

### 3d. `get_core_status(config, db) -> dict`

Read-only status function for CLI and API:

```python
{
    "core_capital": 2500,
    "invested": 1850,
    "cash_remaining": 650,
    "holdings": [
        {
            "symbol": "NVDA",
            "sector": "tech",
            "qty": 0.5,
            "cost_basis": 250.00,
            "current_value": 275.00,
            "unrealized_pnl": 25.00,
            "weight_actual": 0.11,
            "weight_target": 0.10,
            "drift": 0.01,
            "last_buy_date": "2026-04-20",
            "days_since_buy": 7,
        },
        ...
    ],
    "next_rebalance_date": "2026-07-20",
    "days_until_rebalance": 84,
}
```

---

## 4. Database Changes

### 4a. New `core_buys` table

Tracks DCA buy history separately from trading:

```sql
CREATE TABLE IF NOT EXISTS core_buys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    symbol TEXT NOT NULL,
    qty REAL NOT NULL,
    price REAL NOT NULL,
    cost_basis REAL NOT NULL,
    position_id TEXT,
    order_id TEXT
);
```

### 4b. New `rebalance_log` table

```sql
CREATE TABLE IF NOT EXISTS rebalance_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    symbol TEXT NOT NULL,
    action TEXT NOT NULL,       -- "buy" or "sell"
    qty REAL NOT NULL,
    price REAL NOT NULL,
    reason TEXT NOT NULL,       -- "underweight", "overweight", "removal", "sentiment"
    old_weight REAL,
    new_weight REAL
);
```

### 4c. Existing tables

- `trades` table: core holdings trades tagged with `trade_type: "core_holdings"`
- `decisions` table: core decisions tagged with `strategy_id: "core_holdings"` in signals_snapshot
- No changes to signals, portfolio_snapshots, or other tables

---

## 5. Cron Schedule

| Cron | Schedule | Purpose |
|------|----------|---------|
| Trading (existing) | Every 5 min, market hours | Active strategies |
| Core Holdings (new) | Daily 9:35 AM ET, market days only | DCA entries + exit checks |
| Rebalance (new) | Every 90 days, 10:00 AM ET | Quarterly rebalance |
| Weekend Crypto (existing) | Every 2 hrs Sat/Sun | Crypto only |

Core holdings cron prompt:
```
You are the Claude Invest core holdings engine. Run a daily core holdings cycle.
1. Read config for buy_list and core capital
2. Check current core positions
3. For each buy_list stock: check dip entry (price < SMA-50) or DCA schedule (7+ days since last buy)
4. Execute buys within capital limits
5. Check exits: removed stocks, sustained negative sentiment, overweight positions
6. Log every decision
```

The rebalance check runs as part of the daily cycle — on rebalance days (every 90 days), the core cycle also runs `rebalance_core()`.

---

## 6. CLI Commands

| Command | Function | Description |
|---------|----------|-------------|
| `core-status` | `cmd_core_status()` | Show all core holdings with cost basis, weights, drift, P&L |
| `core-buy {symbol}` | `cmd_core_buy(symbol)` | Manual core buy outside schedule |
| `core-add {symbol} {sector} {weight}` | `cmd_core_add(symbol, sector, weight)` | Add to buy_list in config |
| `core-remove {symbol}` | `cmd_core_remove(symbol)` | Remove from buy_list (triggers sell) |
| `core-rebalance` | `cmd_core_rebalance()` | Force quarterly rebalance now |
| `core-cycle` | `cmd_core_cycle()` | Run a full core holdings cycle manually |

Added to `main.py` CLI dispatch alongside existing commands.

---

## 7. API Endpoints

| Endpoint | Method | Response |
|----------|--------|----------|
| `GET /api/core/status` | GET | Core holdings with cost basis, weights, drift, P&L |
| `GET /api/core/schedule` | GET | Upcoming DCA buys (which stocks due, when) |
| `GET /api/core/rebalance-preview` | GET | What rebalance would do if run now |
| `POST /api/core/buy/{symbol}` | POST | Trigger manual core buy |

---

## 8. Dashboard

### New `/core` page with 4 sections:

**Section 1: Portfolio Split**
Two stat cards side by side:
- Trading Pool: $X value, $Y P&L, Z active trades
- Core Pool: $X value, $Y P&L, Z holdings

**Section 2: Holdings Table**
| Symbol | Sector | Cost Basis | Current | P&L | Weight | Target | Drift | Last Buy |
|--------|--------|-----------|---------|-----|--------|--------|-------|----------|

Color coding: green if within target, yellow if drifting, red if >10% drift.

**Section 3: Buy Schedule**
List of buy_list stocks with:
- Days since last buy (green if due, gray if recent)
- Current price vs SMA-50 (green if below = dip opportunity)
- Next scheduled buy date

**Section 4: Rebalance Status**
- Days until next rebalance
- Bar chart showing current vs target weights
- "Preview Rebalance" button that shows what trades would execute

### Navigation
Add `/core` link to nav.tsx: `{ href: "/core", label: "Core Holdings" }`

---

## 9. Risk Manager Updates

The risk manager needs to know which capital pool a trade belongs to:

```python
def check_trade(self, ticker, qty, price, portfolio, strategy_type="trading"):
    if strategy_type == "core_holdings":
        capital = self.core_capital
        max_per_trade = self.config["core_holdings"]["entry"]["max_per_buy"] * capital
    else:
        capital = self.trading_capital
        max_per_trade = capital * self.config["position_size_pct"]
```

- Core holdings bypass the $100/2% per-trade trading limit
- Core holdings use their own `max_per_buy` limit (2% of core capital = $50)
- Daily loss limit (-$150) still applies across BOTH pools combined
- PDT tracking still applies to core holdings buys/sells

---

## 10. Integration with Learning Engine

- Core holdings trades tagged with `strategy_id: "core_holdings"` flow into the learning engine
- Pattern analyzer tracks core holdings as a separate asset_class × strategy bucket
- The optimizer will NOT attempt to adjust core holdings parameters — they're in the off-limits list alongside risk rules
- Daily reports include a "Core Holdings" section with portfolio health
- Strategy brief gets a new section:
  ```
  ## CORE HOLDINGS
  - Invested: $1,850 / $2,500 (74%)
  - Holdings: 8/10 target stocks acquired
  - Next rebalance: 2026-07-20 (84 days)
  - Drift: NVDA +1%, JPM -3% (within threshold)
  ```

---

## 11. Integration with Existing Strategies

The capital split affects existing strategy capital calculations:

**Before:**
```python
strategy_capital = config["capital"] * strategy["capital_pct"]
# mean_reversion: 5000 * 0.33 = $1,650
```

**After:**
```python
trading_capital = config["capital"] * config["capital_split"]["trading"]
strategy_capital = trading_capital * strategy["capital_pct"]
# mean_reversion: 2500 * 0.33 = $825
```

Files that need updating:
- `strategy_engine.py`: `get_strategy_capital()` uses trading pool
- `risk_manager.py`: capital checks use correct pool
- `portfolio_tracker.py`: allocation tracking separates core vs trading
- `market-hours.md` cron prompt: reference trading capital, not total

---

## 12. What This Does NOT Include (Phase 3)

- Crypto core holdings (stocks only for now)
- Dividend tracking and DRIP (dividend reinvestment)
- Fundamental analysis (P/E ratios, earnings dates, revenue growth)
- Options strategies or hedging
- Tax-loss harvesting
- Sector rotation strategies
- International stocks or ADRs

---

## 13. Testing Strategy

- Unit tests for `core_engine.py`: test DCA logic, dip entry, exit conditions, rebalance calculations
- Unit tests for capital split: verify trading strategies get correct reduced capital
- Integration test: full core cycle with mock portfolio data
- Risk manager tests: verify pool isolation (core trade doesn't drain trading capital)
- Config validation: weights sum to 1.0, all required fields present
