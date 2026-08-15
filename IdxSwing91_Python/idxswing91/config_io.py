"""YAML loading for config/default.yaml and config/symbols.yaml."""

from pathlib import Path

import yaml

from .config import StrategyConfig
from .defines import LogLevel


def load_default_config(path: str | Path) -> StrategyConfig:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if "log_level" in data and isinstance(data["log_level"], str):
        data["log_level"] = LogLevel[data["log_level"].upper()]

    return StrategyConfig(symbol="__default__", **data)


def load_symbols_file(path: str | Path) -> tuple[list[str], dict[str, dict]]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    symbols = data.get("symbols", [])
    overrides = data.get("overrides", {})

    for symbol_overrides in overrides.values():
        if "log_level" in symbol_overrides and isinstance(symbol_overrides["log_level"], str):
            symbol_overrides["log_level"] = LogLevel[symbol_overrides["log_level"].upper()]

    return symbols, overrides
