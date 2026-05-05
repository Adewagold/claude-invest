# Trade Graduation & Core Guardian Design

## Overview

Two connected systems that bridge trading and long-term holding:

1. **Graduation Gate** — When a trading position hits RSI > 80, check if it should graduate to core holdings instead of being sold
2. **Core Guardian** — Intelligent exit logic for core holdings that protects against sustained losses without panic selling

## Architecture: Two New Modules (Approach B)

- `graduation.py` — Graduation gate logic, called from trading cron
- `core_guardian.py` — Smart exit for core holdings, called from core-cycle

## Module 1: Graduation Gate (`graduation.py`)

### Trigger

Called during trading cycle when RSI > 80 on a trading position, before executing a sell.

### Graduation Criteria (ALL must pass)

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| Hold duration | >= 5 days | Proves it's not a pump-and-dump spike |
| Profit | >= 10% unrealized gain | Proven winner with real momentum |
| Sentiment | Score > 0.15, articles >= 3 | Sustained narrative, not one headline |
| Trend | Price above 20-day SMA | Not crashing after a spike |

### If All Pass: Graduate

1. Add symbol to `core_holdings.buy_list` in settings.yaml at probationary weight (3.5%)
2. Do NOT sell — position stays open, reclassified from trading to core
3. Record in `graduations` DB table
4. Log decision with action `"graduated"`
5. Rebalance existing weights to accommodate new entry (proportional reduction)

### If Any Fail: Normal Sell

Proceed with the standard RSI > 80 sell as today.

### Probation Period

- Graduated stocks start at **half weight** (3.5% vs normal 7.1%)
- After 30 days without hitting -15% from graduation price → promote to full weight
- If -15% hit during probation → demote (remove from buy_list, position returns to trading pool)

### Public Interface

```python
def check_graduation(symbol: str, config: dict, db: Database, portfolio: dict) -> dict:
    """Check if a trading position should graduate to core holdings.
    
    Returns:
        {"decision": "graduate"|"sell", "reason": str, "criteria": dict}
    """
```

### CLI Command

```bash
python3 -m claude_invest.main check-graduation SYMBOL
```

Returns JSON: `{"decision": "graduate"|"sell", "reason": "...", "criteria": {...}}`

## Module 2: Core Guardian (`core_guardian.py`)

### Trigger

Called during core-cycle (daily at 9:35 AM), after DCA buys complete.

### Peak Tracking

- Maintains `core_peaks` DB table with all-time high price per symbol
- Updated every cycle: if current_price > stored peak, update peak
- Drawdown calculated as: `(current_price - peak_price) / peak_price`

### Exit Tiers (Sustained Drawdown)

| Drawdown from Peak | Sustained For | Action |
|--------------------|---------------|--------|
| -15% | 5+ days | **Warning**: Log alert. If sentiment < -0.2 for 5 days → trim 25% |
| -25% | 10+ days | **Reduce**: Sell 50% of position regardless of sentiment |
| -35% | any duration | **Full exit**: Sell entire position, remove from buy_list |

### Market Crash Override

- Track SPY's drawdown from its own peak in `core_peaks`
- If SPY is down > 10% from peak → **suspend all individual exits**
- Log: `"crash_override: holding through market-wide drawdown"`
- Resume normal exit logic when SPY recovers above -10%

### Graduated Stock Probation Rules

- Stocks in probation (first 30 days) use tighter thresholds:
  - Warning: -10% (vs -15%)
  - Reduce: -17% (vs -25%)
  - Exit: -23% (vs -35%)
- Factor: `probation_tighter_factor: 0.67`
- If probationary stock hits its warning threshold → demote back to trading pool

### What Core Guardian Does NOT Do

- Never sells on RSI/MACD technical signals (existing rule preserved)
- Never sells based on a single bad day (requires sustained duration)
- Never overrides the market crash protection
- Never touches stocks during a market-wide correction (SPY > -10%)

### Public Interface

```python
def check_core_health(config: dict, db: Database, portfolio: dict) -> dict:
    """Run smart exit checks for all core holdings.
    
    Returns:
        {"warnings": [...], "trims": [...], "exits": [...], "crash_override": bool}
    """

def update_peaks(db: Database, portfolio: dict, core_symbols: set) -> None:
    """Update peak prices for all core holdings."""

def check_probation_promotions(config: dict, db: Database) -> list[dict]:
    """Check if any probationary stocks should be promoted to full weight."""
```

### CLI Command

```bash
python3 -m claude_invest.main core-health
```

Returns JSON summary of all holdings' drawdown status and any actions taken.

## Database Changes

### New Table: `graduations`

```sql
CREATE TABLE IF NOT EXISTS graduations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    symbol TEXT NOT NULL,
    entry_price REAL NOT NULL,
    graduation_price REAL NOT NULL,
    hold_days INTEGER NOT NULL,
    gain_pct REAL NOT NULL,
    sentiment_score REAL,
    status TEXT DEFAULT 'probation',
    promoted_at TEXT,
    demoted_at TEXT
);
```

### New Table: `core_peaks`

```sql
CREATE TABLE IF NOT EXISTS core_peaks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL UNIQUE,
    peak_price REAL NOT NULL,
    peak_date TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

## Configuration (settings.yaml additions)

```yaml
graduation:
  min_hold_days: 5
  min_gain_pct: 0.10
  min_sentiment: 0.15
  min_articles: 3
  probation_days: 30
  probation_weight: 0.035

core_guardian:
  warning_drawdown: -0.15
  reduce_drawdown: -0.25
  exit_drawdown: -0.35
  warning_days: 5
  reduce_days: 10
  crash_override_threshold: -0.10
  probation_tighter_factor: 0.67
```

## Integration Points

### Trading Cron Prompt

Add between position analysis and sell execution:

```
When RSI > 80 for a trading position:
1. Run: python3 -m claude_invest.main check-graduation SYMBOL
2. If "graduate" → log graduation, do NOT sell
3. If "sell" → proceed with normal sell
```

### Core-Cycle

In `run_core_cycle()`, after DCA buys:

```python
from claude_invest.modules.core_guardian import check_core_health, update_peaks, check_probation_promotions

# Update peak prices
update_peaks(db, portfolio, core_symbols)

# Check drawdown exits
health = check_core_health(config, db, portfolio)

# Check probation promotions (every cycle)
promotions = check_probation_promotions(config, db)
```

### API Endpoints

- `GET /api/graduations` — list all graduated stocks with status
- `GET /api/core/health` — current drawdown status for all core holdings

### Dashboard

Add "Graduations" section to core holdings page:
- Table of graduated stocks (symbol, date, gain at graduation, status)
- Drawdown indicator per core holding (green/yellow/red)

## Data Flow

```
Trading Cron fires → RSI > 80 detected
    → check_graduation(SYMBOL)
        → Check hold_days >= 5? ✓
        → Check gain >= 10%? ✓
        → Check sentiment > 0.15 w/ 3+ articles? ✓
        → Check price > SMA20? ✓
        → ALL PASS → Graduate
            → Update settings.yaml buy_list (add at 3.5% weight)
            → Insert into graduations table (status=probation)
            → Log decision (action=graduated)
            → Return {"decision": "graduate"}
    
Core-Cycle fires daily
    → update_peaks() for all core symbols
    → check_core_health()
        → For each core holding:
            → Calculate drawdown from peak
            → If drawdown > threshold for sustained days → action
            → If SPY > -10% → crash override, skip exits
    → check_probation_promotions()
        → If 30 days passed without -15% hit → promote to full weight
```

## Testing Strategy

- Unit tests for graduation criteria logic (mock technicals + sentiment)
- Unit tests for core_guardian drawdown tiers (mock peak data + price series)
- Unit test for market crash override (mock SPY drawdown)
- Unit test for probation promotion/demotion
- Integration test: full graduation flow (mock API, verify settings.yaml updated)
