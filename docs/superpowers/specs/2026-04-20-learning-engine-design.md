# Learning Engine & Portfolio Tracker — Design Spec

## Overview

A learning engine that analyzes trading decisions, identifies winning/losing patterns, and feeds lessons back into the trading strategy. Combined with a portfolio tracker that classifies positions by risk tier and sector, monitors allocation drift, and ensures diversification.

Builds on top of the existing day-trading system without modifying it. The existing scanner, sentiment, technicals, risk manager, executor, and cron-based trading all remain unchanged.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              EXISTING SYSTEM (unchanged)             │
│  Scanner → Sentiment → Technicals → Risk → Executor │
│                    ↓ logs to                         │
│              SQLite Database                         │
│         (decisions, trades, signals)                 │
└──────────────────────┬──────────────────────────────┘
                       │ reads from
                       ▼
┌─────────────────────────────────────────────────────┐
│              LEARNING ENGINE (new)                   │
│                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │  Analyzer   │  │   Lessons    │  │  Strategy  │ │
│  │  (learner)  │→ │   Store      │→ │  Builder   │ │
│  │             │  │              │  │            │ │
│  │ - Win/loss  │  │ lessons.json │  │ Generates  │ │
│  │ - Patterns  │  │ daily/*.md   │  │ strategy   │ │
│  │ - Signals   │  │              │  │ brief for  │ │
│  │   combos    │  │              │  │ cron       │ │
│  └─────────────┘  └──────────────┘  │ prompts    │ │
│                                      └────────────┘ │
└──────────────────────┬──────────────────────────────┘
                       │ feeds into
                       ▼
┌─────────────────────────────────────────────────────┐
│           PORTFOLIO TRACKER (new)                    │
│                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │   SAFE   │ │ NEUTRAL  │ │   RISK   │            │
│  │  Target  │ │  Target  │ │  Target  │            │
│  │  config  │ │  config  │ │  config  │            │
│  └──────────┘ └──────────┘ └──────────┘            │
│                                                      │
│  Sector tags: Tech | Energy | Real Estate | Crypto  │
│  Time horizon: Short-term | Long-term               │
│  Drift alerts when allocation off-target             │
└─────────────────────────────────────────────────────┘
```

---

## New Python Modules

### `modules/learner.py` — Pattern Analyzer

Reads the decisions and trades tables from SQLite and produces structured insights.

**Responsibilities:**
- **Trade outcome matching** — For each buy decision, find the corresponding sell (or calculate current unrealized P&L if still open). Determine win (P&L > 0) or loss (P&L <= 0).
- **Signal pattern scoring** — For each trade, extract the signals that were active at entry from the `signals_snapshot` JSON field: RSI range bucket (0-30, 30-50, 50-70, 70-100), MACD position (above/below signal), sentiment range, volume ratio, trend direction. Track win/loss rate per signal combination.
- **Mistake detection** — Flag high-confidence losing patterns. e.g., "Entries at RSI > 70: 0 wins, 2 losses" or "Gap-up biotech at open: 0 wins, 1 loss."
- **Time-of-day analysis** — Track which market windows (open, midday, close) produce best entries.

**Output:** A `LessonReport` dict containing:
```python
{
    "date": "2026-04-20",
    "total_trades": 8,
    "wins": 5,
    "losses": 3,
    "win_rate": 0.625,
    "total_pnl": 12.50,
    "patterns": [
        {
            "signal_combo": "macd_crossover + rsi_40_55 + trend_neutral",
            "wins": 3,
            "losses": 0,
            "avg_pnl": 1.20,
            "confidence": "high"
        },
        {
            "signal_combo": "rsi_above_70 + gap_up",
            "wins": 0,
            "losses": 2,
            "avg_pnl": -8.50,
            "confidence": "high"
        }
    ],
    "mistakes": ["Bought CMND at RSI 74.5 gap-up — stop-lossed at -10.3%"],
    "best_window": "midday",
    "allocation_snapshot": { ... }
}
```

**Key function:** `analyze_day(db: Database, date: str | None = None) -> dict`

### `modules/portfolio_tracker.py` — Allocation Monitor

Reads current positions and classifies them against the target allocation.

**Responsibilities:**
- **Auto-classify sectors** — Query Alpaca asset metadata for each position's sector. Map to standardized categories: Technology, Healthcare, Energy, Real Estate, Financial, Crypto, Meme, Consumer, Industrial, Utilities.
- **Apply manual overrides** — Read `portfolio.sectors.overrides` from config and override auto-classification where specified.
- **Assign risk tier** — Map each sector to a risk tier (safe/neutral/risk) using the `risk_tiers` config mapping.
- **Calculate allocation** — Sum market value per tier, compute percentages, compare to targets from `portfolio.allocation` config.
- **Detect drift** — Flag any tier where actual allocation deviates from target by more than `portfolio.drift_threshold`.
- **Time horizon tagging** — Tag positions as short-term or long-term based on hold duration vs `portfolio.time_horizon` config thresholds.

**Key function:** `get_allocation(config: dict, positions: list[dict]) -> dict`

**Output:**
```python
{
    "total_value": 1312.50,
    "tiers": {
        "safe": {"target": 0.30, "actual": 0.00, "drift": -0.30, "alert": True},
        "neutral": {"target": 0.40, "actual": 0.82, "drift": 0.42, "alert": True},
        "risk": {"target": 0.30, "actual": 0.18, "drift": -0.12, "alert": True}
    },
    "sectors": {
        "healthcare": {"value": 199.82, "pct": 0.15, "positions": ["PFE"]},
        "technology": {"value": 911.13, "pct": 0.69, "positions": ["SNDK"]},
        "crypto": {"value": 99.47, "pct": 0.08, "positions": ["BTCUSD", "ETHUSD"]},
        "meme": {"value": 101.56, "pct": 0.08, "positions": ["TRUMPUSD"]}
    },
    "time_horizon": {
        "short_term": ["BTCUSD", "ETHUSD", "TRUMPUSD", "SNDK"],
        "long_term": ["PFE"]
    }
}
```

### `modules/strategy.py` — Strategy Builder

Takes accumulated lessons and current allocation, generates a strategy brief that cron prompts read.

**Responsibilities:**
- Read `lessons/lessons.json` — accumulated patterns across all trading days
- Read current allocation from portfolio tracker
- Generate `lessons/strategy-brief.md` — a concise text block with:
  - **RULES** (high confidence, 3+ data points): "ALWAYS: Enter on MACD crossover + RSI 40-55. NEVER: Buy at RSI > 70."
  - **OBSERVATIONS** (low confidence, < 3 data points): "NOTE: Gap-up biotechs at open may reverse (1 occurrence)."
  - **ALLOCATION ALERTS**: "Risk tier at 18%, below 30% target — consider adding speculative positions."
  - **WIN RATE**: "Overall: 62.5% win rate. Best pattern: MACD crossover + neutral trend (100% win rate, 3 trades)."

**Key function:** `build_strategy(lessons_path: str, allocation: dict) -> str`

**Output file:** `lessons/strategy-brief.md` — read by cron prompts each cycle.

---

## Config Extension

Added to `src/claude_invest/config/settings.yaml`:

```yaml
portfolio:
  allocation:
    safe: 0.30
    neutral: 0.40
    risk: 0.30
  drift_threshold: 0.10

  sectors:
    overrides:
      TRUMP/USD: "meme"
      DOGE/USD: "meme"
      SHIB/USD: "meme"
      BONK/USD: "meme"
      WIF/USD: "meme"
      PEPE/USD: "meme"

  time_horizon:
    short_term_max_days: 30
    long_term_min_days: 30

risk_tiers:
  safe: ["bonds", "reits", "dividend", "utilities", "consumer_staples"]
  neutral: ["large_cap", "technology", "healthcare", "financial", "industrial", "energy"]
  risk: ["small_cap", "biotech", "meme", "crypto", "penny", "speculative"]
```

All values configurable via the dashboard config page.

---

## CLI Commands

```bash
python main.py review-day              # Run daily analysis, generate lessons + strategy brief
python main.py review-day 2026-04-20   # Analyze a specific date
python main.py allocation              # Show current allocation vs targets with drift alerts
python main.py lessons                 # Show accumulated lessons and pattern scores
```

All return structured JSON for dashboard consumption.

---

## Data Flow — Feedback Loop

```
Trading Day:
  Cron fires → Reads lessons/strategy-brief.md
            → Makes informed decisions
            → Logs to database

End of Day (4:30 PM ET auto-cron OR /review-day):
  Analyzer reads database → Matches trades to outcomes
                          → Scores signal patterns
                          → Detects mistakes
                          → Writes lessons/YYYY-MM-DD.md (daily report)
                          → Updates lessons/lessons.json (cumulative)
                          → Regenerates lessons/strategy-brief.md

Next Trading Day:
  Cron reads updated strategy-brief.md
  → Better decisions based on accumulated learning
```

**Auto-trigger:** A new CronCreate job at `33 16 * * 1-5` (4:33 PM ET weekdays) runs `python main.py review-day`.

**Lesson promotion rules:**
- Pattern with 3+ occurrences and >75% win rate → promoted to RULE (ALWAYS)
- Pattern with 3+ occurrences and <25% win rate → promoted to RULE (NEVER)
- Pattern with <3 occurrences → stays as OBSERVATION
- Rules persist in lessons.json indefinitely
- Observations older than 30 days with no new data are archived

---

## File Structure (new files only)

```
claude-invest/
├── src/claude_invest/
│   └── modules/
│       ├── learner.py           # Pattern analyzer
│       ├── portfolio_tracker.py # Allocation monitor
│       └── strategy.py          # Strategy brief builder
├── lessons/
│   ├── lessons.json             # Cumulative pattern data
│   ├── strategy-brief.md        # Current strategy (read by crons)
│   └── daily/
│       └── 2026-04-20.md        # Daily reports
├── tests/
│   ├── test_learner.py
│   ├── test_portfolio_tracker.py
│   └── test_strategy.py
```

---

## Dashboard Additions

### New page: `/lessons`
- Daily report viewer (select date, see analysis)
- Pattern scoreboard (signal combos ranked by win rate)
- Win/loss chart over time
- Mistake log

### Updated page: `/positions`
- Risk tier badge per position (Safe/Neutral/Risk)
- Allocation donut chart (actual vs target)
- Drift alert banner when any tier is off-target
- Sector breakdown

### Updated page: `/config`
- Portfolio allocation section (safe/neutral/risk sliders)
- Sector overrides editor
- Risk tier mapping editor

---

## FastAPI Endpoints (new)

```
GET  /api/review-day?date=2026-04-20   → Daily analysis report
GET  /api/allocation                    → Current allocation vs targets
GET  /api/lessons                       → Accumulated patterns + rules
GET  /api/strategy-brief                → Current strategy brief text
```

---

## Cron Prompt Modification

Add this line to the beginning of all three trading cron prompts (market hours, after-hours, crypto overnight):

```
Before making any decisions, read the strategy brief:
cat lessons/strategy-brief.md

Apply any RULES strictly. Consider OBSERVATIONS. Check ALLOCATION ALERTS before opening new positions.
```

This is the only change to the existing system — a single line added to each cron prompt.

---

## Backlog (Phase 2 Learning)

For future full analysis upgrade:
- Market regime detection (trending vs choppy days)
- Position correlation analysis (do all crypto move together?)
- Timing analysis (which 15-min windows produce best entries?)
- Drawdown analysis (max drawdown per position, recovery time)
- Sector rotation signals (which sectors are strengthening/weakening?)
