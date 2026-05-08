"""Stock catalog with lazy-loaded symbol/name mapping from parquet files."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class StockEntry(BaseModel):
    symbol: str
    name: str
    market: str


class StockCatalog:
    """Lazy-loads and caches the stock symbol/name mapping from parquet files."""

    def __init__(self, daily_data_dir: str | Path) -> None:
        self._dir = Path(daily_data_dir)
        self._entries: list[StockEntry] | None = None

    def _load(self) -> list[StockEntry]:
        if self._entries is not None:
            return self._entries

        entries: list[StockEntry] = []
        for path in sorted(self._dir.glob("*.parquet")):
            symbol = path.stem
            try:
                df = pd.read_parquet(path, columns=["symbol", "name"])
                if df.empty:
                    continue
                raw_symbol = str(df["symbol"].iloc[-1])
                name = str(df["name"].iloc[-1])
                prefix = raw_symbol[:2].lower()
                market = {"sh": "SH", "sz": "SZ", "bj": "BJ"}.get(prefix, prefix.upper())
                entries.append(StockEntry(symbol=symbol, name=name, market=market))
            except Exception:
                logger.debug("Skipping %s: read error", path.name, exc_info=True)

        entries.sort(key=lambda e: e.symbol)
        logger.info("Loaded %d stocks from %s", len(entries), self._dir)
        self._entries = entries
        return entries

    def search(self, query: str, limit: int = 10) -> list[StockEntry]:
        if not query:
            return []

        entries = self._load()

        if query.isdigit():
            return [e for e in entries if e.symbol.startswith(query)][:limit]

        return [e for e in entries if query in e.name][:limit]
