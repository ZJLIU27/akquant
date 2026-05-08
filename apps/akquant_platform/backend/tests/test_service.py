"""Tests for position service — integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import PlatformConfig
from app.positions.service import PositionService


@pytest.fixture
def service(tmp_path: Path) -> PositionService:
    positions_file = tmp_path / "positions.yaml"
    daily_dir = tmp_path / "daily"
    intraday_dir = tmp_path / "intraday"
    workspace_dir = tmp_path / "workspace"
    registry_file = workspace_dir / "registry.yaml"

    daily_dir.mkdir()
    intraday_dir.mkdir()
    workspace_dir.mkdir()

    registry_file.write_text("position_rule_registry: {}")

    config = PlatformConfig(
        positions_file=str(positions_file),
        daily_data_dir=str(daily_dir),
        intraday_data_dir=str(intraday_dir),
        workspace_dir=str(workspace_dir),
        registry_file=str(registry_file),
    )
    svc = PositionService(config)
    svc.init()
    return svc


def test_init_creates_file(service: PositionService, tmp_path: Path):
    assert (tmp_path / "positions.yaml").exists()


def test_add_buy_creates_position(service: PositionService):
    txn = service.add_buy("000001", "2026-05-08", 1000, 10.5, name="平安银行")
    assert txn is not None
    assert txn.side == "buy"


def test_add_sell_validates_quantity(service: PositionService):
    result = service.add_sell("000001", "2026-05-10", 500, 11.0)
    assert result is None  # no position exists


def test_add_sell_after_buy(service: PositionService):
    service.add_buy("000001", "2026-05-08", 1000, 10.0)
    txn = service.add_sell("000001", "2026-05-10", 500, 11.0)
    assert txn is not None
    assert txn.side == "sell"


def test_sell_exceeding_remaining_rejected(service: PositionService):
    service.add_buy("000001", "2026-05-08", 500, 10.0)
    result = service.add_sell("000001", "2026-05-10", 600, 11.0)
    assert result is None


def test_list_positions(service: PositionService):
    service.add_buy("000001", "2026-05-08", 1000, 10.0, name="平安银行")
    service.add_buy("600000", "2026-05-08", 500, 8.0, name="浦发银行")
    result = service.list_positions()
    assert len(result.positions) == 2


def test_get_position_detail(service: PositionService):
    service.add_buy("000001", "2026-05-08", 1000, 10.0, name="平安银行")
    detail = service.get_position_detail("000001")
    assert detail is not None
    assert detail.summary.remaining_quantity == 1000
    assert detail.summary.status == "open"


def test_get_daily_chart(service: PositionService, tmp_path: Path):
    import pandas as pd

    dates = pd.date_range("2026-01-01", periods=130, freq="B")
    df = pd.DataFrame(
        {
            "open": [10.0] * 130,
            "close": [10.0 + i * 0.01 for i in range(130)],
            "high": [10.2 + i * 0.01 for i in range(130)],
            "low": [9.8 + i * 0.01 for i in range(130)],
            "volume": [1000000.0] * 130,
        },
        index=dates,
    )
    daily_dir = tmp_path / "daily"
    df.to_parquet(daily_dir / "000001.parquet")

    result = service.get_daily_chart("000001")
    assert result["status"] == "ok"
    assert result["rows"] == 130
    last = result["data"][-1]
    assert last["yellow_line"] is not None
    assert last["white_line"] is not None
    assert "single_pin_short" in last
    assert "brick" in last
    assert "brick_base" in last
    assert "brick_delta" in last
    assert "brick_color" in last


def test_edit_transaction(service: PositionService):
    txn = service.add_buy("000001", "2026-05-08", 1000, 10.0)
    edited = service.edit_transaction("000001", txn.id, price=10.5)
    assert edited is not None
    assert edited.price == 10.5
    assert edited.revision == 2


def test_void_transaction(service: PositionService):
    txn = service.add_buy("000001", "2026-05-08", 1000, 10.0)
    voided = service.void_transaction("000001", txn.id, "错误")
    assert voided is not None
    assert voided.voided is True

    detail = service.get_position_detail("000001")
    assert detail is not None
    assert detail.summary.remaining_quantity == 0  # voided txn ignored
    assert detail.summary.status == "closed"


def test_validate(service: PositionService):
    service.add_buy("000001", "2026-05-08", 500, 10.0)
    errors = service.validate()
    assert errors == []


def test_get_open_symbols(service: PositionService):
    service.add_buy("000001", "2026-05-08", 1000, 10.0)
    service.add_buy("600000", "2026-05-08", 500, 8.0)
    symbols = service.get_open_symbols()
    assert "000001" in symbols
    assert "600000" in symbols
