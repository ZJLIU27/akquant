"""FastAPI routes for position management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..config import PlatformConfig, load_config
from .models import (
    PositionDetail,
    PositionListResponse,
    PositionRule,
    Transaction,
    TransactionUpdate,
    VoidTransactionRequest,
)
from .service import PositionService

router = APIRouter(prefix="/api", tags=["positions"])

_service: PositionService | None = None


def get_service() -> PositionService:
    global _service
    if _service is None:
        config = load_config()
        _service = PositionService(config)
        _service.init()
    return _service


def init_service(config: PlatformConfig) -> PositionService:
    global _service
    _service = PositionService(config)
    _service.init()
    return _service


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/positions", response_model=PositionListResponse)
def list_positions() -> PositionListResponse:
    return get_service().list_positions()


@router.get("/positions/{symbol}")
def get_position(symbol: str) -> PositionDetail:
    detail = get_service().get_position_detail(symbol)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Position not found: {symbol}")
    return detail


@router.get("/positions/{symbol}/intraday")
def get_intraday(symbol: str) -> dict[str, Any]:
    svc = get_service()
    df = svc.get_intraday_df(symbol)
    if df is None:
        return {"symbol": symbol, "data": None, "status": "missing"}
    return {
        "symbol": symbol,
        "data": df.to_dict(orient="records"),
        "rows": len(df),
        "status": "ok",
    }


@router.get("/positions/{symbol}/daily")
def get_daily(symbol: str) -> dict[str, Any]:
    return get_service().get_daily_chart(symbol)


@router.post("/positions/{symbol}/transactions")
def add_transaction(symbol: str, txn: dict[str, Any]) -> Transaction:
    svc = get_service()
    side = txn.get("side", "buy")
    if side == "buy":
        result = svc.add_buy(
            symbol=symbol,
            trade_date=txn["trade_date"],
            quantity=txn["quantity"],
            price=txn["price"],
            fee=txn.get("fee", 0),
            name=txn.get("name", ""),
            notes=txn.get("notes", ""),
            tags=txn.get("tags"),
        )
    elif side == "sell":
        result = svc.add_sell(
            symbol=symbol,
            trade_date=txn["trade_date"],
            quantity=txn["quantity"],
            price=txn["price"],
            fee=txn.get("fee", 0),
            notes=txn.get("notes", ""),
            tags=txn.get("tags"),
        )
        if result is None:
            raise HTTPException(status_code=400, detail="Sell exceeds remaining quantity or position not found")
    else:
        raise HTTPException(status_code=400, detail=f"Invalid side: {side}")
    return result


@router.patch("/positions/{symbol}/transactions/{transaction_id}")
def edit_transaction(symbol: str, transaction_id: str, updates: TransactionUpdate) -> Transaction:
    payload = updates.model_dump(exclude_unset=True)
    try:
        result = get_service().edit_transaction(symbol, transaction_id, **payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if result is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return result


@router.post("/positions/{symbol}/transactions/{transaction_id}/void")
def void_transaction(symbol: str, transaction_id: str, body: VoidTransactionRequest) -> Transaction:
    result = get_service().void_transaction(symbol, transaction_id, body.reason)
    if result is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return result


@router.post("/positions/{symbol}/rules")
def add_rule(symbol: str, rule: dict[str, Any]) -> PositionRule:
    result = get_service().add_rule(
        symbol=symbol,
        category=rule["category"],
        script_id=rule["script_id"],
        params=rule.get("params"),
    )
    if result is None:
        raise HTTPException(status_code=400, detail="Invalid script_id or position not found")
    return result


@router.delete("/positions/{symbol}/rules/{rule_id}")
def delete_rule(symbol: str, rule_id: str) -> dict[str, bool]:
    ok = get_service().delete_rule(symbol, rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"ok": True}


@router.patch("/positions/{symbol}/strategy")
def bind_strategy(symbol: str, payload: dict[str, Any]) -> dict[str, Any]:
    position = get_service().bind_strategy(
        symbol=symbol,
        strategy_id=payload.get("strategy_id", ""),
    )
    if position is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid strategy, stage, or position not found",
        )
    return position.model_dump(mode="json")


@router.get("/rules/available")
def list_available_rules() -> list[dict[str, Any]]:
    return get_service().get_available_rules()


@router.get("/strategies/available")
def list_available_strategies() -> list[dict[str, Any]]:
    return get_service().get_available_strategies()


@router.post("/positions/validate")
def validate_positions() -> dict[str, Any]:
    errors = get_service().validate()
    return {"valid": len(errors) == 0, "errors": errors}
