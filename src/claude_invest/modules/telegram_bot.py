"""
Telegram Bot Module
===================
Polls Telegram for inbound commands and dispatches them to existing CLI functions.
Supports portfolio queries, analysis, and trade execution with confirmation safety.

Commands:
  /status       — Portfolio equity/cash/PnL summary
  /analyze SYM  — Technicals + sentiment for a symbol
  /watchlist    — List watchlist symbols
  /buy SYM QTY  — Buy (requires confirmation)
  /sell SYM QTY — Sell (requires confirmation)
  /core         — Core holdings status
  /health       — Core guardian health check
  /stop         — Stop the trading engine (requires confirmation)
  /resume       — Resume the trading engine
  /help         — Show available commands
"""

import logging
import os
import time
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DB_PATH = "claude_invest.db"

# ---------------------------------------------------------------------------
# Pending confirmation state (module-level globals)
# ---------------------------------------------------------------------------
_pending_confirmation: dict = {}   # keys: chat_id -> {"action": str, "args": list}
_pending_timestamp: float = 0.0
_CONFIRMATION_TTL = 60.0            # seconds before a pending confirmation expires


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def parse_command(text: str) -> tuple[Optional[str], list[str]]:
    """Parse a Telegram message into (command, args).

    Returns (None, []) if the text does not start with '/'.
    """
    text = text.strip()
    if not text.startswith("/"):
        return None, []
    parts = text.split()
    cmd = parts[0][1:]   # strip leading '/'
    # Strip bot username suffix (e.g. /status@MyBot)
    if "@" in cmd:
        cmd = cmd.split("@")[0]
    args = parts[1:]
    return cmd, args


def is_authorized(chat_id: int) -> bool:
    """Return True if chat_id matches the configured TELEGRAM_CHAT_ID env var."""
    allowed = os.environ.get("TELEGRAM_CHAT_ID", "")
    try:
        return int(allowed) == int(chat_id)
    except (ValueError, TypeError):
        return False


def dispatch_command(cmd: str, args: list[str]) -> str:
    """Dispatch a parsed command to the appropriate handler.

    Returns a string response (HTML-safe for Telegram HTML parse_mode).
    """
    handlers = {
        "status": _cmd_status,
        "analyze": _cmd_analyze,
        "watchlist": _cmd_watchlist,
        "core": _cmd_core,
        "health": _cmd_health,
        "buy": _cmd_trade_confirm,
        "sell": _cmd_trade_confirm,
        "stop": _cmd_stop_confirm,
        "resume": _cmd_resume,
        "help": _cmd_help,
    }
    handler = handlers.get(cmd.lower())
    if handler is None:
        return f"Unknown command: /{cmd}\n\nType /help for a list of commands."
    return handler(cmd, args)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def _cmd_status(cmd: str, args: list[str]) -> str:
    try:
        from claude_invest.modules.portfolio import get_portfolio
        p = get_portfolio()
        equity = p.get("equity", 0.0)
        cash = p.get("cash", 0.0)
        daily_pnl = p.get("daily_pnl", 0.0)
        position_count = p.get("position_count", 0)
        pnl_sign = "+" if daily_pnl >= 0 else ""
        lines = [
            "<b>Portfolio Status</b>",
            f"Equity:     ${equity:,.2f}",
            f"Cash:       ${cash:,.2f}",
            f"Daily PnL:  {pnl_sign}{daily_pnl:,.2f}",
            f"Positions:  {position_count}",
        ]
        positions = p.get("positions", [])
        if positions:
            lines.append("")
            lines.append("<b>Open Positions</b>")
            for pos in positions[:10]:   # cap at 10 to avoid message truncation
                sym = pos.get("symbol", "?")
                qty = pos.get("qty", 0)
                val = pos.get("market_value", 0.0)
                lines.append(f"  {sym}: {qty} shares  (${val:,.2f})")
            if len(positions) > 10:
                lines.append(f"  … and {len(positions) - 10} more")
        return "\n".join(lines)
    except Exception as e:
        logger.exception("_cmd_status failed")
        return f"Error fetching portfolio: {e}"


def _cmd_analyze(cmd: str, args: list[str]) -> str:
    if not args:
        return "Usage: /analyze SYMBOL\nExample: /analyze AAPL"
    symbol = args[0].upper()
    lines = [f"<b>Analysis: {symbol}</b>"]
    try:
        from claude_invest.modules.technicals import analyze_technicals
        t = analyze_technicals(symbol)
        price = t.get("current_price", "N/A")
        rsi = t.get("rsi", "N/A")
        macd = t.get("macd", "N/A")
        macd_sig = t.get("macd_signal", "N/A")
        trend = t.get("trend", "N/A")
        lines += [
            "",
            "<b>Technicals</b>",
            f"Price:       {price}",
            f"RSI:         {rsi}",
            f"MACD:        {macd}",
            f"MACD Signal: {macd_sig}",
            f"Trend:       {trend}",
        ]
    except Exception as e:
        lines.append(f"Technicals error: {e}")

    try:
        from claude_invest.modules.sentiment import analyze_sentiment
        s = analyze_sentiment(symbol)
        score = s.get("score", "N/A")
        count = s.get("article_count", "N/A")
        lines += [
            "",
            "<b>Sentiment</b>",
            f"Score:    {score}",
            f"Articles: {count}",
        ]
    except Exception as e:
        lines.append(f"Sentiment error: {e}")

    return "\n".join(lines)


def _cmd_watchlist(cmd: str, args: list[str]) -> str:
    try:
        from claude_invest.modules.watchlist import load_watchlist
        items = load_watchlist()
        if not items:
            return "Watchlist is empty."
        lines = ["<b>Watchlist</b>"]
        for item in items:
            sym = item.get("symbol", "?")
            note = item.get("note", "").replace("<", "&lt;").replace(">", "&gt;")
            held = item.get("held", False)
            held_marker = " [held]" if held else ""
            entry = f"  {sym}{held_marker}"
            if note:
                entry += f" — {note}"
            lines.append(entry)
        return "\n".join(lines)
    except Exception as e:
        logger.exception("_cmd_watchlist failed")
        return f"Error loading watchlist: {e}"


def _cmd_core(cmd: str, args: list[str]) -> str:
    try:
        from claude_invest.modules.core_engine import get_core_status
        from claude_invest.config.loader import load_config
        from claude_invest.modules.db import Database
        from claude_invest.modules.portfolio import get_portfolio

        config = load_config()
        db = Database(DB_PATH)
        portfolio = get_portfolio()
        status = get_core_status(config, db, portfolio)

        core_capital = status.get("core_capital", 0.0)
        cash_remaining = status.get("cash_remaining", 0.0)
        next_rebalance = status.get("next_rebalance_date", "N/A")
        holdings = status.get("holdings", [])

        lines = [
            "<b>Core Holdings</b>",
            f"Core Capital:   ${core_capital:,.2f}",
            f"Cash Remaining: ${cash_remaining:,.2f}",
            f"Next Rebalance: {next_rebalance}",
        ]
        if holdings:
            lines.append("")
            lines.append("<b>Holdings</b>")
            for h in holdings:
                sym = h.get("symbol", "?")
                val = h.get("current_value", 0.0)
                weight = h.get("weight", 0.0)
                target = h.get("target_weight", 0.0)
                drift = h.get("drift", 0.0)
                lines.append(
                    f"  {sym}: ${val:,.2f}  wt={weight:.1%} tgt={target:.1%} drift={drift:+.1%}"
                )
        return "\n".join(lines)
    except Exception as e:
        logger.exception("_cmd_core failed")
        return f"Error fetching core status: {e}"


def _cmd_health(cmd: str, args: list[str]) -> str:
    try:
        from claude_invest.modules.core_guardian import check_core_health, update_peaks
        from claude_invest.config.loader import load_config
        from claude_invest.modules.db import Database
        from claude_invest.modules.portfolio import get_portfolio
        from claude_invest.modules.core_engine import get_core_status

        config = load_config()
        db = Database(DB_PATH)
        portfolio = get_portfolio()

        # Update peaks before health check
        core_cfg = config.get("core_holdings", {})
        core_symbols = {item["symbol"] for item in core_cfg.get("buy_list", [])}
        update_peaks(db, portfolio, core_symbols)

        result = check_core_health(config, db, portfolio)

        warnings = result.get("warnings", [])
        trims = result.get("trims", [])
        exits = result.get("exits", [])
        crash_override = result.get("crash_override", False)

        lines = ["<b>Core Health Check</b>"]
        if crash_override:
            lines.append("Crash Override: ACTIVE (exits suspended)")
        lines.append(f"Warnings: {len(warnings)}")
        lines.append(f"Trims:    {len(trims)}")
        lines.append(f"Exits:    {len(exits)}")

        for w in warnings:
            lines.append(f"  WARN: {w}")
        for t in trims:
            lines.append(f"  TRIM: {t}")
        for e in exits:
            lines.append(f"  EXIT: {e}")

        if not warnings and not trims and not exits:
            lines.append("All core positions healthy.")

        return "\n".join(lines)
    except Exception as e:
        logger.exception("_cmd_health failed")
        return f"Error running health check: {e}"


def _cmd_trade_confirm(cmd: str, args: list[str]) -> str:
    """Handle /buy and /sell — sets up pending confirmation."""
    global _pending_confirmation, _pending_timestamp

    side = cmd.lower()   # "buy" or "sell"
    if len(args) < 2:
        return f"Usage: /{side} SYMBOL QTY\nExample: /{side} AAPL 1"

    symbol = args[0].upper()
    try:
        qty = float(args[1])
    except ValueError:
        return f"Invalid quantity: {args[1]}"

    _pending_confirmation = {"action": side, "symbol": symbol, "qty": qty}
    _pending_timestamp = time.time()

    return (
        f"<b>Confirm {side.upper()}</b>\n"
        f"Symbol: {symbol}\n"
        f"Qty:    {qty}\n\n"
        f"Reply <b>yes</b> to execute, or anything else to cancel.\n"
        f"(Expires in 60 seconds)"
    )


def _cmd_stop_confirm(cmd: str, args: list[str]) -> str:
    """Handle /stop — sets up pending confirmation."""
    global _pending_confirmation, _pending_timestamp

    _pending_confirmation = {"action": "stop"}
    _pending_timestamp = time.time()

    return (
        "<b>Confirm STOP</b>\n"
        "This will halt the trading engine.\n\n"
        "Reply <b>yes</b> to stop, or anything else to cancel.\n"
        "(Expires in 60 seconds)"
    )


def _cmd_resume(cmd: str, args: list[str]) -> str:
    """Handle /resume — resumes the trading engine."""
    try:
        # Signal via a sentinel file that run_bot / cron checks
        import pathlib
        sentinel = pathlib.Path("/tmp/claude_invest_stop")
        if sentinel.exists():
            sentinel.unlink()
            return "Trading engine resumed."
        return "Trading engine was not stopped — nothing to resume."
    except Exception as e:
        logger.exception("_cmd_resume failed")
        return f"Error resuming engine: {e}"


def _cmd_help(cmd: str, args: list[str]) -> str:
    return (
        "<b>Available Commands</b>\n\n"
        "/status            — Portfolio equity/cash/PnL\n"
        "/analyze SYMBOL    — Technicals + sentiment\n"
        "/watchlist         — View watchlist\n"
        "/buy SYMBOL QTY    — Buy shares (confirmation required)\n"
        "/sell SYMBOL QTY   — Sell shares (confirmation required)\n"
        "/core              — Core holdings status\n"
        "/health            — Core guardian health check\n"
        "/stop              — Stop trading engine (confirmation required)\n"
        "/resume            — Resume trading engine\n"
        "/help              — Show this message"
    )


# ---------------------------------------------------------------------------
# Confirmation handler
# ---------------------------------------------------------------------------

def handle_confirmation(text: str) -> Optional[str]:
    """Process a yes/no reply to a pending confirmation.

    Returns a response string if a pending confirmation was handled,
    or None if there is no active confirmation.
    """
    global _pending_confirmation, _pending_timestamp

    if not _pending_confirmation:
        return None

    # Check expiry
    if time.time() - _pending_timestamp > _CONFIRMATION_TTL:
        _pending_confirmation = {}
        _pending_timestamp = 0.0
        return "Confirmation expired. No action taken."

    action = _pending_confirmation.get("action", "")
    confirmed = text.strip().lower() == "yes"

    if not confirmed:
        _pending_confirmation = {}
        _pending_timestamp = 0.0
        return "Cancelled."

    # Execute the confirmed action
    try:
        if action in ("buy", "sell"):
            from claude_invest.modules.executor import execute_order
            symbol = _pending_confirmation["symbol"]
            qty = _pending_confirmation["qty"]
            result = execute_order(symbol, action, qty)
            _pending_confirmation = {}
            _pending_timestamp = 0.0
            order_id = result.get("order_id", "N/A")
            status = result.get("status", "N/A")
            return (
                f"<b>{action.upper()} executed</b>\n"
                f"Symbol:   {symbol}\n"
                f"Qty:      {qty}\n"
                f"Order ID: {order_id}\n"
                f"Status:   {status}"
            )

        elif action == "stop":
            import pathlib
            pathlib.Path("/tmp/claude_invest_stop").touch()
            _pending_confirmation = {}
            _pending_timestamp = 0.0
            return "Trading engine stopped. Send /resume to restart."

        else:
            _pending_confirmation = {}
            _pending_timestamp = 0.0
            return f"Unknown pending action: {action}"

    except Exception as e:
        logger.exception("handle_confirmation failed")
        _pending_confirmation = {}
        _pending_timestamp = 0.0
        return f"Error executing confirmed action: {e}"


# ---------------------------------------------------------------------------
# Low-level Telegram API
# ---------------------------------------------------------------------------

def _send_message(token: str, chat_id: str, text: str) -> bool:
    """Send a message via the Telegram Bot API."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        if resp.status_code == 200:
            return True
        logger.warning("Telegram sendMessage returned %d: %s", resp.status_code, resp.text)
        return False
    except Exception as e:
        logger.warning("_send_message failed: %s", e)
        return False


# ---------------------------------------------------------------------------
# Main polling loop
# ---------------------------------------------------------------------------

def run_bot() -> None:
    """Main entry point: poll Telegram for updates and dispatch commands."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set.")
        return

    print("Telegram bot starting up…")

    try:
        from claude_invest.modules.notify import send_alert
        send_alert("Telegram bot online.", category="system")
    except Exception:
        pass

    offset = 0
    poll_url = f"https://api.telegram.org/bot{token}/getUpdates"

    while True:
        try:
            resp = requests.get(
                poll_url,
                params={"timeout": 3, "offset": offset},
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning("getUpdates returned %d", resp.status_code)
                time.sleep(10)
                continue

            data = resp.json()
            updates = data.get("result", [])

            for update in updates:
                offset = update["update_id"] + 1
                message = update.get("message") or update.get("edited_message")
                if not message:
                    continue

                from_chat = message.get("chat", {})
                incoming_chat_id = from_chat.get("id")
                text = (message.get("text") or "").strip()

                if not text:
                    continue

                # Auth check
                if not is_authorized(incoming_chat_id):
                    logger.warning("Unauthorized access attempt from chat_id %s", incoming_chat_id)
                    continue

                # Handle confirmation reply first
                if _pending_confirmation:
                    conf_reply = handle_confirmation(text)
                    if conf_reply is not None:
                        _send_message(token, chat_id, conf_reply)
                        continue

                # Parse and dispatch command
                cmd, args = parse_command(text)
                if cmd is None:
                    # Not a command and no pending confirmation — ignore
                    continue

                response = dispatch_command(cmd, args)
                _send_message(token, chat_id, response)

        except KeyboardInterrupt:
            print("Bot stopped by user.")
            break
        except Exception as e:
            logger.exception("Polling error: %s", e)
            time.sleep(10)

        time.sleep(3)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_bot()
