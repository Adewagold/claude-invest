from pathlib import Path

import yaml


class ConfigError(Exception):
    pass


REQUIRED_KEYS = [
    "mode", "capital", "max_positions", "max_per_ticker",
    "position_size_pct", "daily_loss_limit", "pdt_tracking",
    "exit_strategy", "polling", "discovery", "trading_style",
    "portfolio", "risk_tiers",
]

DEFAULT_CONFIG_PATH = Path(__file__).parent / "settings.yaml"


def load_config(path: str | None = None) -> dict:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH

    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ConfigError("Config file must contain a YAML mapping")

    for key in REQUIRED_KEYS:
        if key not in config:
            raise ConfigError(f"Missing required config key: {key}")

    return config
