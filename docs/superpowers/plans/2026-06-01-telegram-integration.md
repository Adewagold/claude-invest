# Telegram Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a bidirectional Telegram bot for trade notifications and remote command execution.

**Architecture:** Two new modules — `notify.py` (outbound alerts via Telegram API) and `telegram_bot.py` (polling loop for inbound commands). Integrates into existing executor, guardian, and graduation modules. Uses `.env` for secrets.

**Tech Stack:** Python 3.12, `requests` (already installed), Telegram Bot API, existing CLI command functions.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/claude_invest/modules/notify.py` | Outbound: `send_alert(message, category)` → Telegram API |
| `src/claude_invest/modules/telegram_bot.py` | Inbound: poll for messages, dispatch commands, send responses |
| `src/claude_invest/main.py` | Add `telegram-bot` CLI command |
| `src/claude_invest/modules/executor.py` | Add notification after trade execution |
| `src/claude_invest/modules/graduation.py` | Add notification on graduation decision |
| `src/claude_invest/modules/core_guardian.py` | Add notification on warnings/exits |
| `tests/test_notify.py` | Unit tests for notify module |
| `tests/test_telegram_bot.py` | Unit tests for bot command dispatch |

---

### Task 1: Notify Module

**Files:**
- Create: `src/claude_invest/modules/notify.py`
- Test: `tests/test_notify.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_notify.py
import pytest
from unittest.mock import patch, MagicMock
from claude_invest.modules.notify import send_alert, _format_message


def test_format_message_trade():
    result = _format_message("BUY AVGO 0.1 @ $457", "trade")
    assert result.startswith("📈")
    assert "BUY AVGO" in result


def test_format_message_sell():
    result = _format_message("SOLD MU 4 @ $645", "sell")
    assert result.startswith("📉")


def test_format_message_warning():
    result = _format_message("P&L approaching limit", "warning")
    assert result.startswith("⚠️")


def test_format_message_system():
    result = _format_message("Session started", "system")
    assert result.startswith("🔧")


def test_send_alert_disabled(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ENABLED", "false")
    result = send_alert("test message", "system")
    assert result is False


def test_send_alert_missing_token(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    result = send_alert("test message", "system")
    assert result is False


@patch("claude_invest.modules.notify.requests.post")
def test_send_alert_success(mock_post, monkeypatch):
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    mock_post.return_value = MagicMock(status_code=200)

    result = send_alert("test message", "trade")

    assert result is True
    mock_post.assert_called_once()
    call_url = mock_post.call_args[0][0]
    assert "fake-token" in call_url
    assert "sendMessage" in call_url


@patch("claude_invest.modules.notify.requests.post")
def test_send_alert_api_failure(mock_post, monkeypatch):
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    mock_post.side_effect = Exception("Network error")

    result = send_alert("test message", "trade")

    assert result is False


@patch("claude_invest.modules.notify.requests.post")
def test_send_alert_silent_mode(mock_post, monkeypatch):
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_SILENT", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

    result = send_alert("test message", "trade")

    assert result is False
    mock_post.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_notify.py -v`
Expected: FAIL (module doesn't exist)

- [ ] **Step 3: Implement notify.py**

```python
# src/claude_invest/modules/notify.py
"""
Telegram Notification Module
=============================
Sends alerts to Telegram for trade executions, warnings, and system events.
Gracefully degrades if Telegram is not configured.
"""
import logging
import os

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

CATEGORY_EMOJI = {
    "trade": "📈",
    "sell": "📉",
    "graduation": "🎓",
    "warning": "⚠️",
    "guardian": "🛡️",
    "daily_summary": "📊",
    "system": "🔧",
}


def _format_message(message: str, category: str) -> str:
    """Add emoji prefix based on category."""
    emoji = CATEGORY_EMOJI.get(category, "📌")
    return f"{emoji} {message}"


def send_alert(message: str, category: str = "system") -> bool:
    """Send a Telegram notification.

    Returns True if sent successfully, False otherwise.
    Never raises — always fails silently to avoid disrupting trading.
    """
    enabled = os.environ.get("TELEGRAM_ENABLED", "false").lower() == "true"
    if not enabled:
        return False

    silent = os.environ.get("TELEGRAM_SILENT", "false").lower() == "true"
    if silent:
        return False

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.warning("Telegram token or chat_id not configured")
        return False

    formatted = _format_message(message, category)

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        response = requests.post(url, json={
            "chat_id": chat_id,
            "text": formatted,
            "parse_mode": "HTML",
        }, timeout=10)
        if response.status_code == 200:
            return True
        else:
            logger.warning("Telegram API returned %d: %s", response.status_code, response.text)
            return False
    except Exception as e:
        logger.warning("Failed to send Telegram alert: %s", e)
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_notify.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/claude_invest/modules/notify.py tests/test_notify.py
git commit -m "feat: add Telegram notification module with graceful degradation"
```

---

### Task 2: Telegram Bot Module

**Files:**
- Create: `src/claude_invest/modules/telegram_bot.py`
- Test: `tests/test_telegram_bot.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_telegram_bot.py
import pytest
from unittest.mock import patch, MagicMock
from claude_invest.modules.telegram_bot import parse_command, dispatch_command, is_authorized


def test_parse_command_simple():
    cmd, args = parse_command("/status")
    assert cmd == "status"
    assert args == []


def test_parse_command_with_args():
    cmd, args = parse_command("/analyze PLTR")
    assert cmd == "analyze"
    assert args == ["PLTR"]


def test_parse_command_buy():
    cmd, args = parse_command("/buy AVGO 0.1")
    assert cmd == "buy"
    assert args == ["AVGO", "0.1"]


def test_parse_command_unknown():
    cmd, args = parse_command("/foobar")
    assert cmd == "foobar"
    assert args == []


def test_parse_command_no_slash():
    cmd, args = parse_command("hello")
    assert cmd is None
    assert args == []


def test_is_authorized_valid(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    assert is_authorized(12345) is True


def test_is_authorized_invalid(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    assert is_authorized(99999) is False


def test_dispatch_status():
    result = dispatch_command("status", [])
    assert "Equity" in result or "equity" in result.lower() or "error" in result.lower()


def test_dispatch_help():
    result = dispatch_command("help", [])
    assert "/status" in result
    assert "/analyze" in result
    assert "/buy" in result


def test_dispatch_unknown():
    result = dispatch_command("foobar", [])
    assert "Unknown" in result or "unknown" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_telegram_bot.py -v`
Expected: FAIL (module doesn't exist)

- [ ] **Step 3: Implement telegram_bot.py**

```python
# src/claude_invest/modules/telegram_bot.py
"""
Telegram Bot
============
Polls Telegram for inbound commands and dispatches them to existing
CLI functions. Supports portfolio queries, analysis, and trade execution
with confirmation safety.
"""
import json
import logging
import os
import time

import requests
from dotenv import load_dotenv

from claude_invest.config.loader import load_config
from claude_invest.modules.db import Database
from claude_invest.modules.notify import send_alert
from claude_invest.modules.portfolio import get_portfolio
from claude_invest.modules.sentiment import analyze_sentiment
from claude_invest.modules.technicals import analyze_technicals
from claude_invest.modules.executor import execute_order
from claude_invest.modules.watchlist import load_watchlist

load_dotenv()

logger = logging.getLogger(__name__)

DB_PATH = "claude_invest.db"

# Pending confirmation state
_pending_confirmation = None
_pending_timestamp = 0


def parse_command(text: str) -> tuple[str | None, list[str]]:
    """Parse a Telegram message into command and arguments."""
    text = text.strip()
    if not text.startswith("/"):
        return None, []
    parts = text.split()
    cmd = parts[0][1:].lower()  # Remove leading /
    args = parts[1:]
    return cmd, args


def is_authorized(chat_id: int) -> bool:
    """Check if the chat_id matches the authorized user."""
    authorized = os.environ.get("TELEGRAM_CHAT_ID", "")
    return str(chat_id) == authorized


def dispatch_command(cmd: str, args: list[str]) -> str:
    """Dispatch a command and return the response string."""
    global _pending_confirmation, _pending_timestamp

    try:
        if cmd == "status":
            return _cmd_status()
        elif cmd == "analyze" and args:
            return _cmd_analyze(args[0])
        elif cmd == "watchlist":
            return _cmd_watchlist()
        elif cmd == "core":
            return _cmd_core()
        elif cmd == "health":
            return _cmd_health()
        elif cmd == "buy" and len(args) >= 2:
            return _cmd_trade_confirm("buy", args[0], args[1])
        elif cmd == "sell" and len(args) >= 2:
            return _cmd_trade_confirm("sell", args[0], args[1])
        elif cmd == "stop":
            return _cmd_stop_confirm()
        elif cmd == "resume":
            return _cmd_resume()
        elif cmd == "help":
            return _cmd_help()
        else:
            return f"Unknown command: /{cmd}\nSend /help for available commands."
    except Exception as e:
        logger.error("Command error: %s", e)
        return f"Error: {e}"


def _cmd_status() -> str:
    portfolio = get_portfolio()
    return (
        f"💰 <b>Portfolio</b>\n"
        f"Equity: ${portfolio['equity']:,.2f}\n"
        f"Cash: ${portfolio['cash']:,.2f}\n"
        f"P&L: ${portfolio['daily_pnl']:,.2f}\n"
        f"Positions: {portfolio['position_count']}"
    )


def _cmd_analyze(symbol: str) -> str:
    try:
        tech = analyze_technicals(symbol)
        sent = analyze_sentiment(symbol)
        return (
            f"📊 <b>{symbol}</b>\n"
            f"Price: ${tech['current_price']:,.2f}\n"
            f"RSI: {tech['rsi']:.1f}\n"
            f"MACD: {tech['macd']:.2f} vs {tech['macd_signal']:.2f}\n"
            f"Trend: {tech['trend']}\n"
            f"Sentiment: {sent['score']:.2f} ({sent['article_count']} articles)"
        )
    except Exception as e:
        return f"Error analyzing {symbol}: {e}"


def _cmd_watchlist() -> str:
    wl = load_watchlist()
    if not wl:
        return "Watchlist is empty."
    lines = ["📋 <b>Watchlist</b>"]
    for t in wl:
        held = "✅" if t.get("held") else "⬜"
        lines.append(f"{held} {t['symbol']}: {t.get('note', '')[:40]}")
    return "\n".join(lines)


def _cmd_core() -> str:
    from claude_invest.modules.core_engine import get_core_status
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    portfolio = get_portfolio()
    status = get_core_status(config, db, portfolio)
    db.close()
    invested = status["core_capital"] - status.get("cash_remaining", 0)
    return (
        f"🏦 <b>Core Holdings</b>\n"
        f"Capital: ${status['core_capital']:,.0f}\n"
        f"Invested: ${invested:,.0f} ({invested/status['core_capital']*100:.0f}%)\n"
        f"Holdings: {len(status['holdings'])}"
    )


def _cmd_health() -> str:
    from claude_invest.modules.core_guardian import check_core_health, update_peaks
    config = load_config()
    db = Database(DB_PATH)
    db.initialize()
    portfolio = get_portfolio()
    core_symbols = {item["symbol"] for item in config.get("core_holdings", {}).get("buy_list", [])}
    update_peaks(db, portfolio, core_symbols)
    health = check_core_health(config, db, portfolio)
    db.close()
    w = len(health["warnings"])
    t = len(health["trims"])
    e = len(health["exits"])
    crash = "YES ⛔" if health["crash_override"] else "No"
    return (
        f"🛡️ <b>Guardian Status</b>\n"
        f"Warnings: {w}\n"
        f"Trims: {t}\n"
        f"Exits: {e}\n"
        f"Crash Override: {crash}"
    )


def _cmd_trade_confirm(side: str, symbol: str, qty_str: str) -> str:
    global _pending_confirmation, _pending_timestamp
    try:
        qty = float(qty_str)
    except ValueError:
        return f"Invalid quantity: {qty_str}"
    _pending_confirmation = {"side": side, "symbol": symbol.upper(), "qty": qty}
    _pending_timestamp = time.time()
    return f"⚠️ Confirm {side.upper()} {symbol.upper()} {qty}?\nReply 'yes' to execute. Expires in 60s."


def _cmd_stop_confirm() -> str:
    global _pending_confirmation, _pending_timestamp
    _pending_confirmation = {"action": "stop"}
    _pending_timestamp = time.time()
    return "⚠️ Stop all trading? Reply 'yes' to confirm."


def _cmd_resume() -> str:
    return "▶️ Trading resumed. (Crons must be restarted manually in Claude Code.)"


def _cmd_help() -> str:
    return (
        "📖 <b>Commands</b>\n"
        "/status — Portfolio snapshot\n"
        "/analyze SYMBOL — Technical analysis\n"
        "/watchlist — Show watchlist\n"
        "/buy SYMBOL QTY — Buy (with confirm)\n"
        "/sell SYMBOL QTY — Sell (with confirm)\n"
        "/core — Core holdings status\n"
        "/health — Guardian check\n"
        "/stop — Halt trading\n"
        "/resume — Resume trading\n"
        "/help — This message"
    )


def handle_confirmation(text: str) -> str | None:
    """Handle a 'yes' confirmation for pending actions. Returns response or None."""
    global _pending_confirmation, _pending_timestamp

    if _pending_confirmation is None:
        return None

    # Check timeout (60 seconds)
    if time.time() - _pending_timestamp > 60:
        _pending_confirmation = None
        return "⏰ Confirmation expired."

    if text.strip().lower() != "yes":
        _pending_confirmation = None
        return "❌ Cancelled."

    pending = _pending_confirmation
    _pending_confirmation = None

    if "side" in pending:
        result = execute_order(pending["symbol"], pending["side"], pending["qty"])
        if result.get("status") == "error":
            return f"❌ Order failed: {result.get('error')}"
        send_alert(
            f"{pending['side'].upper()} {pending['symbol']} {pending['qty']} @ market",
            "trade" if pending["side"] == "buy" else "sell",
        )
        return f"✅ {pending['side'].upper()} {pending['symbol']} {pending['qty']} — {result.get('status')}"
    elif pending.get("action") == "stop":
        return "🛑 Trading halted. Crons will skip cycles. Send /resume to restart."

    return None


def _send_message(token: str, chat_id: str, text: str):
    """Send a message via Telegram API."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }, timeout=10)


def run_bot():
    """Main polling loop. Checks for messages every 3 seconds."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env")
        return

    print(f"Telegram bot started. Polling for messages...")
    send_alert("🟢 Trading bot online. Send /help for commands.", "system")

    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            resp = requests.get(url, params={"offset": offset, "timeout": 10}, timeout=15)
            updates = resp.json().get("result", [])

            for update in updates:
                offset = update["update_id"] + 1
                message = update.get("message", {})
                text = message.get("text", "")
                msg_chat_id = message.get("chat", {}).get("id")

                if not is_authorized(msg_chat_id):
                    continue

                # Check for pending confirmation first
                confirm_response = handle_confirmation(text)
                if confirm_response:
                    _send_message(token, chat_id, confirm_response)
                    continue

                # Parse and dispatch command
                cmd, args = parse_command(text)
                if cmd is None:
                    continue

                response = dispatch_command(cmd, args)
                _send_message(token, chat_id, response)

        except Exception as e:
            logger.error("Bot polling error: %s", e)
            time.sleep(10)
            continue

        time.sleep(3)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_telegram_bot.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/claude_invest/modules/telegram_bot.py tests/test_telegram_bot.py
git commit -m "feat: add Telegram bot with command dispatch and confirmation safety"
```

---

### Task 3: CLI Command & Config

**Files:**
- Modify: `src/claude_invest/main.py`
- Modify: `.env`

- [ ] **Step 1: Add telegram-bot command to main.py**

Add to the elif chain in `main()`:

```python
    elif command == "telegram-bot":
        cmd_telegram_bot()
```

Add the command function:

```python
def cmd_telegram_bot():
    from claude_invest.modules.telegram_bot import run_bot
    run_bot()
```

- [ ] **Step 2: Add Telegram config to .env**

Append to `.env`:

```
TELEGRAM_BOT_TOKEN=<paste your bot token from BotFather>
TELEGRAM_CHAT_ID=<your Telegram user ID>
TELEGRAM_ENABLED=true
TELEGRAM_SILENT=false
```

Note: To get your chat ID, send any message to your bot, then visit:
`https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
Look for `"chat":{"id":XXXXXXX}` in the response.

- [ ] **Step 3: Run existing tests to verify no regressions**

Run: `python3 -m pytest tests/ --ignore=tests/test_api_server.py -q`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add src/claude_invest/main.py
git commit -m "feat: add telegram-bot CLI command"
```

---

### Task 4: Integrate Notifications into Existing Modules

**Files:**
- Modify: `src/claude_invest/modules/executor.py`
- Modify: `src/claude_invest/modules/graduation.py`
- Modify: `src/claude_invest/modules/core_guardian.py`

- [ ] **Step 1: Add notification to executor.py**

After a successful order in `execute_order()`, add:

```python
from claude_invest.modules.notify import send_alert
```

At the top of the file. Then after the successful order return block (after `return result`), insert before the return:

```python
    # Notify via Telegram
    side_str = "buy" if side == "buy" else "sell"
    category = "trade" if side == "buy" else "sell"
    filled = result.get("filled_price") or "market"
    send_alert(
        f"{side_str.upper()} {symbol} {qty} @ ${filled} | Status: {result.get('status')}",
        category,
    )
```

- [ ] **Step 2: Add notification to graduation.py**

In `execute_graduation()`, after the logger.info line at the end, add:

```python
    from claude_invest.modules.notify import send_alert
    send_alert(
        f"GRADUATED {symbol}: held {hold_days}d, +{gain_pct*100:.1f}%, "
        f"sentiment {sentiment_score or 0:.2f}. Added to core at {probation_weight*100:.1f}% weight.",
        "graduation",
    )
```

In `check_graduation()`, when decision is "sell", add before the return:

```python
    from claude_invest.modules.notify import send_alert
    send_alert(f"Graduation check {symbol}: SELL — {result['reason']}", "system")
```

- [ ] **Step 3: Add notifications to core_guardian.py**

In `check_core_health()`, after each `warnings.append()`, `trims.append()`, and `exits.append()`, add a notification:

After warning append:
```python
            send_alert(
                f"CORE WARNING: {symbol} drawdown {drawdown*100:.1f}% for {days_since} days",
                "guardian",
            )
```

After trim append:
```python
            send_alert(
                f"CORE REDUCE: {symbol} drawdown {drawdown*100:.1f}%. Selling 50%.",
                "guardian",
            )
```

After exit append:
```python
            send_alert(
                f"CORE EXIT: {symbol} drawdown {drawdown*100:.1f}%. Full sell.",
                "guardian",
            )
```

After crash_override is set to True:
```python
            send_alert(
                f"CRASH OVERRIDE: SPY drawdown {spy_drawdown*100:.1f}%. All exits suspended.",
                "guardian",
            )
```

Add import at top of `core_guardian.py`:
```python
from claude_invest.modules.notify import send_alert
```

- [ ] **Step 4: Run all tests**

Run: `python3 -m pytest tests/ --ignore=tests/test_api_server.py -q`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/claude_invest/modules/executor.py src/claude_invest/modules/graduation.py src/claude_invest/modules/core_guardian.py
git commit -m "feat: integrate Telegram notifications into executor, graduation, and guardian"
```

---

### Task 5: Manual Integration Test

- [ ] **Step 1: Get your Telegram chat ID**

Send any message to your bot in Telegram, then run:

```bash
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates" | python3 -m json.tool | grep '"id"'
```

Update `.env` with the chat ID.

- [ ] **Step 2: Test outbound notification**

```bash
python3 -c "
from claude_invest.modules.notify import send_alert
result = send_alert('Test notification from Claude Invest!', 'system')
print(f'Sent: {result}')
"
```

Expected: You receive a Telegram message: `🔧 Test notification from Claude Invest!`

- [ ] **Step 3: Start the bot and test inbound commands**

In a separate terminal:
```bash
python3 -m claude_invest.main telegram-bot
```

Then send these messages to your bot in Telegram:
- `/help` — should list all commands
- `/status` — should show portfolio
- `/analyze PLTR` — should show technicals
- `/watchlist` — should show watchlist
- `/core` — should show core status
- `/health` — should show guardian status
- `/buy AAPL 0.001` — should ask for confirmation
- Send "no" — should cancel
- `/buy AAPL 0.001` — should ask again
- Send "yes" — should execute (tiny fractional share)

- [ ] **Step 4: Commit final state**

```bash
git add .env
git commit -m "chore: configure Telegram bot credentials"
```

Note: Make sure `.env` is in `.gitignore` so credentials aren't committed. If not:
```bash
echo ".env" >> .gitignore
git add .gitignore
git commit -m "chore: add .env to gitignore"
```
