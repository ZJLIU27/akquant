"""Rules engine — registry loader and rule evaluator."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from .models import Position, PositionSummary, RuleResult


class RegistryEntry(BaseModel):
    """A single entry from the rule registry."""

    title: str = ""
    module: str = ""
    function: str = "evaluate"
    params_schema: list[dict[str, Any]] = []
    _loaded_fn: Any = None


class RuleRegistry:
    """Loads and validates position rule registry from workspace/registry.yaml."""

    def __init__(self, registry_file: str | Path, workspace_dir: str | Path) -> None:
        self._registry_file = Path(registry_file)
        self._workspace_dir = Path(workspace_dir)
        self._entries: dict[str, RegistryEntry] = {}
        self._load_errors: dict[str, str] = {}
        self._loaded = False

    def load(self) -> None:
        """Load registry from YAML."""
        self._entries.clear()
        self._load_errors.clear()
        self._loaded = True

        if not self._registry_file.exists():
            return

        with open(self._registry_file, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        rule_registry = data.get("position_rule_registry", {})
        for key, val in rule_registry.items():
            try:
                self._entries[key] = RegistryEntry(**val)
            except Exception as e:
                self._load_errors[key] = str(e)

    @property
    def entries(self) -> dict[str, RegistryEntry]:
        if not self._loaded:
            self.load()
        return self._entries

    @property
    def load_errors(self) -> dict[str, str]:
        if not self._loaded:
            self.load()
        return self._load_errors

    def validate_script_id(self, script_id: str) -> bool:
        """Check if a script_id is registered."""
        return script_id in self.entries

    def get_script_ids(self) -> list[dict[str, Any]]:
        """Return list of available script IDs with metadata for dropdown."""
        result = []
        for key, entry in self.entries.items():
            result.append({
                "script_id": key,
                "title": entry.title,
                "params_schema": entry.params_schema,
            })
        return result

    def _resolve_function(self, script_id: str) -> Any:
        """Dynamically import and resolve the rule function."""
        entry = self.entries.get(script_id)
        if entry is None:
            return None

        if entry._loaded_fn is not None:
            return entry._loaded_fn

        workspace = str(self._workspace_dir.resolve())
        added = False
        try:
            if workspace not in sys.path:
                sys.path.insert(0, workspace)
                added = True

            module = importlib.import_module(entry.module)
            fn = getattr(module, entry.function, None)
            if fn is not None and callable(fn):
                entry._loaded_fn = fn
                return fn
            return None
        except Exception:
            return None
        finally:
            if added and workspace in sys.path:
                sys.path.remove(workspace)


def evaluate_rules(
    position: Position,
    summary: PositionSummary,
    market: dict[str, Any] | None,
    rules: list[dict[str, Any]],
    registry: RuleRegistry,
) -> list[RuleResult]:
    """Evaluate all enabled rules for a position.

    Args:
        position: Raw position data.
        summary: Computed position summary.
        market: Market data dict with 'latest_price', 'price_source', 'intraday_df'.
        rules: List of position rules (from position.rules).
        registry: Rule registry for resolving script functions.

    Returns:
        List of RuleResult for each enabled rule.
    """
    results: list[RuleResult] = []

    for rule in rules:
        # Support both PositionRule objects and plain dicts
        enabled = rule.enabled if hasattr(rule, "enabled") else rule.get("enabled", True)
        if not enabled:
            continue

        rule_id = rule.id if hasattr(rule, "id") else rule["id"]
        script_id = rule.script_id if hasattr(rule, "script_id") else rule["script_id"]
        params = rule.params if hasattr(rule, "params") else rule.get("params", {})
        fn = registry._resolve_function(script_id)

        if fn is None:
            results.append(RuleResult(
                rule_id=rule_id,
                script_id=script_id,
                status="error",
                level="danger",
                message=f"规则脚本 '{script_id}' 加载失败或未注册",
            ))
            continue

        try:
            position_data = {
                "symbol": position.symbol,
                "name": position.name,
                "remaining_quantity": summary.remaining_quantity,
                "avg_cost": summary.avg_cost,
                "cost_amount": summary.cost_amount,
                "realized_pnl": summary.realized_pnl,
                "unrealized_pnl": summary.unrealized_pnl,
                "status": summary.status,
                "transactions": [
                    {
                        "id": t.id,
                        "side": t.side,
                        "trade_date": str(t.trade_date),
                        "quantity": t.quantity,
                        "price": t.price,
                        "fee": t.fee,
                    }
                    for t in position.transactions
                    if not t.voided
                ],
            }

            result = fn(position_data, market, params)

            # Validate result has required fields
            status = result.get("status", "unknown")
            level = result.get("level", "info")
            message = result.get("message", "")

            if status not in ("normal", "triggered", "unknown"):
                status = "error"
            if level not in ("info", "warning", "danger"):
                level = "danger"

            results.append(RuleResult(
                rule_id=rule_id,
                script_id=script_id,
                status=status,
                level=level,
                message=str(message),
            ))
        except Exception as e:
            results.append(RuleResult(
                rule_id=rule_id,
                script_id=script_id,
                status="error",
                level="danger",
                message=f"规则执行异常: {e}",
            ))

    return results
