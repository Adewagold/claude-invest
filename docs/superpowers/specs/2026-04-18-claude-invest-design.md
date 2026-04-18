# Claude Invest — Design Spec

## Overview

An AI-powered algorithmic trading system that uses Claude Code as the decision engine. Claude Code runs on a cron schedule, calls Python modules to gather market data and signals, reasons about buy/sell/hold decisions, and executes trades via the Alpaca API. A Next.js dashboard provides real-time monitoring.

**Phase 1:** Paper trading with $5k effective capital (on $80k paper account)
**Phase 2:** Light live trading after confidence is established

**Assets:** US stocks + crypto (Alpaca-supported pairs)

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Claude Code (Cron)                  │
│              The AI Decision Engine                  │
│  - Wakes on variable schedule                       │
│  - Calls Python modules to gather signals           │
│  - Reasons about buy/sell/hold with full context     │
│  - Executes trades via executor module               │
│  - Logs every decision with rationale               │
└──────────┬──────────────────────────┬───────────────┘
           │ calls                    │ writes
           ▼                          ▼
┌─────────────────────┐    ┌─────────────────────┐
│   Python Backend    │    │   SQLite Database    │
│                     │    │                      │
│  ├── scanner        │    │  - trades            │
│  ├── sentiment      │    │  - positions         │
│  ├── technicals     │    │  - signals           │
│  ├── risk_manager   │    │  - portfolio history │
│  ├── executor       │    │  - decisions log     │
│  ├── portfolio      │    │  - config snapshots  │
│  └── api_server     │    └─────────┬────────────┘
│       (FastAPI)     │              │
└─────────┬───────────┘              │ reads
          │ serves                   │
          ▼                          ▼
┌─────────────────────────────────────────────────────┐
│              Next.js Dashboard                       │
│                                                      │
│  - Live positions & P&L                              │
│  - Trade history with AI reasoning                   │
│  - Signal dashboard (sentiment + technicals)         │
│  - Discovery feed                                    │
│  - Risk status (PDT count, daily P&L, exposure)      │
│  - Config viewer/editor                              │
└─────────────────────────────────────────────────────┘
```

### Key Design Decision

Claude Code is the strategist, not the Python code. The Python modules are "tools" that gather data and execute orders. Claude Code reads all signals holistically and makes nuanced trading decisions with AI reasoning. This means the trading logic improves by tuning prompts, not rewriting algorithms.

---

## Python Backend

### Project Structure

```
src/
├── config/
│   └── settings.yaml          # All tunable parameters
├── modules/
│   ├── scanner.py             # Market scanner & ticker discovery
│   ├── sentiment.py           # News sentiment analysis
│   ├── technicals.py          # Technical indicators (RSI, MACD, MA)
│   ├── risk_manager.py        # Position sizing, PDT, loss limits
│   ├── executor.py            # Alpaca order execution
│   ├── portfolio.py           # Portfolio state & P&L tracking
│   └── db.py                  # SQLite read/write layer
├── api/
│   └── server.py              # FastAPI server for the dashboard
└── main.py                    # CLI entry point Claude Code calls
```

### Module Responsibilities

| Module | Input | Output |
|--------|-------|--------|
| **scanner** | Alpaca snapshots API, news API | Ranked list of tickers with volume + news scores |
| **sentiment** | Ticker symbol | Sentiment score (-1 to +1) from Alpaca news API headlines, scored locally using keyword analysis + TextBlob/VADER NLP |
| **technicals** | Ticker symbol, price history | Signal object: RSI, MACD, moving averages, trend direction |
| **risk_manager** | Proposed trade, current portfolio | Approve/reject + adjusted position size. Tracks PDT count, daily P&L |
| **executor** | Order details (symbol, side, qty) | Order confirmation from Alpaca (paper or live) |
| **portfolio** | None (reads Alpaca account) | Current positions, buying power, P&L, exposure breakdown |
| **db** | Various | Persists trades, signals, decisions, portfolio snapshots to SQLite |

### CLI Interface

Claude Code interacts via CLI commands that return structured JSON:

```bash
python main.py portfolio                    # Current portfolio state
python main.py scan                         # Run market scanner
python main.py analyze {ticker}             # Full signal analysis for a ticker
python main.py risk-check {ticker} {size}   # Check if trade is within risk limits
python main.py execute buy {ticker} {qty}   # Execute a buy order
python main.py execute sell {ticker} {qty}  # Execute a sell order
python main.py log-decision {json}          # Log a decision with reasoning
```

### Dependencies

- `alpaca-py` — Alpaca trading API SDK
- `pandas` — Data manipulation for price history
- `ta` — Technical analysis library (RSI, MACD, Bollinger, etc.)
- `fastapi` + `uvicorn` — API server for dashboard
- `pyyaml` — Config parsing
- `aiosqlite` — Async SQLite for FastAPI

---

## Configuration

All parameters are tunable via `src/config/settings.yaml`:

```yaml
mode: paper                    # paper | live
capital: 5000                  # effective capital to trade with
max_positions: 8               # max concurrent open positions
max_per_ticker: 0.10           # max 10% of capital per ticker
position_size_pct: 0.02        # 2% per trade default
daily_loss_limit: -150         # stop trading if down $150 in a day
pdt_tracking: true             # enforce 3 day-trades per 5 rolling days

exit_strategy:
  stop_loss_pct: 0.05          # hard stop at -5%
  trailing_stop_pct: 0.03     # trailing stop at 3%
  signal_exit: true            # exit on sentiment/technical reversal

polling:
  market_open_interval: 5      # minutes, 9:30-10:30 ET
  market_close_interval: 5     # minutes, 3:00-4:00 ET
  midday_interval: 15          # minutes, 10:30-3:00 ET
  crypto_interval: 60          # minutes, 24/7

discovery:
  min_relative_volume: 2.0     # 2x average volume to flag
  min_news_count: 2            # at least 2 recent articles
  sentiment_threshold: 0.3     # minimum sentiment score to consider

trading_style: mixed           # day | swing | mixed
```

---

## Discovery Engine

### How Tickers Enter the Radar

Two-signal confirmation required:

1. **Volume signal** — Relative volume > 2x average (via Alpaca snapshots API)
2. **News signal** — At least 2 recent news articles with sentiment > 0.3 (via Alpaca news API)

Both signals must fire for a ticker to be flagged as a candidate. This prevents chasing noise from volume-only spikes or news-only stories with no market reaction.

**For crypto:** Alpaca supports a defined set of crypto pairs. The scanner checks all available pairs for volume + sentiment signals rather than "discovering" new ones.

---

## Risk Management

### Position Sizing
- Default: 2% of effective capital per trade ($100 on $5k)
- Max per ticker: 10% of capital ($500)
- Max concurrent positions: 8

### Guardrails
- **Daily loss limit:** Trading stops if daily P&L hits -$150
- **PDT tracking:** Under $25k, max 3 day trades per rolling 5-day window. System tracks and blocks day trades that would exceed the limit.
- **No daily profit cap:** System keeps trading as long as valid setups exist and risk limits aren't hit

### Exit Strategy (Configurable)
- **Hard stop-loss:** Exit at -5% from entry (absolute floor)
- **Trailing stop:** Trail by 3%, locks in gains as price rises
- **Signal-based exit:** Exit if sentiment flips negative or technicals reverse (RSI overbought, MACD cross down)
- All three layers are independently toggleable via config

---

## Claude Code Cron — Decision Flow

Each poll cycle:

```
1. PORTFOLIO CHECK
   → python main.py portfolio
   → Are we within risk limits? Daily loss hit → stop for the day.

2. POSITION MANAGEMENT (each open position)
   → python main.py analyze {ticker}
   → Decide: hold, tighten stop, or exit
   → If exit → python main.py execute sell {ticker} {qty}

3. DISCOVERY (if room for new positions)
   → python main.py scan
   → Get ranked candidates, skip tickers already held or recently exited

4. EVALUATION (top candidates)
   → python main.py analyze {ticker}
   → Full signal review, conviction assessment
   → python main.py risk-check {ticker} {proposed_size}
   → If approved → python main.py execute buy {ticker} {qty}

5. LOG
   → Every decision logged with Claude's reasoning
   → python main.py log-decision {payload}
```

### Cron Schedule (Variable Intervals)

| Window | Time (ET) | Interval | Scope |
|--------|-----------|----------|-------|
| Pre-market scan | 9:00 AM | Once | Discovery + prep |
| Market open | 9:30-10:30 AM | 5 min | Stocks + crypto, high volatility |
| Midday | 10:30 AM-3:00 PM | 15 min | Stocks + crypto, steady state |
| Market close | 3:00-4:00 PM | 5 min | End-of-day decisions |
| After hours | 4:00-8:00 PM | 30 min | Swing position review |
| Crypto overnight | 8:00 PM-9:00 AM | 60 min | Crypto only |

---

## Next.js Dashboard

### Pages

| Page | Content |
|------|---------|
| **/ (Overview)** | Portfolio value chart, today's P&L, open positions with live prices, risk status bar |
| **/trades** | Trade history — entry/exit prices, P&L, hold duration, Claude's reasoning |
| **/signals** | Per-ticker signal dashboard: sentiment, RSI, MACD, volume. Color-coded |
| **/discovery** | Scanner feed — flagged tickers, scores, action taken or skip reason |
| **/positions** | Open position details — entry, current P&L, stop levels, signals then vs now |
| **/config** | View/edit settings.yaml — risk limits, intervals, mode toggle |

### Tech Stack
- Next.js (App Router)
- TradingView Lightweight Charts
- Tailwind CSS
- SWR for data fetching (auto-refresh on overview)

### Dashboard is read-only for trading
The config page is the only write surface. No trading from the UI — Claude Code is the sole trading actor.

### FastAPI Endpoints (Backend → Dashboard)

```
GET  /api/portfolio          → current portfolio state
GET  /api/positions          → open positions with live data
GET  /api/trades             → trade history (paginated)
GET  /api/signals/{ticker}   → latest signals for a ticker
GET  /api/discovery          → recent scanner results
GET  /api/decisions          → decision log with reasoning
GET  /api/config             → current config values
PUT  /api/config             → update config
GET  /api/stats              → daily/weekly/monthly P&L stats
```

---

## Database Schema (SQLite)

### Tables

- **trades** — symbol, side, qty, price, timestamp, order_id, trade_type (day/swing), status
- **positions** — symbol, qty, entry_price, entry_time, current_stop, trailing_stop, status
- **signals** — ticker, timestamp, sentiment_score, rsi, macd, volume_ratio, trend
- **decisions** — timestamp, ticker, action (buy/sell/hold/skip), reasoning (text), signals_snapshot (JSON)
- **portfolio_snapshots** — timestamp, total_value, cash, positions_value, daily_pnl
- **discovery_log** — timestamp, ticker, volume_score, news_score, sentiment, action_taken
- **pdt_tracker** — trade_id, date, is_day_trade

---

## Environment & Secrets

```
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # paper trading
```

Stored in `.env`, never committed. `.env.example` provided as template.

---

## Phase Plan

1. **Phase 1 — Paper Trading:** Build everything against paper API. Run for 2+ weeks. Evaluate P&L, decision quality, and system reliability.
2. **Phase 2 — Live Trading:** Switch `mode: live` and `ALPACA_BASE_URL` to production. Start with reduced `capital` and tighter `daily_loss_limit`. Graduate sizing as confidence builds.
