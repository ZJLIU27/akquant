"""Pydantic models for positions, transactions, rules, and audit log."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Transaction(BaseModel):
    """A single buy or sell transaction."""

    id: str
    side: Literal["buy", "sell"]
    trade_date: date
    quantity: int = Field(gt=0)
    price: float = Field(gt=0)
    fee: float = Field(default=0.0, ge=0)
    source: str = "manual"
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    created_at: datetime
    updated_at: datetime
    revision: int = 1
    voided: bool = False
    voided_at: datetime | None = None
    void_reason: str | None = None


class PositionRule(BaseModel):
    """A rule attached to a position."""

    id: str
    category: Literal["risk", "alert"]
    type: Literal["script"] = "script"
    script_id: str
    enabled: bool = True
    params: dict[str, Any] = Field(default_factory=dict)


class AuditLogEntry(BaseModel):
    """An audit log entry for tracking changes."""

    id: str
    action: str
    transaction_id: str | None = None
    changed_at: datetime
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None


class Position(BaseModel):
    """A single position for one symbol."""

    id: str
    symbol: str
    name: str = ""
    notes: str = ""
    rules: list[PositionRule] = Field(default_factory=list)
    transactions: list[Transaction] = Field(default_factory=list)
    audit_log: list[AuditLogEntry] = Field(default_factory=list)


class PositionFile(BaseModel):
    """Top-level YAML structure for the positions file."""

    positions: list[Position] = Field(default_factory=list)


# --- Computed result models (not stored in YAML) ---


class PositionSummary(BaseModel):
    """Computed summary for a single position."""

    symbol: str
    name: str = ""
    status: Literal["open", "closed", "invalid"] = "open"
    remaining_quantity: int = 0
    avg_cost: float = 0.0
    cost_amount: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    latest_price: float | None = None
    price_source: Literal["intraday", "daily_fallback", "missing"] = "missing"
    market_value: float = 0.0
    position_weight: float = 0.0
    notes: str = ""


class RuleResult(BaseModel):
    """Result of evaluating a single rule."""

    rule_id: str
    script_id: str
    status: Literal["normal", "triggered", "unknown", "error"] = "normal"
    level: Literal["info", "warning", "danger"] = "info"
    message: str = ""


class PositionDetail(BaseModel):
    """Full position detail including summary and rule results."""

    position: Position
    summary: PositionSummary
    rule_results: list[RuleResult] = Field(default_factory=list)


class PositionListResponse(BaseModel):
    """Response for listing all positions."""

    positions: list[PositionSummary] = Field(default_factory=list)
    total_market_value: float = 0.0
