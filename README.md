# Claude Invest

An AI-powered algorithmic trading system that uses **Claude Code** as the decision engine. Claude Code runs on cron schedules, calls Python modules to gather market data and signals, reasons about buy/sell/hold decisions, and executes trades via the Alpaca API. A Next.js dashboard provides real-time monitoring.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                Claude Code (Cron)                │
│              The AI Decision Engine              │
│  - Wakes on variable schedule                    │
│  - Calls Python modules to gather signals        │
│  - Reasons about buy/sell/hold with full context  │
│  - Executes trades via executor module            │
│  - Logs every decision with rationale            │
└──────────┬──────────────────────────┬────────────┘
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
┌─────────────────────────────────────────────────┐
│              Next.js Dashboard                   │
│                                                  │
│  - Live positions & P&L                          │
│  - Trade history with AI reasoning               │
│  - Signal dashboard (sentiment + technicals)     │
│  - Discovery feed & watchlist                    │
│  - Strategy performance & learning insights      │
└─────────────────────────────────────────────────┘
```

### Key Design Decision

Claude Code is the **strategist**, not the Python code. The Python modules are "tools" that gather data and execute orders. Claude Code reads all signals holistically and makes nuanced trading decisions with AI reasoning. This means the trading logic improves by tuning prompts, not rewriting algorithms.

## Features

- **Multi-strategy trading** — Momentum, mean reversion, core holdings, and volatility scalping
- **Technical analysis** — RSI, MACD, SMA (20/50), trend detection via the `ta` library
- **Sentiment analysis** — News headline scoring via Alpaca News API + TextBlob NLP
- **Risk management** — Daily loss limits, circuit breaker, PDT tracking, position sizing, trailing stops
- **Core holdings engine** — Long-term portfolio with sector-weighted DCA and rebalancing
- **Graduation gate** — Trading positions that prove themselves can graduate to core holdings
- **Core guardian** — Smart exit logic for core holdings to protect against sustained losses
- **Volatility scalper** — Intraday dip buying and news reaction scalping
- **Learning engine** — Tracks win/loss patterns by signal combo, time of day, hold duration
- **Watchlist** — Persistent watchlist with entry criteria notes
- **Telegram notifications** — Trade alerts, circuit breaker notifications, portfolio summaries
- **Next.js dashboard** — Real-time monitoring with 10 pages

## Trading Schedule

Claude Code runs on 4 cron schedules:

| Window | Time (ET) | Interval | Scope |
|--------|-----------|----------|-------|
| Market open | 9:00-9:59 AM, Mon-Fri | 5 min | Stocks + crypto, high volatility |
| Midday | 10:00 AM-2:59 PM, Mon-Fri | 15 min | Stocks + crypto, steady state |
| Market close | 3:00-3:59 PM, Mon-Fri | 5 min | End-of-day exits, reviews |
| Crypto 24/7 | Every hour at :23 | Hourly | Crypto only |

## Project Structure

```
src/claude_invest/
├── main.py                    # CLI entry point
├── config/
│   ├── loader.py              # YAML config loader
│   └── settings.yaml          # All tunable parameters
└── modules/
    ├── scanner.py             # Market scanner & ticker discovery
    ├── sentiment.py           # News sentiment analysis (TextBlob/VADER)
    ├── technicals.py          # Technical indicators (RSI, MACD, SMA)
    ├── risk_manager.py        # Position sizing, PDT, loss limits
    ├── executor.py            # Alpaca order execution
    ├── portfolio.py           # Portfolio state & P&L tracking
    ├── portfolio_tracker.py   # Allocation tier tracking
    ├── db.py                  # SQLite persistence layer
    ├── api_server.py          # FastAPI server for dashboard
    ├── watchlist.py           # Persistent watchlist management
    ├── strategy.py            # Strategy lessons & rules
    ├── strategy_engine.py     # Multi-strategy orchestration
    ├── core_engine.py         # Core holdings DCA & rebalancing
    ├── core_guardian.py       # Smart exit logic for core positions
    ├── graduation.py          # Trading → core holdings promotion
    ├── scalp_engine.py        # Volatility scalping engine
    ├── volatility_scanner.py  # ATR-based volatility screening
    ├── trailing_stop.py       # Trailing stop management
    ├── learner.py             # Pattern analysis & learning
    ├── optimizer.py           # Parameter optimization
    ├── pattern_analyzer.py    # Signal combo pattern tracking
    ├── earnings.py            # Earnings calendar checks
    ├── dividends.py           # Dividend tracking
    ├── notify.py              # Notification dispatch
    └── telegram_bot.py        # Telegram bot integration

dashboard/                     # Next.js frontend
├── src/app/
│   ├── page.tsx               # Overview — portfolio value, P&L, positions
│   ├── positions/             # Open positions with signals
│   ├── trades/                # Trade history with AI reasoning
│   ├── signals/               # Technical + sentiment dashboard
│   ├── discovery/             # Scanner feed
│   ├── watchlist/             # Watchlist management
│   ├── strategies/            # Strategy performance
│   ├── lessons/               # Learning insights
│   ├── learning/              # Pattern analysis
│   ├── config/                # Settings viewer
│   └── core/                  # Core holdings status

lessons/                       # Trading lessons & daily logs
├── strategy-brief.md          # Current strategy rules
├── lessons.json               # Pattern win/loss data
└── daily/                     # Daily trading logs
```

## Setup

### Prerequisites

- Python 3.12+
- Node.js 18+ (for dashboard)
- [Alpaca](https://alpaca.markets/) account (paper or live)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI

### Installation

```bash
# Clone the repo
git clone https://github.com/Adewagold/claude-invest.git
cd claude-invest

# Create Python virtual environment
python -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -e .

# Set up environment variables
cp .env.example .env
# Edit .env with your Alpaca API keys

# Install dashboard dependencies
cd dashboard && npm install && cd ..
```

### Configuration

Edit `src/claude_invest/config/settings.yaml` to tune:

- `capital` — Effective capital to trade with
- `max_positions` — Max concurrent open positions
- `daily_loss_limit` — Circuit breaker threshold
- `position_size_pct` — Default position size as % of capital
- `discovery.min_price` — Minimum stock price (filters penny stocks)
- `discovery.min_relative_volume` — Volume spike threshold
- `exit_strategy` — Stop loss, trailing stop, signal-based exit settings
- `core_holdings.buy_list` — Long-term portfolio tickers and weights
- `volatility_scalper` — Scalping strategy parameters

### Running

```bash
# Start the FastAPI backend
source .venv/bin/activate
uvicorn claude_invest.modules.api_server:create_app --factory --host 0.0.0.0 --port 8000

# Start the dashboard (separate terminal)
cd dashboard && npm run dev

# Start trading via Claude Code
cd /path/to/claude-invest
claude  # then say "start trading crons"
```

## CLI Commands

```bash
python src/claude_invest/main.py portfolio              # Current portfolio state
python src/claude_invest/main.py scan                   # Run market scanner
python src/claude_invest/main.py analyze <ticker>       # Full signal analysis
python src/claude_invest/main.py risk-check <t> <q> <p> # Check trade risk
python src/claude_invest/main.py execute buy <t> <q>    # Execute a buy order
python src/claude_invest/main.py execute sell <t> <q>   # Execute a sell order
python src/claude_invest/main.py watchlist               # View watchlist
python src/claude_invest/main.py watchlist-add <sym>     # Add to watchlist
python src/claude_invest/main.py scalp-cycle             # Run scalp engine
python src/claude_invest/main.py core-status             # Core holdings status
python src/claude_invest/main.py core-cycle              # Run core DCA cycle
python src/claude_invest/main.py trailing-status         # Check trailing stops
python src/claude_invest/main.py review-day              # End-of-day review
python src/claude_invest/main.py learning-report         # Pattern analysis
python src/claude_invest/main.py strategies              # Strategy performance
python src/claude_invest/main.py log-decision <json>     # Log a decision
```

## Risk Management

- **Circuit breaker** — Trading halts if daily P&L hits the loss limit (-$150 default)
- **PDT tracking** — Enforces 3 day-trade limit per rolling 5-day window (under $25k)
- **Position sizing** — 2% of capital per trade, max 10% per ticker
- **Trailing stops** — Configurable trailing stop percentage
- **DCA protection** — Allows adding to existing positions at max capacity, blocks new entries
- **Scanner quality filter** — Minimum $5 price excludes penny stocks

## Tech Stack

**Backend:** Python 3.12, FastAPI, alpaca-py, pandas, ta, TextBlob, SQLite

**Frontend:** Next.js 16, TailwindCSS, SWR, TradingView Lightweight Charts

**AI Engine:** Claude Code with cron-based scheduling

**Broker:** Alpaca (paper trading / live)

**Notifications:** Telegram Bot API

## Disclaimer

This is an experimental AI trading system for educational and research purposes. It is configured for **paper trading** by default. Use at your own risk. Past performance does not guarantee future results. Always understand the risks before trading with real money.

## License

MIT
