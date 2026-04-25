# Phase 1: Learning Engine — Design Spec

**Goal**: Build a closed-loop learning system that analyzes completed trades across 5 dimensions, discovers actionable patterns, auto-tunes strategy parameters with guardrails, and generates daily reports for both the AI trading engine and the human operator.

**Approach**: Evolutionary enhancement of existing `learner.py` → `strategy.py` pipeline. New modules plug into the existing flow without rewriting working code.

**Forward-looking**: Data structures and APIs designed so Phase 2 (historical prediction) and Phase 3 (long-term portfolio) can plug in without rewrites.

---

## 1. Database Enhancements

### 1a. Add `position_id` to existing tables

Add a `position_id` TEXT column to the `decisions` and `trades` tables. This UUID links the full lifecycle of a position:

```
BUY decision (position_id: abc123)
  → trade execution (position_id: abc123)
  → HOLD decisions (position_id: abc123)
  → SELL decision (position_id: abc123)
  → trade execution (position_id: abc123)
```

- Generated as a UUID at entry time (when a BUY decision is made)
- Passed through to `executor.py` and stored on the trade record
- SELL decisions and trades reference the same `position_id`
- Replaces FIFO ticker+timestamp matching in `learner.py`
- Column is nullable for backward compatibility with existing records

Migration: `ALTER TABLE decisions ADD COLUMN position_id TEXT;` and same for `trades`.

### 1b. New `change_log` table

Tracks every parameter change the optimizer makes:

```sql
CREATE TABLE change_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    parameter_path TEXT NOT NULL,
    old_value TEXT NOT NULL,
    new_value TEXT NOT NULL,
    reason TEXT NOT NULL,
    trade_count INTEGER NOT NULL,
    auto_applied BOOLEAN NOT NULL,
    reverted BOOLEAN DEFAULT FALSE,
    reverted_at TEXT,
    revert_reason TEXT
);
```

- `parameter_path`: dot-notation path in settings.yaml (e.g., `strategies.mean_reversion.params.rsi_buy_threshold`)
- `auto_applied`: true if 10+ trades, false if 5-9 (proposed only)
- `reverted`: set to true if the change failed its evaluation window or was manually reverted
- No other schema changes needed — `signals_snapshot` JSON handles new dimensions

---

## 2. Pattern Analyzer (`pattern_analyzer.py`)

New module. Takes completed trade pairs (entry + exit linked by `position_id`) and analyzes them across 5 dimensions.

### Input

List of matched trades from the database. Each matched trade contains:
- `position_id`, `ticker`, `strategy_id`
- Entry: timestamp, price, signals_snapshot (RSI, MACD, sentiment, trend)
- Exit: timestamp, price, signals_snapshot
- Computed: `pnl`, `pnl_pct`, `hold_duration_minutes`, `win` (boolean)

### Output: `LearningReport`

```python
{
  "generated_at": "2026-04-25T16:00:00",
  "total_trades": 8,
  "overall_win_rate": 0.625,
  "signal_combos": [...],
  "time_of_day": [...],
  "hold_duration": [...],
  "market_regime": [...],
  "asset_class": [...],
  "cross_dimensional": [...]
}
```

### Dimension Bucketing

| Dimension | Buckets | Source |
|-----------|---------|--------|
| Signal combos | Dynamic from signals_snapshot (e.g., "macd_above_signal + rsi_30_50 + trend_bearish") | Entry signals_snapshot JSON |
| Time-of-day | `pre_market` (9:00-9:29), `market_open` (9:30-10:30), `midday` (10:30-15:00), `market_close` (15:00-16:00), `after_hours` (16:00-20:00), `crypto_overnight` (20:00-9:00) | Entry timestamp converted to ET |
| Hold duration | `scalp` (<15m), `intraday` (<1h), `swing_short` (1h-1d), `swing_long` (1d-5d), `position` (>5d) | Exit timestamp - entry timestamp |
| Market regime | `high_volatility` (ATR > 1.5x 20-day avg), `low_volatility` (ATR < 0.75x 20-day avg), `normal` | Computed from daily bars via Alpaca Historical Data API at entry time. ATR(14) compared to 20-day rolling average of ATR(14). |
| Asset class | `stock` or `crypto` (detected by "/" in ticker), crossed with `strategy_id` | Ticker format + strategy tag |

### Cross-Dimensional Analysis

After individual dimension slicing, look for patterns that emerge from combining two dimensions. Only surface combos with 3+ trades. Example: "mean_reversion + market_open + high_vol: 3W/0L".

Limit to 2-dimension crosses (not 3+) to avoid overfitting with small sample sizes.

### Confidence Levels

- `insufficient`: < 5 trades
- `low`: 5-9 trades (enough to propose, not to auto-apply)
- `high`: 10+ trades (enough to auto-apply)

---

## 3. Parameter Optimizer (`optimizer.py`)

New module. Takes the `LearningReport` and decides what to change in `settings.yaml`.

### Optimizable Parameters

| Parameter | Bounds | Strategy |
|-----------|--------|----------|
| `rsi_buy_threshold` | 10-40 | Mean Reversion |
| `rsi_sell_threshold` | 55-85 | Mean Reversion |
| `max_hold_bars` | 3-10 | Mean Reversion |
| `stop_loss_pct` | 0.005-0.05 | All strategies |
| `take_profit_pct` | 0.01-0.10 | All strategies |
| MACD `fast` period | 3-12 | Trend Pullback |
| MACD `slow` period | 20-50 | Trend Pullback |

### Off-Limits (hardcoded exclusions)

- Risk rules: max per trade, max per ticker, position limits, daily loss limit
- Capital allocation percentages between strategies
- Strategy enabled/disabled status
- Any parameter not listed in the optimizable table above

### Decision Logic

1. Group completed trades by strategy
2. For each optimizable parameter, compare outcomes at different value ranges
3. If a different range shows better win rate AND better avg P&L:
   - **5-9 trades**: Add to `proposed_changes` in daily report, log to `change_log` with `auto_applied=false`
   - **10+ trades**: Auto-apply to `settings.yaml`, log to `change_log` with `auto_applied=true`, flag in daily report

### Guardrails

| Guardrail | Value | Rationale |
|-----------|-------|-----------|
| Max changes per strategy per day | 1 | Isolate variables — can't tell what helped if you change 2 things |
| Min trades to propose | 5 | Early signal, shown as suggestion |
| Min trades to auto-apply | 10 | Real confidence before touching config |
| Evaluation window | 10 trades | Same bar to keep as to apply |
| Auto-revert if win rate drops | Yes | Safety net for bad changes |
| Max reverts before locking | 2 | Stop flip-flopping — mark as "contested" |
| Max active unevaluated changes | 3 total | Prevent drifting too far from baseline |
| Parameter bounds | Per-parameter (see table) | Prevent nonsensical values |

### Evaluation Window

After a parameter change is applied:
- Track the next 10 trades for that strategy
- Compare win rate of those 10 trades vs the win rate that justified the change
- If win rate drops by more than 15 percentage points → auto-revert
- If a parameter is reverted twice → lock it and flag as "contested" in daily report
- Contested parameters require manual unlock via `revert-change` command

### Config Update Mechanism

The optimizer reads `settings.yaml`, modifies the specific parameter value, and writes back. The project uses PyYAML which does not preserve comments on round-trip. To handle this: add `ruamel.yaml` as a dependency for comment-preserving round-trip YAML editing. If `settings.yaml` has no comments worth preserving, standard PyYAML load/dump is acceptable. Every change is logged to the `change_log` table before writing.

---

## 4. Enhanced Strategy Brief (`strategy-brief.md`)

Same file path, richer content. Auto-generated by the enhanced `strategy.py`.

### Format

```markdown
# Strategy Brief
*Updated: YYYY-MM-DD (auto-generated)*

## RULES — ALWAYS (10+ trades, 75%+ win rate)
- PREFER [pattern]: [W]W/[L]L ([rate]%)

## RULES — NEVER (10+ trades, <25% win rate)
- AVOID [pattern]: [W]W/[L]L ([rate]%)

## OBSERVATIONS (5-9 trades, needs more data)
- [pattern]: [W]W/[L]L ([rate]%) — [context]

## PARAMETER CHANGES ACTIVE
- [strategy].[param]: [old] → [new] (applied [date], eval: [n]/10 trades)
- [strategy].[param]: [old] → [new] (proposed, needs [n] more trades)

## CONTESTED PARAMETERS (locked, needs manual review)
- [strategy].[param]: reverted twice, locked at [value]

## DIMENSION INSIGHTS
- Best time window: [window] ([rate]% win rate)
- Best hold duration: [bucket] ([rate]% win rate)
- High volatility favors: [strategy]
- Asset class note: [insight]

## ALLOCATION ALERTS
- [TIER]: [actual]% actual vs [target]% target ([status])

## OVERALL: [W]W/[L]L ([rate]% win rate)
```

### Generation Rules

- RULES — ALWAYS: patterns with 10+ trades AND 75%+ win rate
- RULES — NEVER: patterns with 10+ trades AND <25% win rate
- OBSERVATIONS: patterns with 5-9 trades (any win rate)
- Patterns with <5 trades are not shown (insufficient data)
- DIMENSION INSIGHTS: top insight from each of the 5 dimensions, only if 5+ trades in that bucket
- PARAMETER CHANGES ACTIVE: pulled from `change_log` table where `reverted=false`

---

## 5. Daily Report (`lessons/daily/YYYY-MM-DD.md`)

Human-readable analysis generated at end of each trading day.

### Format

```markdown
# Daily Learning Report — YYYY-MM-DD

## Performance Summary
- Trades closed today: [n] ([w]W/[l]L)
- Daily realized P&L: $[amount]
- Running win rate: [rate]% ([W]W/[L]L lifetime)
- Running total P&L: $[amount]

## Dimension Analysis

### Time-of-Day
| Window | W/L | Avg P&L | Trend |
|--------|-----|---------|-------|

### Hold Duration
| Bucket | W/L | Avg P&L | Trend |
|--------|-----|---------|-------|

### Market Regime
| Regime | W/L | Avg P&L | Trend |
|--------|-----|---------|-------|

### Asset Class x Strategy
| Class | Strategy | W/L | Avg P&L |
|-------|----------|-----|---------|

## Parameter Changes
- AUTO-APPLIED: [details]
- PROPOSED: [details]
- REVERTED: [details]
- CONTESTED: [details]

## Actionable Insights
1. [Numbered list of human-readable recommendations]
2. [Derived from cross-dimensional analysis]
3. [Specific, not generic — references actual data]
```

### Generation Trigger

- **Automatic**: New daily cron fires at 4:05 PM ET on market days, midnight ET on weekends/crypto-only days
- **Manual**: `review-day` command still works for on-demand generation
- Both trigger the full pipeline: pattern_analyzer → optimizer → strategy brief → daily report

---

## 6. Dashboard Learning Page

Replace the existing `/lessons` page with `/learning`.

### Layout: 4 sections

**Section 1: Performance Overview (top stats bar)**
- Lifetime win rate with trend arrow (improving/declining vs prior 7 days)
- Total completed trades
- Total realized P&L
- Active parameter changes count

**Section 2: Dimension Charts**
- Time-of-day heatmap: rows = strategies, columns = time windows, cell color = win rate (green > 60%, yellow 40-60%, red < 40%)
- Hold duration bar chart: win rate by duration bucket, grouped by strategy
- Market regime comparison: grouped bar chart, high vol vs low vol vs normal, per strategy
- Asset class breakdown: stocks vs crypto, per strategy

All charts show trade count in each cell/bar to indicate confidence level. Cells with < 3 trades are grayed out.

**Section 3: Parameter Change Timeline**
- Chronological list of all changes from `change_log` table
- Each entry: date, parameter path, old → new, reason, trade count, status badge
- Status badges: green "Active", yellow "Evaluating (n/10)", red "Reverted", gray "Contested/Locked"
- Manual revert button for active changes

**Section 4: Strategy Brief Preview**
- Live rendered markdown of current `strategy-brief.md`
- "Last updated" timestamp
- Diff highlight showing what changed since previous version (optional, Phase 1.5)

### API Endpoints

| Endpoint | Method | Response |
|----------|--------|----------|
| `GET /api/learning/report` | GET | Latest `LearningReport` JSON (all 5 dimensions) |
| `GET /api/learning/changes` | GET | `change_log` rows, newest first |
| `GET /api/learning/performance` | GET | Win rate + P&L time series (daily buckets) |
| `POST /api/learning/revert/{id}` | POST | Revert a specific parameter change by change_log ID |

---

## 7. Integration & Automation

### Enhanced Trade Lifecycle

1. Cron fires → reads `strategy-brief.md` (now includes dimension insights + active parameter changes)
2. Analyzes market → decides to BUY
3. `main.py` generates `position_id` (UUID) → attaches to decision + trade
4. Logs: `decision(position_id, action=buy, signals_snapshot)`
5. Executes: `trade(position_id, side=buy)`
6. ... time passes, HOLD decisions logged with same `position_id` ...
7. Cron fires → analyzes position → decides to SELL
8. Logs: `decision(position_id, action=sell, signals_snapshot)`
9. Executes: `trade(position_id, side=sell)`

### Learning Loop (daily, automated)

1. End-of-day cron fires (4:05 PM ET market days, midnight crypto-only days)
2. `review-day` command runs:
   a. Query all closed positions (have both buy + sell with matching `position_id`)
   b. `pattern_analyzer.py` slices across 5 dimensions → `LearningReport`
   c. `optimizer.py` evaluates parameter changes:
      - Check eval windows on active changes (revert if failing after 10 trades)
      - Propose new changes (5-9 trades)
      - Auto-apply confident changes (10+ trades, within guardrails)
      - Write to `change_log` table
      - Update `settings.yaml` if auto-applying (round-trip YAML preserving formatting)
   d. `strategy.py` generates enhanced `strategy-brief.md`
   e. Write daily report to `lessons/daily/YYYY-MM-DD.md`
   f. Update `lessons.json` with new patterns (backward compatible)
3. Next cron cycle reads updated brief → better decisions

### New CLI Commands

| Command | Purpose |
|---------|---------|
| `review-day` (enhanced) | Run full learning pipeline — pattern analysis, optimization, brief generation, daily report |
| `learning-report` | Output latest LearningReport JSON (consumed by dashboard API) |
| `change-log` | Show parameter change history from change_log table |
| `revert-change {id}` | Manually revert a specific parameter change by ID |

### Existing Code Changes

| File | Change |
|------|--------|
| `main.py` | Add `position_id` generation on buy decisions, pass through on sell. Add new CLI commands. |
| `db.py` | Add `position_id` column migration for decisions + trades. Add `change_log` table. New query methods for matched trades by position_id. |
| `learner.py` | Replace FIFO matching with `position_id` join. Keep backward compat for old records without position_id. |
| `strategy.py` | Enhanced brief generation with dimension insights, parameter changes, contested params sections. |
| `executor.py` | Accept and store `position_id` on trade records. |
| `api_server.py` | 3 new GET endpoints + 1 POST endpoint for learning dashboard. |

### No Changes To

`scanner.py`, `sentiment.py`, `technicals.py`, `watchlist.py`, `risk_manager.py`, `portfolio.py`, `portfolio_tracker.py`, `config/loader.py`

---

## 8. Phase 2/3 Extension Points

The learning engine is designed to support future phases without rewrites:

### Phase 2: Historical Data Prediction
- `pattern_analyzer.py` already produces structured `LearningReport` — a prediction engine can consume the same format
- `signals` table stores complete technical snapshots — historical backfill adds more rows, same schema
- `change_log` provides the parameter history needed to backtest "what if we had used these parameters earlier"
- The 5-dimension analysis framework extends naturally to historical data (just more trades to analyze)

### Phase 3: Long-Term Portfolio
- `position_id` lifecycle tracking works for any hold duration (days, weeks, months)
- `hold_duration` bucketing already includes `position` (>5d) — extend with `long_term` (>30d)
- `market_regime` analysis applies to long-term rebalancing decisions
- `change_log` audit trail supports the higher scrutiny long-term portfolio changes require
- Strategy engine already supports multiple strategies with independent capital allocation — add a "long_term_hold" strategy type

---

## 9. Testing Strategy

- Unit tests for `pattern_analyzer.py`: test each dimension bucketing with known trade data
- Unit tests for `optimizer.py`: test guardrails (bounds, max changes, revert logic, contested locking)
- Integration test: full pipeline from matched trades → LearningReport → parameter change → updated brief
- Migration test: verify old records (without position_id) still work with FIFO fallback
- Dashboard: verify all 4 API endpoints return correct data shapes
