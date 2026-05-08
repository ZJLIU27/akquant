"""Tests for intraday cache."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from app.intraday.cache import IntradayCache, download_intraday


@pytest.fixture
def cache(tmp_intraday_dir: Path) -> IntradayCache:
    return IntradayCache(tmp_intraday_dir, ttl_seconds=300, retention_days=7)


def _save_intraday(cache: IntradayCache, symbol: str, df: pd.DataFrame | None = None) -> None:
    if df is None:
        df = pd.DataFrame({"close": [10.0, 10.5, 11.0], "volume": [100, 200, 300]})
    cache.save_intraday(symbol, df)


def _write_cached_day(
    intraday_dir: Path,
    symbol: str,
    trade_date: str,
    df: pd.DataFrame | None = None,
    updated_at: datetime | None = None,
) -> None:
    if df is None:
        df = pd.DataFrame({"close": [10.0, 10.5, 11.0], "volume": [100, 200, 300]})
    symbol_dir = intraday_dir / symbol
    symbol_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(symbol_dir / f"{trade_date}.parquet")
    meta = {
        "symbol": symbol,
        "trade_date": trade_date,
        "updated_at": (updated_at or datetime.now(tz=timezone(timedelta(hours=8)))).isoformat(),
        "source": "test",
        "rows": len(df),
        "status": "success",
    }
    (symbol_dir / f"{trade_date}.meta.json").write_text(json.dumps(meta), encoding="utf-8")


def test_cache_not_valid_when_missing(cache: IntradayCache):
    assert not cache.is_cache_valid("000001")


def test_cache_valid_after_save(cache: IntradayCache):
    _save_intraday(cache, "000001")
    assert cache.is_cache_valid("000001")


def test_cache_invalid_after_ttl(tmp_intraday_dir: Path):
    cache = IntradayCache(tmp_intraday_dir, ttl_seconds=0)
    _save_intraday(cache, "000001")
    assert not cache.is_cache_valid("000001")


def test_get_intraday_df(cache: IntradayCache):
    df = pd.DataFrame({"close": [10.0, 10.5]})
    _save_intraday(cache, "000001", df)
    result = cache.get_intraday_df("000001")
    assert result is not None
    assert len(result) == 2


def test_get_intraday_df_uses_latest_cached_trade_day(tmp_intraday_dir: Path):
    cache = IntradayCache(tmp_intraday_dir, ttl_seconds=300, retention_days=7)
    old_date = (datetime.now(tz=timezone(timedelta(hours=8))) - timedelta(days=2)).strftime("%Y-%m-%d")
    newer_date = (datetime.now(tz=timezone(timedelta(hours=8))) - timedelta(days=1)).strftime("%Y-%m-%d")
    _write_cached_day(tmp_intraday_dir, "000001", old_date, pd.DataFrame({"close": [8.0]}))
    _write_cached_day(tmp_intraday_dir, "000001", newer_date, pd.DataFrame({"close": [9.0, 9.5]}))

    result = cache.get_intraday_df("000001")

    assert result is not None
    assert result["close"].tolist() == [9.0, 9.5]


def test_save_intraday_uses_dataframe_trade_date(cache: IntradayCache, tmp_intraday_dir: Path):
    df = pd.DataFrame({"close": [10.0]})
    df.attrs["trade_date"] = "2026-05-08"

    cache.save_intraday("000001", df)

    assert (tmp_intraday_dir / "000001" / "2026-05-08.parquet").exists()
    meta = json.loads((tmp_intraday_dir / "000001" / "2026-05-08.meta.json").read_text())
    assert meta["trade_date"] == "2026-05-08"


def test_get_intraday_df_missing(cache: IntradayCache):
    assert cache.get_intraday_df("999999") is None


def test_get_latest_price(cache: IntradayCache):
    df = pd.DataFrame({"close": [10.0, 10.5, 11.0]})
    _save_intraday(cache, "000001", df)
    price, source = cache.get_latest_price("000001")
    assert price == 11.0
    assert source == "intraday"


def test_get_latest_price_from_akshare_intraday_columns(cache: IntradayCache):
    df = pd.DataFrame(
        {
            "时间": ["14:56:53", "15:00:00"],
            "成交价": [6.12, 6.11],
            "手数": [1, 4769],
            "买卖盘性质": ["买盘", "卖盘"],
        }
    )
    _save_intraday(cache, "601002", df)
    price, source = cache.get_latest_price("601002")
    assert price == 6.11
    assert source == "intraday"


def test_download_intraday_falls_back_to_latest_minute_day(monkeypatch: pytest.MonkeyPatch):
    minute_df = pd.DataFrame(
        {
            "时间": ["2026-05-07 14:59:00", "2026-05-08 09:30:00", "2026-05-08 15:00:00"],
            "开盘": [4.98, 5.0, 5.05],
            "收盘": [4.98, 5.0, 5.05],
            "最高": [4.98, 5.0, 5.05],
            "最低": [4.98, 5.0, 5.05],
            "成交量": [10, 20, 30],
            "成交额": [49.8, 100.0, 151.5],
            "均价": [4.98, 5.0, 5.02],
        }
    )
    fake_akshare = SimpleNamespace(
        stock_intraday_em=lambda symbol: pd.DataFrame(),
        stock_zh_a_hist_min_em=lambda symbol, period, adjust: minute_df,
        stock_zh_a_minute=lambda symbol, period, adjust: pd.DataFrame(),
    )
    monkeypatch.setitem(sys.modules, "akshare", fake_akshare)

    result = download_intraday("300145")

    assert result is not None
    assert result["time"].tolist() == ["2026-05-08 09:30:00", "2026-05-08 15:00:00"]
    assert result["close"].tolist() == [5.0, 5.05]
    assert result.attrs["trade_date"] == "2026-05-08"


def test_download_intraday_falls_back_to_market_prefixed_minute(monkeypatch: pytest.MonkeyPatch):
    minute_df = pd.DataFrame(
        {
            "day": ["2026-05-07 14:57:00", "2026-05-08 14:57:00", "2026-05-08 15:00:00"],
            "open": [4.98, 5.04, 5.05],
            "high": [4.98, 5.05, 5.05],
            "low": [4.98, 5.04, 5.05],
            "close": [4.98, 5.05, 5.05],
            "volume": [100, 200, 300],
        }
    )

    def get_minute(symbol: str, period: str, adjust: str) -> pd.DataFrame:
        assert symbol == "sz300145"
        return minute_df

    fake_akshare = SimpleNamespace(
        stock_intraday_em=lambda symbol: pd.DataFrame(),
        stock_zh_a_hist_min_em=lambda symbol, period, adjust: (_ for _ in ()).throw(RuntimeError("remote closed")),
        stock_zh_a_minute=get_minute,
    )
    monkeypatch.setitem(sys.modules, "akshare", fake_akshare)

    result = download_intraday("300145")

    assert result is not None
    assert result["time"].tolist() == ["2026-05-08 14:57:00", "2026-05-08 15:00:00"]
    assert result["close"].tolist() == [5.05, 5.05]
    assert result.attrs["trade_date"] == "2026-05-08"


def test_get_latest_price_missing(cache: IntradayCache):
    price, source = cache.get_latest_price("999999")
    assert price is None
    assert source == "missing"


def test_daily_fallback(cache: IntradayCache, tmp_daily_dir: Path):
    df = pd.DataFrame({"close": [9.0, 9.5, 10.0]})
    df.to_parquet(tmp_daily_dir / "000001.parquet")
    price, source = cache.get_daily_fallback_price("000001", tmp_daily_dir)
    assert price == 10.0
    assert source == "daily_fallback"


def test_resolve_price_prefers_intraday(cache: IntradayCache, tmp_daily_dir: Path):
    # Set up daily fallback
    pd.DataFrame({"close": [9.0]}).to_parquet(tmp_daily_dir / "000001.parquet")
    # Set up intraday
    _save_intraday(cache, "000001", pd.DataFrame({"close": [11.0]}))
    price, source = cache.resolve_price("000001", tmp_daily_dir)
    assert price == 11.0
    assert source == "intraday"


def test_resolve_price_falls_back_to_daily(cache: IntradayCache, tmp_daily_dir: Path):
    pd.DataFrame({"close": [9.0]}).to_parquet(tmp_daily_dir / "000001.parquet")
    price, source = cache.resolve_price("000001", tmp_daily_dir)
    assert price == 9.0
    assert source == "daily_fallback"


def test_resolve_price_does_not_treat_volume_as_price(cache: IntradayCache, tmp_daily_dir: Path):
    _save_intraday(
        cache,
        "000001",
        pd.DataFrame({"time": ["09:30:00", "09:31:00"], "volume": [100, 200]}),
    )
    pd.DataFrame({"close": [9.0]}).to_parquet(tmp_daily_dir / "000001.parquet")
    price, source = cache.resolve_price("000001", tmp_daily_dir)
    assert price == 9.0
    assert source == "daily_fallback"


def test_cleanup_old_cache(cache: IntradayCache, tmp_intraday_dir: Path):
    # Create old cache files
    old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    symbol_dir = tmp_intraday_dir / "000001"
    symbol_dir.mkdir(parents=True, exist_ok=True)
    pq = symbol_dir / f"{old_date}.parquet"
    meta = symbol_dir / f"{old_date}.meta.json"
    pd.DataFrame({"close": [10.0]}).to_parquet(pq)
    meta.write_text(json.dumps({"status": "success"}))
    assert pq.exists()

    deleted = cache.cleanup_old_cache()
    assert len(deleted) > 0
    assert not pq.exists()


def test_meta_json_written(cache: IntradayCache, tmp_intraday_dir: Path):
    _save_intraday(cache, "000001")
    today = datetime.now(tz=timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    meta_path = tmp_intraday_dir / "000001" / f"{today}.meta.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text())
    assert meta["symbol"] == "000001"
    assert meta["status"] == "success"
    assert meta["rows"] == 3
