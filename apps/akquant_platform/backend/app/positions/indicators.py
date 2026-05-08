"""Technical indicator computation for position rules."""

from __future__ import annotations

from typing import Any

import pandas as pd


def compute_sma(series: pd.Series, period: int) -> pd.Series:
    """Simple moving average."""
    return series.rolling(window=period, min_periods=period).mean()


def compute_tdx_sma(series: pd.Series, period: int, weight: int = 1) -> pd.Series:
    """TongDaXin SMA(X,N,M): Y=(M*X+(N-M)*Y')/N."""
    values: list[float | None] = []
    prev: float | None = None
    for value in series.astype(float):
        if pd.isna(value):
            values.append(None)
            continue
        if prev is None:
            prev = float(value)
        else:
            prev = (weight * float(value) + (period - weight) * prev) / period
        values.append(prev)
    return pd.Series(values, index=series.index, dtype="float64")


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential moving average, matching TongDaXin EMA style."""
    return series.ewm(span=period, adjust=False).mean()


def compute_bbi(close: pd.Series) -> pd.Series:
    """Z multi-empty line = (MA14 + MA28 + MA57 + MA114) / 4."""
    ma14 = compute_sma(close, 14)
    ma28 = compute_sma(close, 28)
    ma57 = compute_sma(close, 57)
    ma114 = compute_sma(close, 114)
    return (ma14 + ma28 + ma57 + ma114) / 4


def compute_white_line(close: pd.Series) -> pd.Series:
    """Z short-term trend line = EMA(EMA(C, 10), 10)."""
    return compute_ema(compute_ema(close, 10), 10)


def compute_single_pin_series(daily_df: pd.DataFrame) -> dict[str, pd.Series]:
    """Single-pin-under-20 oscillator series from the reference formula."""
    close = daily_df["close"].astype(float)
    low = daily_df["low"].astype(float)
    result: dict[str, pd.Series] = {}
    periods = {
        "single_pin_short": 3,
        "single_pin_mid": 10,
        "single_pin_mid_long": 20,
        "single_pin_long": 21,
    }
    for key, period in periods.items():
        lowest = low.rolling(window=period, min_periods=period).min()
        highest_close = close.rolling(window=period, min_periods=period).max()
        denom = highest_close - lowest
        result[key] = 100 * (close - lowest) / denom.where(denom != 0)
    return result


def compute_brick_series(daily_df: pd.DataFrame) -> pd.Series:
    """Raw VAR6A brick line from the reference TongDaXin formula."""
    close = daily_df["close"].astype(float)
    high = daily_df["high"].astype(float)
    low = daily_df["low"].astype(float)
    highest = high.rolling(window=4, min_periods=4).max()
    lowest = low.rolling(window=4, min_periods=4).min()
    denom = (highest - lowest).where((highest - lowest) != 0)

    var1a = (highest - close) / denom * 100 - 90
    var2a = compute_tdx_sma(var1a, 4, 1) + 100
    var3a = (close - lowest) / denom * 100
    var4a = compute_tdx_sma(var3a, 6, 1)
    var5a = compute_tdx_sma(var4a, 6, 1) + 100
    return var5a - var2a


def compute_volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """Volume ratio = current volume / average volume over period."""
    avg = compute_sma(volume, period)
    return volume / avg


def detect_local_lows(low: pd.Series, window: int = 5) -> list[dict[str, Any]]:
    """Detect local minimum points in low prices.

    A local low is a point where low[i] is the minimum in
    [i-window, i+window].
    """
    results = []
    n = len(low)
    for i in range(window, n - window):
        segment = low.iloc[i - window : i + window + 1]
        if low.iloc[i] == segment.min():
            results.append(
                {"index": i, "date": low.index[i], "value": float(low.iloc[i])}
            )
    return results


def compute_indicators(daily_df: pd.DataFrame | None) -> dict[str, Any]:
    """Compute all indicators from daily OHLCV DataFrame.

    Args:
        daily_df: DataFrame with open/close/high/low/volume columns,
                  sorted by date ascending. May be None.

    Returns:
        Dict with computed indicator values. Missing indicators are
        simply omitted from the dict.
    """
    if daily_df is None or daily_df.empty:
        return {}

    indicators: dict[str, Any] = {}
    close = daily_df["close"]
    low = daily_df["low"]
    volume = daily_df["volume"]

    # Yellow line / BBI / Z multi-empty line:
    # (MA(C,14) + MA(C,28) + MA(C,57) + MA(C,114)) / 4.
    bbi = compute_bbi(close)
    if pd.notna(bbi.iloc[-1]):
        indicators["bbi"] = round(float(bbi.iloc[-1]), 4)
        indicators["yellow_line"] = indicators["bbi"]
    if len(bbi) >= 2 and pd.notna(bbi.iloc[-2]):
        indicators["bbi_prev"] = round(float(bbi.iloc[-2]), 4)
        indicators["yellow_line_prev"] = indicators["bbi_prev"]

    # White line / Z short-term trend line: EMA(EMA(C,10),10).
    white = compute_white_line(close)
    if pd.notna(white.iloc[-1]):
        indicators["white_line"] = round(float(white.iloc[-1]), 4)

    # Volume ratio and 20-day average volume
    if len(volume) >= 20:
        avg_vol = float(volume.iloc[-20:].mean())
        if avg_vol > 0:
            indicators["volume_ratio"] = round(float(volume.iloc[-1]) / avg_vol, 4)
            indicators["avg_volume_20d"] = round(avg_vol, 2)

    # N-structure local lows (last 60 bars)
    lookback = min(60, len(low))
    recent_low = low.iloc[-lookback:]
    local_lows = detect_local_lows(recent_low, window=5)
    if local_lows:
        # Take the most recent local low
        last = local_lows[-1]
        indicators["n_structure_low"] = round(last["value"], 4)
        indicators["n_structure_low_date"] = str(last["date"])

    return indicators
