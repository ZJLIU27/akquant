"""Tests for the stock search catalog."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.stocks.catalog import StockCatalog


def _write_parquet(directory: Path, filename: str, symbol: str, name: str) -> None:
    df = pd.DataFrame(
        {"symbol": [symbol], "name": [name], "open": [10.0], "close": [10.5]},
        index=pd.DatetimeIndex(["2025-01-01"], name="date"),
    )
    df.to_parquet(directory / filename)


@pytest.fixture
def stock_dir(tmp_path: Path) -> Path:
    d = tmp_path / "stocks"
    d.mkdir()
    _write_parquet(d, "601002.parquet", "sh601002", "晋亿实业")
    _write_parquet(d, "600193.parquet", "sh600193", "创兴股份")
    _write_parquet(d, "002168.parquet", "sz002168", "惠程科技")
    _write_parquet(d, "688121.parquet", "sh688121", "卓然股份")
    _write_parquet(d, "000627.parquet", "sz000627", "天茂集团")
    return d


def test_search_empty_query(stock_dir: Path) -> None:
    catalog = StockCatalog(stock_dir)
    assert catalog.search("") == []


def test_search_by_symbol_prefix(stock_dir: Path) -> None:
    catalog = StockCatalog(stock_dir)
    results = catalog.search("601")
    assert len(results) == 1
    assert results[0].symbol == "601002"
    assert results[0].name == "晋亿实业"
    assert results[0].market == "SH"


def test_search_by_full_symbol(stock_dir: Path) -> None:
    catalog = StockCatalog(stock_dir)
    results = catalog.search("601002")
    assert len(results) == 1
    assert results[0].symbol == "601002"


def test_search_by_name(stock_dir: Path) -> None:
    catalog = StockCatalog(stock_dir)
    results = catalog.search("晋亿")
    assert len(results) == 1
    assert results[0].symbol == "601002"


def test_search_name_multiple(stock_dir: Path) -> None:
    catalog = StockCatalog(stock_dir)
    results = catalog.search("股份")
    assert len(results) >= 2


def test_search_limit(stock_dir: Path) -> None:
    catalog = StockCatalog(stock_dir)
    all_results = catalog.search("股份", limit=1)
    assert len(all_results) <= 1


def test_search_no_match(stock_dir: Path) -> None:
    catalog = StockCatalog(stock_dir)
    assert catalog.search("999999") == []


def test_search_no_name_match(stock_dir: Path) -> None:
    catalog = StockCatalog(stock_dir)
    assert catalog.search("不存在的公司") == []


def test_lazy_load(stock_dir: Path) -> None:
    catalog = StockCatalog(stock_dir)
    assert catalog._entries is None
    catalog.search("601")
    assert catalog._entries is not None
