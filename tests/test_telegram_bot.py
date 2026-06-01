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


def test_dispatch_help():
    result = dispatch_command("help", [])
    assert "/status" in result
    assert "/analyze" in result
    assert "/buy" in result


def test_dispatch_unknown():
    result = dispatch_command("foobar", [])
    assert "Unknown" in result or "unknown" in result
