"""Tests for intraday cache."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from app.intraday.cache import IntradayCache


@pytest.fixture
def cache(tmp_intraday_dir: Path) -> IntradayCache:
    return IntradayCache(tmp_intraday_dir, ttl_seconds=300, retention_days=7)


def _save_intraday(cache: IntradayCache, symbol: str, df: pd.DataFrame | None = None) -> None:
    if df is None:
        df = pd.DataFrame({"close": [10.0, 10.5, 11.0], "volume": [100, 200, 300]})
    cache.save_intraday(symbol, df)


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
