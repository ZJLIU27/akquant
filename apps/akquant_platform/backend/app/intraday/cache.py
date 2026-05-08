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

    def _latest_cached_trade_date(self, symbol: str) -> str | None:
        """Return the newest cached trade date still inside the retention window."""
        symbol_dir = self._symbol_dir(symbol)
        if not symbol_dir.exists():
            return None

        cutoff = datetime.now(tz=timezone(timedelta(hours=8))) - timedelta(
            days=self._retention_days
        )
        cutoff_str = cutoff.strftime("%Y-%m-%d")
        dates = sorted(
            (
                pq_file.stem
                for pq_file in symbol_dir.glob("*.parquet")
                if pq_file.stem >= cutoff_str
            ),
            reverse=True,
        )
        return dates[0] if dates else None

    def _today_str(self) -> str:
        return datetime.now(tz=timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

    def _effective_trade_date(self) -> str:
        """Return today's date, or yesterday's if before 9am CST (market not yet open)."""
        now = datetime.now(tz=timezone(timedelta(hours=8)))
        if now.hour < 9:
            return (now - timedelta(days=1)).strftime("%Y-%m-%d")
        return now.strftime("%Y-%m-%d")

    def is_cache_valid(self, symbol: str) -> bool:
        """Check if today's (or yesterday's before 9am) intraday cache exists and is within TTL."""
        meta_path = self._meta_path(symbol)
        if not meta_path.exists():
            meta_path = self._meta_path(symbol, trade_date=self._effective_trade_date())
        if not meta_path.exists():
            latest_trade_date = self._latest_cached_trade_date(symbol)
            if latest_trade_date is not None:
                meta_path = self._meta_path(symbol, trade_date=latest_trade_date)
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
        """Read today's (or yesterday's if before 9am) intraday DataFrame from cache."""
        pq_path = self._parquet_path(symbol)
        if not pq_path.exists():
            pq_path = self._parquet_path(symbol, trade_date=self._effective_trade_date())
        if not pq_path.exists():
            latest_trade_date = self._latest_cached_trade_date(symbol)
            if latest_trade_date is not None:
                pq_path = self._parquet_path(symbol, trade_date=latest_trade_date)
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
        trade_date: str | None = None,
    ) -> None:
        """Save intraday DataFrame and meta.json."""
        cache_trade_date = trade_date or df.attrs.get("trade_date") or self._today_str()
        pq_path = self._parquet_path(symbol, trade_date=cache_trade_date)
        meta_path = self._meta_path(symbol, trade_date=cache_trade_date)

        pq_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(pq_path, compression="snappy")

        now_str = datetime.now(tz=timezone(timedelta(hours=8))).isoformat()
        meta = {
            "symbol": symbol,
            "trade_date": cache_trade_date,
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

    for attempt in range(2):
        try:
            df = ak.stock_intraday_em(symbol=symbol)
            if df is not None and not df.empty:
                return df
        except Exception:
            if attempt == 0:
                time.sleep(0.5)

    for attempt in range(3):
        try:
            df = ak.stock_zh_a_hist_min_em(symbol=symbol, period="1", adjust="")
            if df is not None and not df.empty:
                df = _normalize_minute_intraday(df)
                time_col = _find_time_column(df)
                if time_col is not None:
                    parsed = pd.to_datetime(df[time_col], errors="coerce")
                    latest_date = parsed.dropna().dt.date.max()
                    if latest_date is not None:
                        df = df.loc[parsed.dt.date == latest_date].copy()
                        df.attrs["trade_date"] = latest_date.strftime("%Y-%m-%d")
                if not df.empty:
                    return df
        except Exception:
            if attempt < 2:
                time.sleep(0.5)

    for attempt in range(3):
        try:
            df = ak.stock_zh_a_minute(symbol=_market_symbol(symbol), period="1", adjust="")
            if df is not None and not df.empty:
                df = df.rename(columns={"day": "time"}).copy()
                time_col = _find_time_column(df)
                if time_col is not None:
                    parsed = pd.to_datetime(df[time_col], errors="coerce")
                    latest_date = parsed.dropna().dt.date.max()
                    if latest_date is not None:
                        df = df.loc[parsed.dt.date == latest_date].copy()
                        df.attrs["trade_date"] = latest_date.strftime("%Y-%m-%d")
                if not df.empty:
                    return df
        except Exception:
            if attempt < 2:
                time.sleep(0.5)
    return None


def _market_symbol(symbol: str) -> str:
    """Return a market-prefixed A-share symbol for minute endpoints."""
    return f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"


def _normalize_minute_intraday(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize AkShare minute-bar columns into stable chart columns."""
    normalized = df.copy()
    if len(normalized.columns) >= 8:
        rename_map = {
            normalized.columns[0]: "time",
            normalized.columns[1]: "open",
            normalized.columns[2]: "close",
            normalized.columns[3]: "high",
            normalized.columns[4]: "low",
            normalized.columns[5]: "volume",
            normalized.columns[6]: "amount",
            normalized.columns[7]: "avg_price",
        }
        normalized = normalized.rename(columns=rename_map)
    return normalized


def _find_time_column(df: pd.DataFrame) -> str | None:
    """Find the timestamp column in an intraday DataFrame."""
    for col in ["time", "datetime", "date", "时间"]:
        if col in df.columns:
            return col
    for col in df.columns:
        parsed = pd.to_datetime(df[col], errors="coerce")
        if parsed.notna().any():
            return str(col)
    return None
