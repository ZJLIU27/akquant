"""Platform configuration loader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[4]


class PlatformConfig(BaseModel):
    """Platform configuration from configs/platform.yaml."""

    workspace_dir: str = "./workspace"
    registry_file: str = "./workspace/registry.yaml"
    daily_data_dir: str = "./data"
    intraday_data_dir: str = "./data/intraday"
    positions_file: str = "./workspace/position_configs/current_positions.yaml"
    backtest_output_dir: str = "./outputs/backtests"
    timezone: str = "Asia/Shanghai"
    intraday_cache_ttl_seconds: int = 300
    intraday_cache_retention_days: int = 7

    def resolve_path(self, key: str) -> Path:
        """Resolve a config path relative to CWD."""
        return Path(getattr(self, key)).resolve()


def load_config(config_path: str | Path | None = None) -> PlatformConfig:
    """Load platform config from YAML file.

    Falls back to defaults if file doesn't exist.
    """
    if config_path is None:
        config_path = REPO_ROOT / "configs" / "platform.yaml"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        example = REPO_ROOT / "configs" / "platform.example.yaml"
        if example.exists():
            config_path = example
        else:
            return _resolve_config_paths(PlatformConfig(), REPO_ROOT)

    with open(config_path, encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}

    return _resolve_config_paths(PlatformConfig(**data), REPO_ROOT)


def _resolve_config_paths(config: PlatformConfig, base_dir: Path) -> PlatformConfig:
    """Resolve configured filesystem paths relative to the repository root."""
    path_fields = [
        "workspace_dir",
        "registry_file",
        "daily_data_dir",
        "intraday_data_dir",
        "positions_file",
        "backtest_output_dir",
    ]
    updates: dict[str, str] = {}
    for field in path_fields:
        value = Path(getattr(config, field))
        if not value.is_absolute():
            value = base_dir / value
        updates[field] = str(value.resolve())
    return config.model_copy(update=updates)
