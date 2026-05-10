"""Position calculator — pure logic, no I/O.

Computes moving weighted average cost, realized/unrealized PnL,
position status, and position weights from a list of transactions.
"""

from __future__ import annotations

from .models import Position, PositionSummary, Transaction


def calculate_position(
    position: Position,
    latest_price: float | None = None,
    price_source: str = "missing",
) -> PositionSummary:
    """Calculate position summary from transactions.

    Uses moving weighted average cost. Voided transactions are ignored.
    Sell exceeding remaining quantity marks position as invalid.

    Args:
        position: Position with transactions.
        latest_price: Latest market price, or None if missing.
        price_source: Source of the price ("intraday", "daily_fallback", "missing").

    Returns:
        Computed PositionSummary.
    """
    # Filter out voided transactions, sort by trade_date (stable for same date)
    active_txns = sorted(
        [t for t in position.transactions if not t.voided],
        key=lambda t: (t.trade_date, t.created_at),
    )

    remaining_quantity = 0
    cost_amount = 0.0
    realized_pnl = 0.0
    status = "closed"

    for txn in active_txns:
        if txn.side == "buy":
            cost_amount += txn.price * txn.quantity + txn.fee
            remaining_quantity += txn.quantity
        elif txn.side == "sell":
            if txn.quantity > remaining_quantity:
                return PositionSummary(
                    id=position.id,
                    symbol=position.symbol,
                    name=position.name,
                    strategy_id=position.strategy_id,
                    strategy_stage=position.strategy_stage,
                    strategy_tags=position.strategy_tags,
                    status="invalid",
                    notes=position.notes,
                )
            if remaining_quantity > 0:
                avg_cost = cost_amount / remaining_quantity
            else:
                avg_cost = 0.0
            sell_income = txn.price * txn.quantity - txn.fee
            realized_pnl += sell_income - avg_cost * txn.quantity
            # Average cost stays the same per spec: "卖出后剩余持仓的平均成本保持为卖出前移动平均成本"
            cost_amount -= avg_cost * txn.quantity
            remaining_quantity -= txn.quantity

    if remaining_quantity > 0:
        status = "open"
    elif remaining_quantity == 0:
        status = "closed"
    else:
        status = "invalid"

    avg_cost = cost_amount / remaining_quantity if remaining_quantity > 0 else 0.0
    market_value = latest_price * remaining_quantity if latest_price and remaining_quantity > 0 else 0.0
    unrealized_pnl = (latest_price - avg_cost) * remaining_quantity if latest_price and remaining_quantity > 0 else 0.0

    return PositionSummary(
        id=position.id,
        symbol=position.symbol,
        name=position.name,
        strategy_id=position.strategy_id,
        strategy_stage=position.strategy_stage,
        strategy_tags=position.strategy_tags,
        status=status,
        remaining_quantity=remaining_quantity,
        avg_cost=round(avg_cost, 6),
        cost_amount=round(cost_amount, 2),
        realized_pnl=round(realized_pnl, 2),
        unrealized_pnl=round(unrealized_pnl, 2),
        latest_price=latest_price,
        price_source=price_source,
        market_value=round(market_value, 2),
        notes=position.notes,
    )


def calculate_position_weights(summaries: list[PositionSummary]) -> list[PositionSummary]:
    """Set position_weight for open positions based on market value.

    Weight = position_market_value / sum(open_position_market_value).
    Closed/invalid positions get weight 0.
    """
    open_mv = sum(s.market_value for s in summaries if s.status == "open" and s.market_value > 0)
    for s in summaries:
        if s.status == "open" and open_mv > 0:
            s.position_weight = round(s.market_value / open_mv, 6)
        else:
            s.position_weight = 0.0
    return summaries
