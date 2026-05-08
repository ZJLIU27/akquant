"""Intraday data cache — download, TTL, refresh, cleanup.

Manages per-symbol intraday parquet files and meta.json sidecars.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd


class IntradayCache:
    """Manages intraday parquet files and metadata."""

    def __init__(
        self,
        intraday_dir: str | Path,
        ttl_seconds: int = 300,
        retention_days: int = 7,
        tz: str = "Asia/Shanghai",
    ) -> None:
        self._dir = Path(intraday_dir)
        self._ttl = ttl_seconds
        self._retention_days = retention_days
        self._tz = tz

    def _symbol_dir(self, symbol: str) -> Path:
        return self._dir / symbol

    def _parquet_path(self, symbol: str, trade_date: str | None = None) -> Path:
        date_str = trade_date or self._today_str()
        return self._symbol_dir(symbol) / f"{date_str}.parquet"

    def _meta_path(self, symbol: str, trade_date: str | None = None) -> Path:
        date_str = trade_date or self._today_str()
        return self._symbol_dir(symbol) / f"{date_str}.meta.json"

    def _today_str(self) -> str:
        return datetime.now(tz=timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

    def is_cache_valid(self, symbol: str) -> bool:
        """Check if today's intraday cache exists and is within TTL."""
        meta_path = self._meta_path(symbol)
        if not meta_path.exists():
            return False

        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            updated_at = datetime.fromisoformat(meta.get("updated_at", ""))
            now = datetime.now(tz=updated_at.tzinfo)
            elapsed = (now - updated_at).total_seconds()
            return elapsed < self._ttl and meta.get("status") == "success"
        except Exception:
            return False

    def get_intraday_df(self, symbol: str) -> pd.DataFrame | None:
        """Read today's intraday DataFrame from cache."""
        pq_path = self._parquet_path(symbol)
        if not pq_path.exists():
            return None
        try:
            return pd.read_parquet(pq_path)
        except Exception:
            return None

    def get_latest_price(self, symbol: str) -> tuple[float | None, str]:
        """Get latest price from intraday cache.

        Returns:
            (price, source) tuple. Source is "intraday", "daily_fallback", or "missing".
        """
        df = self.get_intraday_df(symbol)
        if df is not None and not df.empty:
            price_col = self._find_price_column(df)
            if price_col:
                return float(df[price_col].iloc[-1]), "intraday"
        return None, "missing"

    def get_daily_fallback_price(self, symbol: str, daily_dir: str | Path) -> tuple[float | None, str]:
        """Fallback to daily data for latest close price."""
        pq = Path(daily_dir) / f"{symbol}.parquet"
        if not pq.exists():
            return None, "missing"
        try:
            df = pd.read_parquet(pq)
            if "close" in df.columns and not df.empty:
                return float(df["close"].iloc[-1]), "daily_fallback"
        except Exception:
            pass
        return None, "missing"

    def resolve_price(
        self, symbol: str, daily_dir: str | Path
    ) -> tuple[float | None, str]:
        """Resolve latest price: intraday first, then daily fallback."""
        price, source = self.get_latest_price(symbol)
        if price is not None:
            return price, source
        return self.get_daily_fallback_price(symbol, daily_dir)

    def _find_price_column(self, df: pd.DataFrame) -> str | None:
        """Find the price column in a DataFrame."""
        for col in [
            "close",
            "price",
            "成交价",
            "最新价",
            "现价",
            "当前价",
            "收盘",
        ]:
            if col in df.columns:
                return col
        return None

    def save_intraday(
        self,
        symbol: str,
        df: pd.DataFrame,
        source: str = "akshare",
    ) -> None:
        """Save intraday DataFrame and meta.json."""
        pq_path = self._parquet_path(symbol)
        meta_path = self._meta_path(symbol)

        pq_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(pq_path, compression="snappy")

        now_str = datetime.now(tz=timezone(timedelta(hours=8))).isoformat()
        meta = {
            "symbol": symbol,
            "trade_date": self._today_str(),
            "updated_at": now_str,
            "source": source,
            "rows": len(df),
            "status": "success",
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    def cleanup_old_cache(self) -> list[str]:
        """Delete intraday cache older than retention_days.

        Returns:
            List of deleted date strings.
        """
        if not self._dir.exists():
            return []

        cutoff = datetime.now(tz=timezone(timedelta(hours=8))) - timedelta(
            days=self._retention_days
        )
        cutoff_str = cutoff.strftime("%Y-%m-%d")
        deleted: list[str] = []

        for symbol_dir in self._dir.iterdir():
            if not symbol_dir.is_dir():
                continue
            for pq_file in symbol_dir.glob("*.parquet"):
                date_str = pq_file.stem
                if date_str < cutoff_str:
                    pq_file.unlink(missing_ok=True)
                    meta_file = pq_file.with_suffix(".meta.json")
                    meta_file.unlink(missing_ok=True)
                    deleted.append(f"{symbol_dir.name}/{date_str}")

        return deleted


def download_intraday(symbol: str) -> pd.DataFrame | None:
    """Download today's intraday data for a symbol via akshare.

    Returns DataFrame or None on failure.
    """
    try:
        import akshare as ak
    except ImportError:
        return None

    try:
        df = ak.stock_intraday_em(symbol=symbol)
        if df is not None and not df.empty:
            return df
    except Exception:
        pass
    return None
