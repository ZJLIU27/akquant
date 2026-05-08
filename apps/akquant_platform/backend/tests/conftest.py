"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_positions_file(tmp_path: Path) -> Path:
    return tmp_path / "positions.yaml"


@pytest.fixture
def tmp_intraday_dir(tmp_path: Path) -> Path:
    d = tmp_path / "intraday"
    d.mkdir()
    return d


@pytest.fixture
def tmp_daily_dir(tmp_path: Path) -> Path:
    d = tmp_path / "daily"
    d.mkdir()
    return d


@pytest.fixture
def tmp_registry_file(tmp_path: Path) -> Path:
    return tmp_path / "registry.yaml"
