"""FastAPI routes for stock search."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..config import load_config
from .catalog import StockCatalog, StockEntry

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

_catalog: StockCatalog | None = None


def get_catalog() -> StockCatalog:
    global _catalog
    if _catalog is None:
        config = load_config()
        _catalog = StockCatalog(config.daily_data_dir)
    return _catalog


@router.get("/search", response_model=list[StockEntry])
def search_stocks(q: str = Query(default=""), limit: int = Query(default=10, le=50)) -> list[StockEntry]:
    return get_catalog().search(q, limit=limit)
