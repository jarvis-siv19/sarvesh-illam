"""Shared tracked defaults plus optional per-house configuration."""
from pathlib import Path
from typing import Any

import yaml


def merge_config(base: Any, override: Any) -> Any:
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override
    merged = base.copy()
    for key, value in override.items():
        merged[key] = merge_config(merged[key], value) if key in merged else value
    return merged


def load_config(directory: Path) -> dict:
    config = yaml.safe_load((directory / "config.yaml").read_text()) or {}
    local_path = directory / "config.local.yaml"
    if local_path.is_file():
        config = merge_config(config, yaml.safe_load(local_path.read_text()) or {})
    return config
