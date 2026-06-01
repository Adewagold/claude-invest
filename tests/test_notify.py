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
