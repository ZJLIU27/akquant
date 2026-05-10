"""Tests for position repository — YAML read/write."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.positions.models import PositionFile
from app.positions.repository import PositionRepository


@pytest.fixture
def repo(tmp_positions_file: Path) -> PositionRepository:
    return PositionRepository(tmp_positions_file)


def _open(repo: PositionRepository, symbol: str = "000001", **kwargs):
    return repo.create_position_with_transaction(
        symbol,
        kwargs.pop("side", "buy"),
        kwargs.pop("trade_date", "2026-05-08"),
        kwargs.pop("quantity", 1000),
        kwargs.pop("price", 10.5),
        **kwargs,
    )


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
    pos, txn = _open(repo, fee=5, name="平安银行")
    assert txn.side == "buy"
    assert txn.quantity == 1000

    pf = repo.load()
    assert len(pf.positions) == 1
    assert pf.positions[0].symbol == "000001"
    assert pf.positions[0].name == "平安银行"
    assert len(pf.positions[0].transactions) == 1


def test_add_buy_existing_position(repo: PositionRepository):
    _open(repo, name="平安银行")
    _open(repo, trade_date="2026-05-09", quantity=500, price=11.0)
    pf = repo.load()
    assert len(pf.positions) == 2
    assert len(pf.positions[0].transactions) == 1
    assert len(pf.positions[1].transactions) == 1


def test_add_sell(repo: PositionRepository):
    pos, _ = _open(repo)
    txn = repo.add_transaction(pos.id, "sell", "2026-05-10", 500, 11.0)
    assert txn.side == "sell"
    pf = repo.load()
    assert len(pf.positions[0].transactions) == 2


def test_edit_transaction(repo: PositionRepository):
    pos, txn = _open(repo)
    edited = repo.edit_transaction(pos.id, txn.id, price=10.6, quantity=800)
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


def test_edit_transaction_fee(repo: PositionRepository):
    pos, txn = _open(repo, fee=0)
    edited = repo.edit_transaction(pos.id, txn.id, fee=5.5)
    assert edited is not None
    assert edited.fee == 5.5
    assert edited.revision == 2

    pf = repo.load()
    audit = pf.positions[0].audit_log
    assert audit[0].before["fee"] == 0
    assert audit[0].after["fee"] == 5.5


def test_edit_transaction_side(repo: PositionRepository):
    pos, txn = _open(repo)
    edited = repo.edit_transaction(pos.id, txn.id, side="sell")
    assert edited is not None
    assert edited.side == "sell"

    pf = repo.load()
    assert pf.positions[0].transactions[0].side == "sell"


def test_edit_transaction_notes_tags_source(repo: PositionRepository):
    pos, txn = _open(repo)
    edited = repo.edit_transaction(
        pos.id, txn.id,
        notes="adjusted", tags=["a", "b"], source="broker",
    )
    assert edited is not None
    assert edited.notes == "adjusted"
    assert edited.tags == ["a", "b"]
    assert edited.source == "broker"

    pf = repo.load()
    t = pf.positions[0].transactions[0]
    assert t.notes == "adjusted"
    assert t.tags == ["a", "b"]
    assert t.source == "broker"


def test_edit_transaction_no_change_skips_revision(repo: PositionRepository):
    pos, txn = _open(repo)
    edited = repo.edit_transaction(pos.id, txn.id, price=10.5)
    assert edited is not None
    assert edited.revision == 1  # no change, revision not bumped

    pf = repo.load()
    assert len(pf.positions[0].audit_log) == 0  # no audit entry


def test_edit_voided_transaction_rejected(repo: PositionRepository):
    pos, txn = _open(repo)
    repo.void_transaction(pos.id, txn.id, "wrong entry")
    with pytest.raises(ValueError, match="voided"):
        repo.edit_transaction(pos.id, txn.id, price=12.0)


def test_void_transaction(repo: PositionRepository):
    pos, txn = _open(repo)
    voided = repo.void_transaction(pos.id, txn.id, void_reason="输入错误")
    assert voided is not None
    assert voided.voided is True
    assert voided.void_reason == "输入错误"

    pf = repo.load()
    assert pf.positions[0].audit_log[-1].action == "void_transaction"


def test_edit_nonexistent_transaction(repo: PositionRepository):
    pos, _ = _open(repo)
    result = repo.edit_transaction(pos.id, "nonexistent-id", price=10.6)
    assert result is None


def test_void_nonexistent_position(repo: PositionRepository):
    result = repo.void_transaction("999999", "any-id")
    assert result is None


def test_add_rule(repo: PositionRepository):
    pos, _ = _open(repo)
    rule = repo.add_rule(pos.id, "risk", "manual_take_profit_stop_loss", {"stop_loss_price": 9.8})
    assert rule is not None
    assert rule.script_id == "manual_take_profit_stop_loss"

    pf = repo.load()
    assert len(pf.positions[0].rules) == 1


def test_delete_rule(repo: PositionRepository):
    pos, _ = _open(repo)
    rule = repo.add_rule(pos.id, "risk", "manual_take_profit_stop_loss")
    assert repo.delete_rule(pos.id, rule.id)
    pf = repo.load()
    assert len(pf.positions[0].rules) == 0


def test_delete_nonexistent_rule(repo: PositionRepository):
    pos, _ = _open(repo)
    assert not repo.delete_rule(pos.id, "nonexistent-id")


def test_validate_no_errors(repo: PositionRepository):
    _open(repo, price=10.0)
    errors = repo.validate()
    assert errors == []


def test_validate_sell_exceeds_remaining(repo: PositionRepository):
    pos, _ = _open(repo, quantity=500, price=10.0)
    repo.add_transaction(pos.id, "sell", "2026-05-10", 600, 11.0)
    errors = repo.validate()
    assert any("sell exceeds remaining" in e for e in errors)


def test_validate_duplicate_position_ids(repo: PositionRepository):
    _open(repo, price=10.0, name="A")
    # Manually inject a duplicate id
    pf = repo.load()
    from app.positions.models import Position
    pf.positions.append(Position(id=pf.positions[0].id, symbol="000001", name="B"))
    repo.save(pf)
    errors = repo.validate()
    assert any("Duplicate position id" in e for e in errors)
