"""YAML-based position repository.

Reads/writes the positions file, handles UUID generation,
transaction edits, voids, and audit log persistence.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .models import (
    AuditLogEntry,
    Position,
    PositionFile,
    PositionRule,
    Transaction,
)


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now()


class PositionRepository:
    """Manages reading and writing the positions YAML file."""

    def __init__(self, positions_file: str | Path) -> None:
        self._path = Path(positions_file)

    def load(self) -> PositionFile:
        """Load positions from YAML file."""
        if not self._path.exists():
            return PositionFile()
        with open(self._path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return PositionFile.model_validate(data)

    def save(self, pf: PositionFile) -> None:
        """Save positions to YAML file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = pf.model_dump(mode="json")
        with open(self._path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def list_positions(self) -> list[Position]:
        """Return all positions."""
        return self.load().positions

    def get_position(self, symbol: str) -> Position | None:
        """Find a position by symbol."""
        for p in self.load().positions:
            if p.symbol == symbol:
                return p
        return None

    def _get_or_create_position(
        self, pf: PositionFile, symbol: str, name: str = ""
    ) -> tuple[PositionFile, Position]:
        """Find existing position or create a new one."""
        for p in pf.positions:
            if p.symbol == symbol:
                return pf, p
        pos = Position(id=_new_id(), symbol=symbol, name=name)
        pf.positions.append(pos)
        return pf, pos

    def add_transaction(
        self,
        symbol: str,
        side: str,
        trade_date: str,
        quantity: int,
        price: float,
        fee: float = 0.0,
        source: str = "manual",
        tags: list[str] | None = None,
        notes: str = "",
        name: str = "",
    ) -> Transaction:
        """Add a new transaction. Creates the position if needed."""
        pf = self.load()
        pf, pos = self._get_or_create_position(pf, symbol, name)
        now = _now()
        txn = Transaction(
            id=_new_id(),
            side=side,
            trade_date=trade_date,
            quantity=quantity,
            price=price,
            fee=fee,
            source=source,
            tags=tags or [],
            notes=notes,
            created_at=now,
            updated_at=now,
            revision=1,
            voided=False,
        )
        pos.transactions.append(txn)
        self.save(pf)
        return txn

    def edit_transaction(
        self,
        symbol: str,
        transaction_id: str,
        **updates: Any,
    ) -> Transaction | None:
        """Edit a transaction. Updates revision, updated_at, and writes audit log.

        Returns None if position/transaction not found.
        Raises ValueError if transaction is voided or no actual changes.
        """
        pf = self.load()
        pos = None
        for p in pf.positions:
            if p.symbol == symbol:
                pos = p
                break
        if pos is None:
            return None

        txn = None
        for t in pos.transactions:
            if t.id == transaction_id:
                txn = t
                break
        if txn is None:
            return None

        if txn.voided:
            raise ValueError("Cannot edit a voided transaction")

        editable_fields = {"price", "quantity", "fee", "trade_date", "side", "notes", "tags", "source"}

        # Only record fields that actually change
        before: dict[str, Any] = {}
        after: dict[str, Any] = {}
        for field in editable_fields:
            if field in updates:
                old_val = getattr(txn, field)
                new_val = updates[field]
                if old_val != new_val:
                    before[field] = old_val
                    after[field] = new_val

        if not before:
            # No actual changes — return as-is without bumping revision
            return txn

        # Apply updates
        for field, value in updates.items():
            if field in editable_fields:
                setattr(txn, field, value)

        txn.updated_at = _now()
        txn.revision += 1

        # Write audit log
        audit = AuditLogEntry(
            id=_new_id(),
            action="update_transaction",
            transaction_id=transaction_id,
            changed_at=_now(),
            before=before,
            after=after,
        )
        pos.audit_log.append(audit)

        self.save(pf)
        return txn

    def void_transaction(
        self,
        symbol: str,
        transaction_id: str,
        void_reason: str = "",
    ) -> Transaction | None:
        """Void a transaction (soft delete). Sets voided=True and writes audit log."""
        pf = self.load()
        pos = None
        for p in pf.positions:
            if p.symbol == symbol:
                pos = p
                break
        if pos is None:
            return None

        txn = None
        for t in pos.transactions:
            if t.id == transaction_id:
                txn = t
                break
        if txn is None:
            return None

        now = _now()
        txn.voided = True
        txn.voided_at = now
        txn.void_reason = void_reason

        audit = AuditLogEntry(
            id=_new_id(),
            action="void_transaction",
            transaction_id=transaction_id,
            changed_at=now,
            before={"voided": False},
            after={"voided": True, "void_reason": void_reason},
        )
        pos.audit_log.append(audit)

        self.save(pf)
        return txn

    def add_rule(
        self,
        symbol: str,
        category: str,
        script_id: str,
        params: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> PositionRule | None:
        """Add a rule to a position."""
        pf = self.load()
        pos = None
        for p in pf.positions:
            if p.symbol == symbol:
                pos = p
                break
        if pos is None:
            return None

        rule = PositionRule(
            id=_new_id(),
            category=category,
            script_id=script_id,
            enabled=enabled,
            params=params or {},
        )
        pos.rules.append(rule)
        self.save(pf)
        return rule

    def delete_rule(self, symbol: str, rule_id: str) -> bool:
        """Remove a rule from a position."""
        pf = self.load()
        pos = None
        for p in pf.positions:
            if p.symbol == symbol:
                pos = p
                break
        if pos is None:
            return False

        before = len(pos.rules)
        pos.rules = [r for r in pos.rules if r.id != rule_id]
        self.save(pf)
        return len(pos.rules) < before

    def validate(self) -> list[str]:
        """Validate positions file. Returns list of error messages."""
        errors: list[str] = []

        if not self._path.exists():
            return errors

        try:
            pf = self.load()
        except Exception as e:
            return [f"YAML parse error: {e}"]

        # Check duplicate symbols
        symbols = [p.symbol for p in pf.positions]
        seen: set[str] = set()
        for s in symbols:
            if s in seen:
                errors.append(f"Duplicate symbol: {s}")
            seen.add(s)

        # Check for sell exceeding remaining
        for pos in pf.positions:
            remaining = 0
            active = sorted(
                [t for t in pos.transactions if not t.voided],
                key=lambda t: (t.trade_date, t.created_at),
            )
            for txn in active:
                if txn.side == "buy":
                    remaining += txn.quantity
                elif txn.side == "sell":
                    remaining -= txn.quantity
                    if remaining < 0:
                        errors.append(
                            f"Position {pos.symbol}: sell exceeds remaining at "
                            f"transaction {txn.id[:8]}..."
                        )

        return errors

    def init_file(self) -> None:
        """Create an empty positions file if it doesn't exist."""
        if not self._path.exists():
            self.save(PositionFile())
