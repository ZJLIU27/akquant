"""Tests for position repository — YAML read/write."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.positions.models import PositionFile
from app.positions.repository import PositionRepository


@pytest.fixture
def repo(tmp_positions_file: Path) -> PositionRepository:
    return PositionRepository(tmp_positions_file)


def test_init_creates_file(repo: PositionRepository, tmp_positions_file: Path):
    assert not tmp_positions_file.exists()
    repo.init_file()
    assert tmp_positions_file.exists()


def test_init_idempotent(repo: PositionRepository, tmp_positions_file: Path):
    repo.init_file()
    repo.init_file()
    assert tmp_positions_file.exists()


def test_load_empty_file(repo: PositionRepository, tmp_positions_file: Path):
    tmp_positions_file.write_text("positions: []\n")
    pf = repo.load()
    assert pf.positions == []


def test_add_buy_creates_position(repo: PositionRepository):
    txn = repo.add_transaction("000001", "buy", "2026-05-08", 1000, 10.5, fee=5, name="平安银行")
    assert txn.side == "buy"
    assert txn.quantity == 1000

    pf = repo.load()
    assert len(pf.positions) == 1
    assert pf.positions[0].symbol == "000001"
    assert pf.positions[0].name == "平安银行"
    assert len(pf.positions[0].transactions) == 1


def test_add_buy_existing_position(repo: PositionRepository):
    repo.add_transaction("000001", "buy", "2026-05-08", 1000, 10.5, name="平安银行")
    repo.add_transaction("000001", "buy", "2026-05-09", 500, 11.0)
    pf = repo.load()
    assert len(pf.positions) == 1
    assert len(pf.positions[0].transactions) == 2


def test_add_sell(repo: PositionRepository):
    repo.add_transaction("000001", "buy", "2026-05-08", 1000, 10.5)
    txn = repo.add_transaction("000001", "sell", "2026-05-10", 500, 11.0)
    assert txn.side == "sell"
    pf = repo.load()
    assert len(pf.positions[0].transactions) == 2


def test_edit_transaction(repo: PositionRepository):
    txn = repo.add_transaction("000001", "buy", "2026-05-08", 1000, 10.5)
    edited = repo.edit_transaction("000001", txn.id, price=10.6, quantity=800)
    assert edited is not None
    assert edited.price == 10.6
    assert edited.quantity == 800
    assert edited.revision == 2

    pf = repo.load()
    audit = pf.positions[0].audit_log
    assert len(audit) == 1
    assert audit[0].action == "update_transaction"
    assert audit[0].before["price"] == 10.5
    assert audit[0].after["price"] == 10.6


def test_void_transaction(repo: PositionRepository):
    txn = repo.add_transaction("000001", "buy", "2026-05-08", 1000, 10.5)
    voided = repo.void_transaction("000001", txn.id, void_reason="输入错误")
    assert voided is not None
    assert voided.voided is True
    assert voided.void_reason == "输入错误"

    pf = repo.load()
    assert pf.positions[0].audit_log[-1].action == "void_transaction"


def test_edit_nonexistent_transaction(repo: PositionRepository):
    repo.add_transaction("000001", "buy", "2026-05-08", 1000, 10.5)
    result = repo.edit_transaction("000001", "nonexistent-id", price=10.6)
    assert result is None


def test_void_nonexistent_position(repo: PositionRepository):
    result = repo.void_transaction("999999", "any-id")
    assert result is None


def test_add_rule(repo: PositionRepository):
    repo.add_transaction("000001", "buy", "2026-05-08", 1000, 10.5)
    rule = repo.add_rule("000001", "risk", "manual_take_profit_stop_loss", {"stop_loss_price": 9.8})
    assert rule is not None
    assert rule.script_id == "manual_take_profit_stop_loss"

    pf = repo.load()
    assert len(pf.positions[0].rules) == 1


def test_delete_rule(repo: PositionRepository):
    repo.add_transaction("000001", "buy", "2026-05-08", 1000, 10.5)
    rule = repo.add_rule("000001", "risk", "manual_take_profit_stop_loss")
    assert repo.delete_rule("000001", rule.id)
    pf = repo.load()
    assert len(pf.positions[0].rules) == 0


def test_delete_nonexistent_rule(repo: PositionRepository):
    repo.add_transaction("000001", "buy", "2026-05-08", 1000, 10.5)
    assert not repo.delete_rule("000001", "nonexistent-id")


def test_validate_no_errors(repo: PositionRepository):
    repo.add_transaction("000001", "buy", "2026-05-08", 1000, 10.0)
    errors = repo.validate()
    assert errors == []


def test_validate_sell_exceeds_remaining(repo: PositionRepository):
    repo.add_transaction("000001", "buy", "2026-05-08", 500, 10.0)
    repo.add_transaction("000001", "sell", "2026-05-10", 600, 11.0)
    errors = repo.validate()
    assert any("sell exceeds remaining" in e for e in errors)


def test_validate_duplicate_symbols(repo: PositionRepository):
    repo.add_transaction("000001", "buy", "2026-05-08", 1000, 10.0, name="A")
    # Manually inject a duplicate
    pf = repo.load()
    from app.positions.models import Position
    pf.positions.append(Position(id="dup", symbol="000001", name="B"))
    repo.save(pf)
    errors = repo.validate()
    assert any("Duplicate symbol" in e for e in errors)
