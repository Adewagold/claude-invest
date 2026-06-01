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
    emoji = CATEGORY_EMOJI.get(category, "📌")
    return f"{emoji} {message}"


def send_alert(message: str, category: str = "system") -> bool:
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
