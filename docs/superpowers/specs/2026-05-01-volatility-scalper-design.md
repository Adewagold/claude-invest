# Volatility Scalper Strategy — Design Spec

**Date:** 2026-05-01
**Status:** Draft
**Author:** Claude Invest System

---

## Goal

Add a 4th trading strategy that catches high-volatility intraday moves — dip buying oversold crashes, shorting overbought spikes, and news reaction scalping.

This strategy complements the existing three strategies (momentum, mean reversion, core holdings) by targeting short-duration, high-volatility setups that resolve within the same trading day.

---

## 1. Configuration (`settings.yaml`)

Add a new top-level strategy key:

```yaml
volatility_scalper:
  name: "Volatility Scalper"
  enabled: true
  capital_pct: 0.25
  modes:
    dip_buying: true
    rally_shorting: false
    news_reaction: true
  watchlist: [OKLO, RIVN, PLTR, IONQ, MARA]
  discovery:
    enabled: true
    min_atr_pct: 0.04
    lookback_days: 20
  params:
    bar_timeframe: "15Min"
    dip_threshold: -0.05
    rally_threshold: 0.05
    rsi_period: 14
    rsi_oversold: 30
    rsi_overbought: 75
    news_sentiment_buy: -0.3
    news_sentiment_short: 0.4
    news_min_articles: 3
    take_profit_pct: 0.03
    stop_loss_pct: 0.03
    max_hold_minutes: 120
    force_exit_time: "15:55"
    max_concurrent: 2
```

### Capital Allocation Impact

With 4 strategies at equal weight, each strategy drops from 0.33 to 0.25:

| Strategy           | Old `capital_pct` | New `capital_pct` | Dollar Amount (pool $2,500) |
|--------------------|-------------------|-------------------|-----------------------------|
| Momentum           | 0.33              | 0.25              | $625                        |
| Mean Reversion     | 0.33              | 0.25              | $625                        |
| Core Holdings      | 0.33              | 0.25              | $625                        |
| Volatility Scalper | —                 | 0.25              | $625                        |

Update the other three strategies' `capital_pct` values in `settings.yaml` when enabling this strategy.

---

## 2. Volatility Scanner (`volatility_scanner.py`)

**Location:** `engine/volatility_scanner.py`

### Public API

```python
def scan_volatile_stocks(config: dict) -> list[dict]:
    """
    Returns ranked list of volatile stock candidates.

    Each dict contains:
      - ticker: str
      - atr_pct: float        # ATR as % of price
      - intraday_change: float # % change from open
      - volume_ratio: float    # today's volume / 20-day avg
      - source: str           # "curated" or "discovered"
      - rank: int
    """
```

### Logic

1. **Load curated watchlist** — always include tickers from `settings.yaml volatility_scalper.watchlist`
2. **Auto-discover** — if `discovery.enabled`, scan a broader universe for stocks with ATR% >= `min_atr_pct` over the last `lookback_days` trading days
3. **Rank candidates** — sort by composite score: `(atr_pct * 0.5) + (abs(intraday_change) * 0.3) + (volume_ratio * 0.2)`
4. **Priority** — curated stocks always appear first in the ranked list, regardless of score

### Data Sources

- ATR calculation: Alpaca historical bars (daily timeframe, `lookback_days` window)
- Intraday change: Alpaca latest trade vs. previous close
- Volume ratio: today's volume vs. 20-day average daily volume

---

## 3. Scalp Engine (`scalp_engine.py`)

**Location:** `engine/scalp_engine.py`

### Public API

```python
def run_scalp_cycle(config: dict, db) -> dict:
    """
    Runs one full scalp cycle: scan candidates, evaluate setups, place trades.

    Returns summary dict:
      - scanned: int
      - signals_found: int
      - trades_placed: int
      - skipped_reason: list[str]
    """

def check_scalp_exits(config: dict, db) -> list[dict]:
    """
    Checks all open scalp positions for exit conditions.

    Returns list of closed positions, each dict:
      - ticker: str
      - exit_reason: str  # "take_profit" | "stop_loss" | "max_hold" | "force_exit"
      - pnl_pct: float
    """
```

### Trading Modes

#### Mode 1: Dip Buying (`dip_buying: true`)

**Entry conditions (all must be true):**
- Intraday price change <= `dip_threshold` (-5%)
- RSI on 15-min bars < `rsi_oversold` (30)
- Not already holding a position in this ticker
- Open scalp positions < `max_concurrent` (2)

**Signal:** Buy at market on the next 15-min bar open.

#### Mode 2: Rally Shorting (`rally_shorting: false` by default)

**Entry conditions (all must be true):**
- Intraday price change >= `rally_threshold` (+5%)
- RSI on 15-min bars > `rsi_overbought` (75)
- Not already holding a short position in this ticker
- Open scalp positions < `max_concurrent` (2)

**Signal:** Short at market on the next 15-min bar open.

**Note:** Disabled by default. Requires margin account and explicit opt-in.

#### Mode 3: News Reaction (`news_reaction: true`)

**Entry conditions (all must be true):**
- News sentiment score <= `news_sentiment_buy` (-0.3) — strong negative overreaction
- At least `news_min_articles` (3) news articles in the last 2 hours
- Price has already dropped (confirms market overreaction, not ongoing decline)
- RSI on 15-min bars < `rsi_oversold` (30)
- Open scalp positions < `max_concurrent` (2)

**Signal:** Buy at market — betting on sentiment reversal / snap-back.

**Short side** (when `rally_shorting` also enabled): sentiment >= `news_sentiment_short` (+0.4) with RSI > `rsi_overbought`.

### Exit Logic (`check_scalp_exits`)

Evaluated in priority order on each cycle:

| Exit Condition | Trigger | Action |
|----------------|---------|--------|
| Force exit | Current time >= `force_exit_time` (15:55) | Market sell/cover all scalp positions |
| Take profit | P&L >= `take_profit_pct` (+3%) | Market close position |
| Stop loss | P&L <= `-stop_loss_pct` (-3%) | Market close position |
| Max hold | Position age >= `max_hold_minutes` (120 min) | Market close position |

Force exit takes absolute priority — no scalp position is held overnight.

### Concurrency Guard

Before placing any new scalp trade, count open positions tagged `strategy_id: "volatility_scalper"`. If count >= `max_concurrent`, skip all new entries until a position closes.

---

## 4. `technicals.py` Update

**File:** `engine/technicals.py`

### Change

Add optional `timeframe` parameter to `analyze_technicals`:

```python
# Before
def analyze_technicals(ticker: str) -> dict:

# After
def analyze_technicals(ticker: str, timeframe: str = "1Hour") -> dict:
```

### Behavior

- Default `"1Hour"` — preserves existing behavior for all callers
- When `timeframe="15Min"` — fetches 15-minute bars from Alpaca instead of hourly
- RSI, MACD, and moving averages all computed on the requested bar timeframe
- Alpaca bar endpoint already supports `"15Min"` as a valid timeframe string

### Callers to Update

- `scalp_engine.py` — passes `timeframe="15Min"` explicitly
- All other strategy engines — no change needed (default preserved)

---

## 5. CLI Commands

Add to the existing CLI entry point (likely `cli.py` or `commands/`):

| Command | Description |
|---------|-------------|
| `scalp-cycle` | Run one full scalp cycle (scan + evaluate + trade) |
| `scalp-scan` | Show current volatile candidates without trading |
| `scalp-status` | Show all open scalp positions with P&L |

### Example Output — `scalp-scan`

```
Volatile Candidates (2026-05-01 10:32 ET)
==========================================
 1. MARA   ATR: 7.2%  Change: -6.1%  Vol/Avg: 2.4x  [curated]
 2. IONQ   ATR: 5.8%  Change: +5.3%  Vol/Avg: 1.9x  [curated]
 3. RIVN   ATR: 4.9%  Change: -3.2%  Vol/Avg: 1.3x  [curated]
 4. SOUN   ATR: 4.3%  Change: -2.8%  Vol/Avg: 3.1x  [discovered]
```

### Example Output — `scalp-status`

```
Open Scalp Positions (2026-05-01 11:15 ET)
===========================================
 MARA  BUY  100 shares  Entry: $18.42  Current: $18.89  P&L: +2.5%  Age: 43min
 IONQ  BUY   80 shares  Entry: $11.20  Current: $11.08  P&L: -1.1%  Age: 12min
```

---

## 6. API Endpoints

Add to the Next.js API routes:

### `GET /api/scalp/status`

Returns open scalp positions.

**Response:**
```json
{
  "positions": [
    {
      "ticker": "MARA",
      "side": "long",
      "shares": 100,
      "entry_price": 18.42,
      "current_price": 18.89,
      "pnl_pct": 0.025,
      "age_minutes": 43,
      "entry_mode": "dip_buying"
    }
  ],
  "count": 1,
  "max_concurrent": 2
}
```

### `GET /api/scalp/candidates`

Returns current volatile stock candidates from the scanner.

**Response:**
```json
{
  "candidates": [
    {
      "ticker": "MARA",
      "atr_pct": 0.072,
      "intraday_change": -0.061,
      "volume_ratio": 2.4,
      "source": "curated",
      "rank": 1
    }
  ],
  "scanned_at": "2026-05-01T10:32:00-04:00"
}
```

---

## 7. Dashboard

**Location:** Add a new section to the existing `/strategies` page — do not create a new page.

### New Section: "Volatility Scalper"

Layout (within the Strategies page):

```
[ Volatility Scalper ]
-----------------------
Active Scalp Positions   |  Today's Scalp Trades
  MARA  +2.5%  43min    |   IONQ  closed  +3.1%  (take profit)
  IONQ  -1.1%  12min    |   RIVN  closed  -2.8%  (stop loss)

Volatile Candidates
  1. MARA   7.2% ATR   -6.1% today   2.4x vol
  2. IONQ   5.8% ATR   +5.3% today   1.9x vol
```

Data fetched from:
- `/api/scalp/status` — active positions
- `/api/scalp/candidates` — scanner output
- `/api/trades?strategy=volatility_scalper&date=today` — today's closed scalp trades

---

## 8. Integration

### Learning Engine

Tag all scalp trades with `strategy_id: "volatility_scalper"`. The learning engine tracks strategy performance by ID — no changes needed to the learning engine itself. Performance metrics (win rate, avg P&L, avg hold time) will appear automatically in the strategies dashboard.

### Risk Manager

Scalp positions use the **trading pool** (not the core holdings pool). The risk manager's existing per-trade and daily-loss limits apply. No special risk rules needed — the hard `max_concurrent: 2` cap and the 3% stop loss provide bounded downside.

### Cron Integration

**No new cron job.** The volatility scalper runs inside the existing market hours cron:

1. `run_scalp_cycle` called once per cycle (alongside other strategy cycles)
2. `check_scalp_exits` called at the start of each cycle (before new entries) to process exits first

The existing `force_exit_time: "15:55"` ensures all scalp positions are closed before market close without needing a dedicated cron.

### Capital Allocation

- Trading pool: $2,500 total
- Volatility scalper allocation: $2,500 * 0.25 = **$625**
- Update the other three strategies from `capital_pct: 0.33` to `capital_pct: 0.25` in `settings.yaml`

---

## 9. Not Included (Explicit Scope Exclusions)

The following are out of scope for this implementation:

- **Options/puts** — equity positions only
- **Pre-market / after-hours scalping** — regular market hours only (force exit at 15:55)
- **Auto position sizing by volatility** — fixed capital allocation per strategy
- **Multi-leg strategies** — single-leg long/short only
- **Fractional shares** — whole share positions only

These may be considered in future iterations.

---

## 10. Testing

### Unit Tests

**`tests/test_volatility_scanner.py`**
- Test `scan_volatile_stocks` returns ranked list
- Test curated tickers always appear first
- Test `min_atr_pct` filter excludes low-volatility stocks
- Test with discovery disabled — only curated tickers returned

**`tests/test_scalp_engine.py`**
- Test `run_scalp_cycle` with mock data for each mode (dip, short, news)
- Test `max_concurrent` guard blocks new entries when at limit
- Test `check_scalp_exits` triggers take_profit at +3%
- Test `check_scalp_exits` triggers stop_loss at -3%
- Test `check_scalp_exits` triggers max_hold after 120 minutes
- Test force exit closes all positions when time >= 15:55
- Test disabled modes (e.g., `rally_shorting: false`) produce no short signals

### Integration Test

**`tests/test_scalp_integration.py`**
- Full cycle: `scan_volatile_stocks` -> `run_scalp_cycle` -> `check_scalp_exits` with mock Alpaca responses
- Verify trade is recorded in DB with correct `strategy_id`
- Verify learning engine can query by `strategy_id: "volatility_scalper"`

### `technicals.py` Test Update

- Add test case: `analyze_technicals("MARA", timeframe="15Min")` returns valid RSI
- Verify default `timeframe="1Hour"` behavior unchanged for existing tests

---

## Implementation Order

1. Update `settings.yaml` — add `volatility_scalper` block, update other strategies to `0.25`
2. Update `technicals.py` — add `timeframe` parameter
3. Build `volatility_scanner.py`
4. Build `scalp_engine.py`
5. Add CLI commands
6. Add API endpoints
7. Update Strategies dashboard
8. Write tests
