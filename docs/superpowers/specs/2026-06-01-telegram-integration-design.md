# Telegram Integration Design

## Overview

Bidirectional Telegram bot for Claude Invest: outbound trade notifications and inbound command execution via polling.

## Architecture: Polling Bot (Approach A)

Two new modules:
- `notify.py` — outbound alerts to Telegram
- `telegram_bot.py` — inbound command polling and dispatch

## Module 1: Outbound Notifications (`notify.py`)

### Interface

```python
def send_alert(message: str, category: str = "system") -> bool:
    """Send a Telegram notification. Returns True if sent successfully."""
```

### Categories

| Category | Emoji | Example |
|----------|-------|---------|
| `trade` | 📈 | `📈 BUY AVGO 0.109 @ $457 \| momentum \| +$50` |
| `sell` | 📉 | `📉 SOLD MU 4 @ $645 \| RSI 82.83 \| +$319 (+14.1%)` |
| `graduation` | 🎓 | `🎓 GRADUATED SNDK to core \| +45.7%` |
| `warning` | ⚠️ | `⚠️ P&L approaching -$150: currently -$113` |
| `guardian` | 🛡️ | `🛡️ CORE WARNING: NVDA drawdown -15% for 5 days` |
| `daily_summary` | 📊 | `📊 Daily: +$34 \| 19 positions \| PLTR +0.3%` |
| `system` | 🔧 | `🔧 Orphan position found: OKLO 12 shares` |

### Integration Points

| Module | When | Category |
|--------|------|----------|
| `executor.py` | After every trade execution | `trade` or `sell` |
| `graduation.py` | On graduate/sell decision | `graduation` |
| `core_guardian.py` | On warnings, trims, exits, crash override | `guardian` |
| Trading cron | Daily loss limit approaching -$120 | `warning` |
| `strategy.py` (review-day) | End-of-day summary | `daily_summary` |
| Session start | Orphan position detected | `system` |

### Graceful Degradation

- If `TELEGRAM_ENABLED=false` or token missing: `send_alert()` returns `False` silently
- If API call fails: logs error, returns `False`, does not raise
- Never blocks or slows the trading cycle

## Module 2: Inbound Commands (`telegram_bot.py`)

### Commands

| Command | Action | Response |
|---------|--------|----------|
| `/status` | Portfolio snapshot | Equity, P&L, position count |
| `/analyze SYMBOL` | Technical + sentiment analysis | RSI, MACD, trend, sentiment |
| `/watchlist` | Show watchlist | Unheld tickers with notes |
| `/buy SYMBOL QTY` | Execute buy (with confirmation) | Order status |
| `/sell SYMBOL QTY` | Execute sell (with confirmation) | Order status |
| `/core` | Core holdings status | Holdings count, deployed %, cash remaining |
| `/health` | Core guardian check | Warnings, trims, exits, crash override |
| `/stop` | Halt trading (set flag) | Confirmation |
| `/resume` | Resume trading | Confirmation |
| `/help` | List all commands | Command reference |

### Security

- Only responds to authorized `TELEGRAM_CHAT_ID` from `.env`
- All other messages silently ignored
- Trade commands (`/buy`, `/sell`, `/stop`) require confirmation:
  1. Bot sends: "Confirm BUY AVGO 0.1? Reply 'yes' to execute."
  2. User replies: "yes"
  3. Bot executes and reports result
- Any reply other than "yes" cancels the action

### Polling Loop

```python
def run_bot():
    """Main polling loop. Checks for messages every 3 seconds."""
    offset = 0
    while True:
        updates = get_updates(offset)
        for update in updates:
            if update.chat_id == AUTHORIZED_CHAT_ID:
                response = dispatch_command(update.text)
                send_message(response)
            offset = update.update_id + 1
        time.sleep(3)
```

- Polls Telegram `getUpdates` API every 3 seconds
- Dispatches to existing CLI command functions (reuses `cmd_portfolio()`, `cmd_analyze()`, etc.)
- On network failure: logs error, waits 10 seconds, retries

### Pending Confirmations

- Stores one pending confirmation in memory: `{"action": "buy", "symbol": "AVGO", "qty": 0.1}`
- If user sends "yes", executes the pending action
- If user sends anything else or a new command, pending confirmation is cleared
- Timeout: pending confirmations expire after 60 seconds

## Configuration

### `.env` additions

```
TELEGRAM_BOT_TOKEN=<from BotFather>
TELEGRAM_CHAT_ID=<your Telegram user ID>
TELEGRAM_ENABLED=true
TELEGRAM_SILENT=false
```

- `TELEGRAM_ENABLED`: master switch for all Telegram functionality
- `TELEGRAM_SILENT`: suppresses outbound notifications but keeps inbound commands active (useful for testing)

### `settings.yaml` addition

```yaml
telegram:
  warning_threshold: -120
  daily_summary_time: "16:10"
```

## CLI Integration

New command in `main.py`:

```bash
python3 -m claude_invest.main telegram-bot
```

Starts the polling loop. Can be run:
- Manually in a terminal tab
- As a Claude Code cron at session start
- As a systemd service on home server (future)

## Data Flow

```
Outbound:
  executor.py ──→ notify.send_alert() ──→ Telegram API ──→ Phone
  core_guardian.py ──→ notify.send_alert() ──→ Telegram API ──→ Phone

Inbound:
  Phone ──→ /analyze PLTR ──→ Telegram API
    ↓
  telegram_bot.py polls getUpdates
    ↓
  dispatch_command("/analyze PLTR")
    ↓
  cmd_analyze("PLTR") → format response
    ↓
  send_message(response) ──→ Telegram API ──→ Phone
```

## Dependencies

- `requests` (already installed) — for Telegram API calls
- No new packages required

## Testing

- Unit tests for `notify.py`: mock requests.post, verify message formatting
- Unit tests for `telegram_bot.py`: mock getUpdates, verify command dispatch
- Integration test: send a test message via `/status` and verify response format
- Security test: verify unauthorized chat_id messages are ignored

## What Does NOT Change

- All existing crons, strategies, rules unchanged
- Dashboard, API server, CLI all unaffected
- System works identically with `TELEGRAM_ENABLED=false`
- No new database tables
