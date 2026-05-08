import importlib.util
import sys
import types
from pathlib import Path

import pandas as pd


def _load_update_data_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "update_data.py"
    spec = importlib.util.spec_from_file_location("update_data_script", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_update_single_stock_preserves_existing_metadata(monkeypatch, tmp_path):
    module = _load_update_data_module()
    data_path = tmp_path / "000001.parquet"
    existing = pd.DataFrame(
        {
            "open": [10.0],
            "close": [10.5],
            "high": [10.8],
            "low": [9.9],
            "volume": [1000.0],
            "symbol": ["sz000001"],
            "name": ["平安银行"],
        },
        index=pd.DatetimeIndex([pd.Timestamp("2026-05-06")], name="date"),
    )
    existing.to_parquet(data_path)

    def fetch_akshare_symbol(symbol, start_date, end_date, adjust):
        assert symbol == "000001"
        assert start_date == "20260507"
        assert adjust == "qfq"
        return pd.DataFrame(
            {
                "date": [pd.Timestamp("2026-05-07")],
                "open": [11.0],
                "close": [11.1],
                "high": [11.3],
                "low": [10.9],
                "volume": [2000.0],
            }
        )

    akquant_module = types.ModuleType("akquant")
    utils_module = types.ModuleType("akquant.utils")
    utils_module.fetch_akshare_symbol = fetch_akshare_symbol
    akquant_module.utils = utils_module
    monkeypatch.setitem(sys.modules, "akquant", akquant_module)
    monkeypatch.setitem(sys.modules, "akquant.utils", utils_module)

    code, ok, message = module.update_single_stock(
        "000001", tmp_path, "20260507", None
    )

    assert (code, ok, message) == ("000001", True, "+1 rows")
    updated = pd.read_parquet(data_path)
    latest = updated.loc[pd.Timestamp("2026-05-07")]
    assert latest["symbol"] == "sz000001"
    assert latest["name"] == "平安银行"
    assert list(updated.columns) == list(existing.columns)


def test_update_single_stock_repairs_metadata_when_already_current(tmp_path):
    module = _load_update_data_module()
    data_path = tmp_path / "000001.parquet"
    existing = pd.DataFrame(
        {
            "open": [10.0, 11.0],
            "close": [10.5, 11.1],
            "high": [10.8, 11.3],
            "low": [9.9, 10.9],
            "volume": [1000.0, 2000.0],
            "symbol": ["sz000001", None],
            "name": ["平安银行", None],
        },
        index=pd.DatetimeIndex(
            [pd.Timestamp("2100-01-01"), pd.Timestamp("2100-01-02")], name="date"
        ),
    )
    existing.to_parquet(data_path)

    code, ok, message = module.update_single_stock("000001", tmp_path, "21000102", None)

    assert (code, ok, message) == ("000001", True, "metadata repaired")
    updated = pd.read_parquet(data_path)
    assert updated["symbol"].tolist() == ["sz000001", "sz000001"]
    assert updated["name"].tolist() == ["平安银行", "平安银行"]


def test_update_single_stock_creates_new_file(monkeypatch, tmp_path):
    module = _load_update_data_module()

    def fetch_akshare_symbol(symbol, start_date, end_date, adjust):
        assert symbol == "000002"
        assert start_date == "20100101"
        return pd.DataFrame(
            {
                "date": [pd.Timestamp("2026-05-07")],
                "open": [12.0],
                "close": [12.5],
                "high": [12.8],
                "low": [11.9],
                "volume": [3000.0],
            }
        )

    akquant_module = types.ModuleType("akquant")
    utils_module = types.ModuleType("akquant.utils")
    utils_module.fetch_akshare_symbol = fetch_akshare_symbol
    akquant_module.utils = utils_module
    monkeypatch.setitem(sys.modules, "akquant", akquant_module)
    monkeypatch.setitem(sys.modules, "akquant.utils", utils_module)

    code, ok, message = module.update_single_stock(
        "000002", tmp_path, "20260507", None
    )

    assert (code, ok, message) == ("000002", True, "+1 rows")
    created = pd.read_parquet(tmp_path / "000002.parquet")
    assert created.loc[pd.Timestamp("2026-05-07"), "symbol"] == "000002"
    assert created.loc[pd.Timestamp("2026-05-07"), "name"] == ""


def test_update_single_stock_fetches_requested_end_date(monkeypatch, tmp_path):
    module = _load_update_data_module()
    data_path = tmp_path / "000001.parquet"
    existing = pd.DataFrame(
        {
            "open": [11.0],
            "close": [11.1],
            "high": [11.3],
            "low": [10.9],
            "volume": [2000.0],
            "symbol": ["sz000001"],
            "name": ["平安银行"],
        },
        index=pd.DatetimeIndex([pd.Timestamp("2026-05-07")], name="date"),
    )
    existing.to_parquet(data_path)

    def fetch_akshare_symbol(symbol, start_date, end_date, adjust):
        assert symbol == "000001"
        assert start_date == "20260508"
        assert end_date == "20260508"
        return pd.DataFrame(
            {
                "date": [pd.Timestamp("2026-05-08")],
                "open": [11.2],
                "close": [11.4],
                "high": [11.5],
                "low": [11.1],
                "volume": [2500.0],
            }
        )

    akquant_module = types.ModuleType("akquant")
    utils_module = types.ModuleType("akquant.utils")
    utils_module.fetch_akshare_symbol = fetch_akshare_symbol
    akquant_module.utils = utils_module
    monkeypatch.setitem(sys.modules, "akquant", akquant_module)
    monkeypatch.setitem(sys.modules, "akquant.utils", utils_module)

    code, ok, message = module.update_single_stock(
        "000001", tmp_path, "20260508", None
    )

    assert (code, ok, message) == ("000001", True, "+1 rows")
    updated = pd.read_parquet(data_path)
    assert pd.Timestamp("2026-05-08") in updated.index
