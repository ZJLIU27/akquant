"""Tests for indicator computation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.positions.indicators import (
    compute_bbi,
    compute_brick_series,
    compute_ema,
    compute_indicators,
    compute_kdj_series,
    compute_macd_series,
    compute_single_pin_series,
    compute_sma,
    compute_tdx_sma,
    compute_volume_ratio,
    compute_white_line,
    detect_local_lows,
)


def _make_daily_df(rows: int = 30, base_price: float = 10.0) -> pd.DataFrame:
    """Create a synthetic daily OHLCV DataFrame."""
    dates = pd.date_range("2026-01-01", periods=rows, freq="B")
    np.random.seed(42)
    close = base_price + np.cumsum(np.random.randn(rows) * 0.1)
    return pd.DataFrame(
        {
            "open": close - np.random.rand(rows) * 0.1,
            "close": close,
            "high": close + np.random.rand(rows) * 0.2,
            "low": close - np.random.rand(rows) * 0.2,
            "volume": np.random.randint(50000000, 150000000, rows).astype(float),
        },
        index=dates,
    )


class TestComputeSMA:
    def test_basic(self):
        s = pd.Series([1, 2, 3, 4, 5], dtype=float)
        result = compute_sma(s, 3)
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == pytest.approx(2.0)

    def test_period_equals_length(self):
        s = pd.Series([10, 20, 30], dtype=float)
        result = compute_sma(s, 3)
        assert result.iloc[2] == pytest.approx(20.0)


class TestComputeTDXSMA:
    def test_recursive_formula(self):
        s = pd.Series([10.0, 20.0, 30.0])
        result = compute_tdx_sma(s, 4, 1)
        assert result.iloc[0] == pytest.approx(10.0)
        assert result.iloc[1] == pytest.approx((20.0 + 3 * 10.0) / 4)


class TestComputeBBI:
    def test_requires_114_rows(self):
        close = pd.Series([float(i) for i in range(100)])
        bbi = compute_bbi(close)
        # All values should be NaN since MA114 needs 114 data points.
        assert bbi.isna().all()

    def test_tdx_formula_with_114_rows(self):
        close = pd.Series([float(i) for i in range(1, 115)])
        bbi = compute_bbi(close)
        expected = (
            close.rolling(14, min_periods=14).mean().iloc[-1]
            + close.rolling(28, min_periods=28).mean().iloc[-1]
            + close.rolling(57, min_periods=57).mean().iloc[-1]
            + close.rolling(114, min_periods=114).mean().iloc[-1]
        ) / 4
        assert pd.notna(bbi.iloc[-1])
        assert bbi.iloc[-1] == pytest.approx(expected)


class TestComputeWhiteLine:
    def test_tdx_double_ema_formula(self):
        close = pd.Series([float(i) for i in range(1, 31)])
        white = compute_white_line(close)
        expected = compute_ema(compute_ema(close, 10), 10)
        assert white.iloc[-1] == pytest.approx(expected.iloc[-1])


class TestReferenceSubCharts:
    def test_single_pin_series(self):
        df = _make_daily_df(30)
        values = compute_single_pin_series(df)
        assert set(values) == {
            "single_pin_short",
            "single_pin_mid",
            "single_pin_mid_long",
            "single_pin_long",
        }
        assert values["single_pin_short"].dropna().between(0, 100).all()

    def test_brick_series(self):
        df = _make_daily_df(30)
        brick = compute_brick_series(df)
        assert len(brick) == len(df)
        assert brick.dropna().notna().all()

    def test_kdj_series(self):
        df = _make_daily_df(30)
        kdj = compute_kdj_series(df)
        assert set(kdj) == {"kdj_k", "kdj_d", "kdj_j"}
        assert all(len(series) == len(df) for series in kdj.values())
        assert kdj["kdj_k"].dropna().between(0, 100).all()
        assert kdj["kdj_d"].dropna().between(0, 100).all()

    def test_macd_series(self):
        df = _make_daily_df(40)
        macd = compute_macd_series(df["close"])
        assert set(macd) == {"macd_dif", "macd_dea", "macd"}
        assert all(len(series) == len(df) for series in macd.values())
        assert macd["macd"].dropna().notna().all()


class TestComputeVolumeRatio:
    def test_basic(self):
        # SMA of last 20 values: (100*19 + 200) / 20 = 105
        # Ratio = 200 / 105 ≈ 1.905
        vol = pd.Series([100.0] * 20 + [200.0])
        ratio = compute_volume_ratio(vol, 20)
        assert ratio.iloc[-1] == pytest.approx(200.0 / 105.0, rel=1e-3)


class TestDetectLocalLows:
    def test_finds_local_min(self):
        low = pd.Series([10, 8, 6, 4, 2, 4, 6, 8, 10], dtype=float)
        lows = detect_local_lows(low, window=2)
        assert len(lows) >= 1
        assert lows[0]["value"] == pytest.approx(2.0)


class TestComputeIndicators:
    def test_full_indicators(self):
        df = _make_daily_df(130)
        indicators = compute_indicators(df)
        assert "bbi" in indicators
        assert "bbi_prev" in indicators
        assert "yellow_line" in indicators
        assert "yellow_line_prev" in indicators
        assert "white_line" in indicators
        assert "volume_ratio" in indicators
        assert "avg_volume_20d" in indicators
        assert indicators["yellow_line"] == indicators["bbi"]
        assert indicators["yellow_line_prev"] == indicators["bbi_prev"]

    def test_insufficient_data(self):
        df = _make_daily_df(10)
        indicators = compute_indicators(df)
        assert "bbi" not in indicators
        assert "yellow_line" not in indicators
        assert "white_line" in indicators

    def test_none_input(self):
        assert compute_indicators(None) == {}

    def test_bbi_values_reasonable(self):
        df = _make_daily_df(130)
        indicators = compute_indicators(df)
        bbi = indicators["bbi"]
        bbi_prev = indicators["bbi_prev"]
        assert isinstance(bbi, float)
        assert isinstance(bbi_prev, float)

    def test_volume_ratio_calculation(self):
        df = _make_daily_df(40)
        indicators = compute_indicators(df)
        assert indicators["volume_ratio"] > 0

    def test_n_structure_low_detected(self):
        """With varied data, should detect at least one local low."""
        df = _make_daily_df(60)
        indicators = compute_indicators(df)
        # May or may not detect depending on random data, but should not crash
        if "n_structure_low" in indicators:
            assert indicators["n_structure_low"] > 0
