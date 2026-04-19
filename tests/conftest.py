import os
import tempfile
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def tmp_db_path(tmp_path):
    """Provide a temporary SQLite database path."""
    return str(tmp_path / "test.db")


@pytest.fixture
def sample_config(tmp_path):
    """Provide a sample config dict matching settings.yaml structure."""
    config = {
        "mode": "paper",
        "capital": 5000,
        "max_positions": 8,
        "max_per_ticker": 0.10,
        "position_size_pct": 0.02,
        "daily_loss_limit": -150,
        "pdt_tracking": True,
        "exit_strategy": {
            "stop_loss_pct": 0.05,
            "trailing_stop_pct": 0.03,
            "signal_exit": True,
        },
        "polling": {
            "market_open_interval": 5,
            "market_close_interval": 5,
            "midday_interval": 15,
            "crypto_interval": 60,
        },
        "discovery": {
            "min_relative_volume": 2.0,
            "min_news_count": 2,
            "sentiment_threshold": 0.3,
        },
        "trading_style": "mixed",
    }
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(yaml.dump(config))
    return config, str(config_path)
