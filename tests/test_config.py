import pytest
from claude_invest.config.loader import load_config, ConfigError


def test_load_config_from_file(sample_config):
    config_dict, config_path = sample_config
    config = load_config(config_path)
    assert config["mode"] == "paper"
    assert config["capital"] == 5000
    assert config["max_positions"] == 8
    assert config["exit_strategy"]["stop_loss_pct"] == 0.05


def test_load_config_default():
    """Loading without a path uses the bundled default settings.yaml."""
    config = load_config()
    assert config["mode"] == "paper"
    assert "capital" in config
    assert "exit_strategy" in config
    assert "discovery" in config


def test_load_config_missing_file():
    with pytest.raises(ConfigError):
        load_config("/nonexistent/path/settings.yaml")


def test_config_validates_required_keys(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text("mode: paper\n")
    with pytest.raises(ConfigError, match="capital"):
        load_config(str(bad_config))


def test_config_has_portfolio_section():
    config = load_config()
    assert "portfolio" in config
    assert "allocation" in config["portfolio"]
    assert config["portfolio"]["allocation"]["safe"] == 0.30
    assert config["portfolio"]["allocation"]["neutral"] == 0.40
    assert config["portfolio"]["allocation"]["risk"] == 0.30
    assert "drift_threshold" in config["portfolio"]
    assert "sectors" in config["portfolio"]
    assert "risk_tiers" in config


def test_config_risk_tiers():
    config = load_config()
    assert "safe" in config["risk_tiers"]
    assert "neutral" in config["risk_tiers"]
    assert "risk" in config["risk_tiers"]
    assert "meme" in config["risk_tiers"]["risk"]
    assert "technology" in config["risk_tiers"]["neutral"]
