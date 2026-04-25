import json
import os
import pytest
from claude_invest.modules.db import Database
from claude_invest.modules.optimizer import (
    evaluate_parameters,
    apply_change,
    check_evaluation_windows,
    can_apply_more_changes,
    OPTIMIZABLE_PARAMS,
)


@pytest.fixture
def config_path(tmp_path):
    from ruamel.yaml import YAML
    yaml = YAML()
    config = {
        "strategies": {
            "active": ["mean_reversion", "trend_pullback", "momentum"],
            "mean_reversion": {
                "name": "RSI(2) Mean Reversion",
                "enabled": True,
                "capital_pct": 0.33,
                "params": {
                    "rsi_buy_threshold": 25,
                    "rsi_sell_threshold": 65,
                    "max_hold_bars": 5,
                    "stop_loss_pct": 0.01,
                    "take_profit_pct": 0.02,
                },
            },
            "trend_pullback": {
                "name": "MACD Trend",
                "enabled": True,
                "capital_pct": 0.34,
                "params": {"macd_fast": 5, "macd_slow": 35, "stop_loss_pct": 0.02, "take_profit_pct": 0.04},
            },
            "momentum": {
                "name": "Momentum",
                "enabled": True,
                "capital_pct": 0.33,
                "params": {"stop_loss_pct": 0.05, "take_profit_pct": 0.10},
            },
        },
    }
    path = str(tmp_path / "settings.yaml")
    with open(path, "w") as f:
        yaml.dump(config, f)
    return path


def test_optimizable_params_defined():
    assert "rsi_buy_threshold" in OPTIMIZABLE_PARAMS
    assert OPTIMIZABLE_PARAMS["rsi_buy_threshold"]["min"] == 10
    assert OPTIMIZABLE_PARAMS["rsi_buy_threshold"]["max"] == 40


def test_apply_change_updates_yaml(config_path, tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    apply_change(
        config_path=config_path, db=db,
        parameter_path="strategies.mean_reversion.params.rsi_buy_threshold",
        old_value="25", new_value="20",
        reason="Test change", trade_count=10, auto_applied=True,
    )
    from ruamel.yaml import YAML
    yaml = YAML()
    with open(config_path) as f:
        config = yaml.load(f)
    assert config["strategies"]["mean_reversion"]["params"]["rsi_buy_threshold"] == 20
    changes = db.get_change_log()
    assert len(changes) == 1
    assert changes[0]["new_value"] == "20"
    db.close()


def test_apply_change_respects_bounds(config_path, tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    apply_change(
        config_path=config_path, db=db,
        parameter_path="strategies.mean_reversion.params.rsi_buy_threshold",
        old_value="25", new_value="5",
        reason="Test", trade_count=10, auto_applied=True,
    )
    from ruamel.yaml import YAML
    yaml = YAML()
    with open(config_path) as f:
        config = yaml.load(f)
    assert config["strategies"]["mean_reversion"]["params"]["rsi_buy_threshold"] == 10
    db.close()


def test_can_apply_more_changes(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    assert can_apply_more_changes(db) is True
    for i in range(3):
        db.insert_change_log({
            "parameter_path": f"strategies.s{i}.params.p",
            "old_value": "1", "new_value": "2",
            "reason": "test", "trade_count": 10, "auto_applied": True,
        })
    assert can_apply_more_changes(db) is False
    db.close()


def test_evaluate_parameters_with_insufficient_trades():
    trades_by_strategy = {"mean_reversion": [{"win": True, "entry_signals": {"rsi": 18}}]}
    config = {"strategies": {"mean_reversion": {"params": {"rsi_buy_threshold": 25}}}}
    proposals = evaluate_parameters(trades_by_strategy, config)
    assert len(proposals) == 0  # Only 1 trade, need 5 minimum
