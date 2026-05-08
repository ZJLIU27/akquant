"""Tests for rules engine — registry + evaluator."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from app.positions.models import Position, PositionSummary
from app.positions.rules import RuleRegistry, evaluate_rules


@pytest.fixture
def registry(tmp_path: Path) -> RuleRegistry:
    reg_file = tmp_path / "registry.yaml"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    reg_file.write_text("""
position_rule_registry:
  manual_take_profit_stop_loss:
    title: "手动止盈止损"
    module: "position_rules.manual_take_profit_stop_loss"
    function: "evaluate"
    params_schema:
      - name: "stop_loss_price"
        type: "number"
        required: false
        label: "止损价"
  nonexistent_rule:
    title: "不存在的规则"
    module: "nonexistent_module"
    function: "evaluate"
""", encoding="utf-8")
    return RuleRegistry(reg_file, workspace)


def test_registry_loads_entries(registry: RuleRegistry):
    registry.load()
    assert "manual_take_profit_stop_loss" in registry.entries
    assert "nonexistent_rule" in registry.entries


def test_validate_script_id(registry: RuleRegistry):
    registry.load()
    assert registry.validate_script_id("manual_take_profit_stop_loss")
    assert not registry.validate_script_id("unknown_rule")


def test_get_script_ids(registry: RuleRegistry):
    registry.load()
    ids = registry.get_script_ids()
    assert len(ids) == 2
    assert ids[0]["script_id"] == "manual_take_profit_stop_loss"


def test_evaluate_rules_missing_script(registry: RuleRegistry):
    registry.load()
    pos = Position(id="p1", symbol="000001", transactions=[])
    summary = PositionSummary(symbol="000001", remaining_quantity=100, avg_cost=10.0)
    rules = [{"id": "r1", "enabled": True, "script_id": "unknown_rule", "params": {}}]
    results = evaluate_rules(pos, summary, None, rules, registry)
    assert len(results) == 1
    assert results[0].status == "error"
    assert results[0].level == "danger"


def test_evaluate_rules_disabled_skipped(registry: RuleRegistry):
    registry.load()
    pos = Position(id="p1", symbol="000001", transactions=[])
    summary = PositionSummary(symbol="000001")
    rules = [{"id": "r1", "enabled": False, "script_id": "test", "params": {}}]
    results = evaluate_rules(pos, summary, None, rules, registry)
    assert len(results) == 0


def test_evaluate_rules_exception_isolation(registry: RuleRegistry):
    """A rule that throws should return error status, not crash."""
    registry.load()
    # Inject a function that raises
    entry = registry.entries["manual_take_profit_stop_loss"]
    entry._loaded_fn = lambda pos, market, params: (_ for _ in ()).throw(RuntimeError("boom"))

    pos = Position(id="p1", symbol="000001", transactions=[])
    summary = PositionSummary(symbol="000001")
    rules = [{"id": "r1", "enabled": True, "script_id": "manual_take_profit_stop_loss", "params": {}}]
    results = evaluate_rules(pos, summary, None, rules, registry)
    assert len(results) == 1
    assert results[0].status == "error"


def test_evaluate_rules_invalid_result_fields(registry: RuleRegistry):
    """Rule returning invalid field values gets corrected."""
    registry.load()
    entry = registry.entries["manual_take_profit_stop_loss"]
    entry._loaded_fn = lambda pos, market, params: {"status": "bad", "level": "bad", "message": "test"}

    pos = Position(id="p1", symbol="000001", transactions=[])
    summary = PositionSummary(symbol="000001")
    rules = [{"id": "r1", "enabled": True, "script_id": "manual_take_profit_stop_loss", "params": {}}]
    results = evaluate_rules(pos, summary, None, rules, registry)
    assert results[0].status == "error"
    assert results[0].level == "danger"
