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


@router.get("/positions/{position_id}")
def get_position(position_id: str) -> PositionDetail:
    detail = get_service().get_position_detail(position_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Position not found: {position_id}")
    return detail


@router.get("/positions/{position_id}/intraday")
def get_intraday(position_id: str) -> dict[str, Any]:
    svc = get_service()
    detail = svc.get_position_detail(position_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Position not found: {position_id}")
    df = svc.get_intraday_df_for_position(position_id)
    if df is None:
        return {"symbol": detail.position.symbol, "data": None, "status": "missing"}
    return {
        "symbol": detail.position.symbol,
        "data": df.to_dict(orient="records"),
        "rows": len(df),
        "status": "ok",
    }


@router.get("/positions/{position_id}/daily")
def get_daily(position_id: str) -> dict[str, Any]:
    result = get_service().get_daily_chart_for_position(position_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Position not found: {position_id}")
    return result


@router.post("/positions/{position_ref}/transactions")
def add_transaction(position_ref: str, txn: dict[str, Any]) -> Transaction:
    svc = get_service()
    side = txn.get("side", "buy")
    if svc.repo.get_position(position_ref) is None:
        if side != "buy":
            raise HTTPException(
                status_code=400,
                detail="Sell requires an existing position id",
            )
        result = svc.add_buy(
            symbol=position_ref,
            trade_date=txn["trade_date"],
            quantity=txn["quantity"],
            price=txn["price"],
            fee=txn.get("fee", 0),
            name=txn.get("name", ""),
            notes=txn.get("notes", ""),
            tags=txn.get("tags"),
        )
    elif side in {"buy", "sell"}:
        result = svc.add_position_transaction(
            position_id=position_ref,
            side=side,
            trade_date=txn["trade_date"],
            quantity=txn["quantity"],
            price=txn["price"],
            fee=txn.get("fee", 0),
            notes=txn.get("notes", ""),
            tags=txn.get("tags"),
        )
        if result is None:
            raise HTTPException(status_code=400, detail="Transaction exceeds remaining quantity or position not found")
    else:
        raise HTTPException(status_code=400, detail=f"Invalid side: {side}")
    return result


@router.patch("/positions/{position_id}/transactions/{transaction_id}")
def edit_transaction(position_id: str, transaction_id: str, updates: TransactionUpdate) -> Transaction:
    payload = updates.model_dump(exclude_unset=True)
    try:
        result = get_service().edit_transaction(position_id, transaction_id, **payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if result is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return result


@router.post("/positions/{position_id}/transactions/{transaction_id}/void")
def void_transaction(position_id: str, transaction_id: str, body: VoidTransactionRequest) -> Transaction:
    result = get_service().void_transaction(position_id, transaction_id, body.reason)
    if result is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return result


@router.post("/positions/{position_id}/rules")
def add_rule(position_id: str, rule: dict[str, Any]) -> PositionRule:
    result = get_service().add_rule(
        position_id=position_id,
        category=rule["category"],
        script_id=rule["script_id"],
        params=rule.get("params"),
    )
    if result is None:
        raise HTTPException(status_code=400, detail="Invalid script_id or position not found")
    return result


@router.delete("/positions/{position_id}/rules/{rule_id}")
def delete_rule(position_id: str, rule_id: str) -> dict[str, bool]:
    ok = get_service().delete_rule(position_id, rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"ok": True}


@router.patch("/positions/{position_id}/strategy")
def bind_strategy(position_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    position = get_service().bind_strategy(
        position_id=position_id,
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
