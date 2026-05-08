"""Tests for position calculator — pure logic, no I/O."""

from __future__ import annotations

from datetime import date, datetime

from app.positions.calculator import calculate_position, calculate_position_weights
from app.positions.models import Position, PositionSummary, Transaction


def _txn(side: str, date_str: str, qty: int, price: float, fee: float = 0, voided: bool = False) -> Transaction:
    return Transaction(
        id=f"txn-{side}-{date_str}",
        side=side,
        trade_date=date(date.fromisoformat(date_str).year, date.fromisoformat(date_str).month, date.fromisoformat(date_str).day),
        quantity=qty,
        price=price,
        fee=fee,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
        voided=voided,
    )


def _position(txns: list[Transaction], **kwargs) -> Position:
    return Position(id="pos-1", symbol="000001", name="Test", transactions=txns, **kwargs)


def test_single_buy():
    pos = _position([_txn("buy", "2026-05-08", 1000, 10.5, fee=5)])
    s = calculate_position(pos, latest_price=11.0, price_source="intraday")
    assert s.status == "open"
    assert s.remaining_quantity == 1000
    assert s.avg_cost == 10.505  # (10.5*1000 + 5) / 1000
    assert s.cost_amount == 10505.0
    assert s.realized_pnl == 0.0
    assert s.unrealized_pnl == round((11.0 - 10.505) * 1000, 2)


def test_buy_and_sell():
    pos = _position([
        _txn("buy", "2026-05-08", 1000, 10.0, fee=5),
        _txn("sell", "2026-05-10", 500, 11.0, fee=5),
    ])
    s = calculate_position(pos, latest_price=11.0)
    assert s.status == "open"
    assert s.remaining_quantity == 500
    # avg cost after buy: (10*1000+5)/1000 = 10.005
    # sell income: 11*500-5 = 5495
    # realized pnl: 5495 - 10.005*500 = 5495 - 5002.5 = 492.5
    assert s.realized_pnl == 492.5
    assert s.cost_amount == round(10.005 * 500, 2)


def test_full_sell_closes_position():
    pos = _position([
        _txn("buy", "2026-05-08", 1000, 10.0, fee=5),
        _txn("sell", "2026-05-10", 1000, 12.0, fee=5),
    ])
    s = calculate_position(pos)
    assert s.status == "closed"
    assert s.remaining_quantity == 0
    assert s.avg_cost == 0.0
    # realized: (12*1000-5) - 10.005*1000 = 11995 - 10005 = 1989.5 (with rounding)
    assert s.realized_pnl > 0


def test_sell_exceeds_remaining_is_invalid():
    pos = _position([
        _txn("buy", "2026-05-08", 500, 10.0),
        _txn("sell", "2026-05-10", 600, 11.0),
    ])
    s = calculate_position(pos)
    assert s.status == "invalid"


def test_voided_transaction_ignored():
    pos = _position([
        _txn("buy", "2026-05-08", 1000, 10.0),
        _txn("sell", "2026-05-10", 500, 11.0, voided=True),
    ])
    s = calculate_position(pos, latest_price=11.0)
    assert s.remaining_quantity == 1000
    assert s.realized_pnl == 0.0


def test_multiple_buys_weighted_average():
    pos = _position([
        _txn("buy", "2026-05-01", 1000, 10.0),
        _txn("buy", "2026-05-05", 1000, 12.0),
    ])
    s = calculate_position(pos, latest_price=11.0)
    assert s.remaining_quantity == 2000
    assert s.avg_cost == 11.0  # (10*1000 + 12*1000) / 2000


def test_no_transactions_is_closed():
    pos = _position([])
    s = calculate_position(pos)
    assert s.status == "closed"
    assert s.remaining_quantity == 0


def test_no_price_gives_missing_source():
    pos = _position([_txn("buy", "2026-05-08", 1000, 10.0)])
    s = calculate_position(pos)
    assert s.price_source == "missing"
    assert s.latest_price is None
    assert s.market_value == 0.0


def test_position_weights():
    summaries = [
        PositionSummary(symbol="A", status="open", remaining_quantity=100, market_value=1000.0),
        PositionSummary(symbol="B", status="open", remaining_quantity=200, market_value=3000.0),
        PositionSummary(symbol="C", status="closed", remaining_quantity=0, market_value=0.0),
    ]
    result = calculate_position_weights(summaries)
    assert result[0].position_weight == 0.25  # 1000/4000
    assert result[1].position_weight == 0.75  # 3000/4000
    assert result[2].position_weight == 0.0


def test_fee_increases_cost():
    pos_no_fee = _position([_txn("buy", "2026-05-08", 1000, 10.0, fee=0)])
    pos_with_fee = _position([_txn("buy", "2026-05-08", 1000, 10.0, fee=100)])
    s1 = calculate_position(pos_no_fee)
    s2 = calculate_position(pos_with_fee)
    assert s2.cost_amount > s1.cost_amount
    assert s2.avg_cost > s1.avg_cost
