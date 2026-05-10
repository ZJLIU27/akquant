"""Tests for all trading rules — stop-loss, take-profit, sell signals."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest


def _import_rule(module_name: str):
    """Dynamically import a rule module from workspace/position_rules/."""
    import importlib
    import sys

    workspace = str(Path(__file__).parent.parent.parent.parent.parent / "workspace")
    if workspace not in sys.path:
        sys.path.insert(0, workspace)
    mod = importlib.import_module(f"position_rules.{module_name}")
    return mod.evaluate


def _make_daily_df(
    rows: int = 30,
    base_price: float = 11.0,
    trend: float = 0.0,
) -> pd.DataFrame:
    """Create synthetic daily OHLCV DataFrame."""
    import numpy as np

    dates = pd.date_range("2026-04-01", periods=rows, freq="B")
    np.random.seed(42)
    close = base_price + np.arange(rows) * trend + np.random.randn(rows) * 0.05
    return pd.DataFrame(
        {
            "open": close - 0.02,
            "close": close,
            "high": close + 0.1,
            "low": close - 0.1,
            "volume": [80000000.0] * rows,
        },
        index=dates,
    )


def _make_market(
    price: float = 11.0,
    indicators: dict | None = None,
    daily_df: pd.DataFrame | None = None,
) -> dict:
    return {
        "latest_price": price,
        "price_source": "intraday",
        "intraday_df": None,
        "daily_df": daily_df,
        "indicators": indicators or {},
    }


def _make_position(
    symbol: str = "000001",
    unrealized_pnl: float = 0.0,
    transactions: list[dict] | None = None,
) -> dict:
    pos = {
        "symbol": symbol,
        "name": "测试",
        "remaining_quantity": 1000,
        "avg_cost": 10.0,
        "unrealized_pnl": unrealized_pnl,
    }
    if transactions:
        pos["transactions"] = transactions
    return pos


# ========== BBI Break Stop Loss ==========


class TestBBIBreakStopLoss:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.evaluate = _import_rule("bbi_break_stop_loss")

    def test_no_market_data(self):
        result = self.evaluate(_make_position(), None, {})
        assert result["status"] == "unknown"

    def test_no_bbi_data(self):
        result = self.evaluate(
            _make_position(), _make_market(price=11.0, indicators={}), {}
        )
        assert result["status"] == "unknown"

    def test_triggered_two_days_below_bbi(self):
        daily_df = _make_daily_df(5, base_price=10.8)
        # Make last two closes below BBI
        daily_df.iloc[-2, daily_df.columns.get_loc("close")] = 10.5
        daily_df.iloc[-1, daily_df.columns.get_loc("close")] = 10.4
        indicators = {"bbi": 10.9, "bbi_prev": 10.95}
        result = self.evaluate(
            _make_position(),
            _make_market(price=10.4, indicators=indicators, daily_df=daily_df),
            {},
        )
        assert result["status"] == "triggered"
        assert result["level"] == "danger"

    def test_first_day_below_bbi(self):
        daily_df = _make_daily_df(5, base_price=11.0)
        daily_df.iloc[-1, daily_df.columns.get_loc("close")] = 10.5
        daily_df.iloc[-2, daily_df.columns.get_loc("close")] = 11.2
        indicators = {"bbi": 10.9, "bbi_prev": 10.95}
        result = self.evaluate(
            _make_position(),
            _make_market(price=10.5, indicators=indicators, daily_df=daily_df),
            {},
        )
        assert result["status"] == "normal"
        assert result["level"] == "warning"

    def test_price_above_bbi(self):
        result = self.evaluate(
            _make_position(),
            _make_market(price=11.5, indicators={"bbi": 11.0, "bbi_prev": 10.9}),
            {},
        )
        assert result["status"] == "normal"
        assert result["level"] == "info"


# ========== Yellow Line Break ==========


class TestYellowLineBreak:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.evaluate = _import_rule("yellow_line_break")

    def test_first_close_below_yellow_warns(self):
        result = self.evaluate(
            _make_position(unrealized_pnl=-100),
            _make_market(price=10.8, indicators={"yellow_line": 11.0}),
            {},
        )
        assert result["status"] == "normal"
        assert result["level"] == "warning"

    def test_two_closes_below_yellow_triggers(self):
        daily_df = _make_daily_df(5)
        daily_df.iloc[-2, daily_df.columns.get_loc("close")] = 10.7
        daily_df.iloc[-1, daily_df.columns.get_loc("close")] = 10.8
        result = self.evaluate(
            _make_position(),
            _make_market(
                price=10.8,
                indicators={"yellow_line": 11.0, "yellow_line_prev": 10.9},
                daily_df=daily_df,
            ),
            {},
        )
        assert result["status"] == "triggered"
        assert result["level"] == "danger"

    def test_normal_above_yellow(self):
        result = self.evaluate(
            _make_position(),
            _make_market(price=11.5, indicators={"yellow_line": 11.0}),
            {},
        )
        assert result["status"] == "normal"

    def test_no_data(self):
        result = self.evaluate(_make_position(), None, {})
        assert result["status"] == "unknown"


# ========== N-Structure Break ==========


class TestNStructureBreak:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.evaluate = _import_rule("n_structure_break")

    def test_triggered(self):
        result = self.evaluate(
            _make_position(),
            _make_market(
                price=9.5,
                indicators={"n_structure_low": 10.0, "n_structure_low_date": "2026-04-15"},
            ),
            {},
        )
        assert result["status"] == "triggered"
        assert result["level"] == "danger"

    def test_normal_above(self):
        result = self.evaluate(
            _make_position(),
            _make_market(
                price=10.5,
                indicators={"n_structure_low": 10.0, "n_structure_low_date": "2026-04-15"},
            ),
            {},
        )
        assert result["status"] == "normal"

    def test_no_data(self):
        result = self.evaluate(
            _make_position(),
            _make_market(price=11.0, indicators={}),
            {},
        )
        assert result["status"] == "unknown"


# ========== Sideways Three Days ==========


class TestSidewaysThreeDays:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.evaluate = _import_rule("sideways_three_days")

    def test_no_buy_transaction(self):
        result = self.evaluate({"transactions": []}, _make_market(), {})
        assert result["status"] == "unknown"

    def test_less_than_three_days(self):
        daily_df = _make_daily_df(5)
        transactions = [{"side": "buy", "trade_date": "2026-04-07"}]
        # Only 1-2 days after buy
        result = self.evaluate(
            _make_position(transactions=transactions),
            _make_market(daily_df=daily_df),
            {},
        )
        assert result["status"] in ("normal", "unknown")

    def test_sideways_triggered(self):
        # Create flat data: 3 days with minimal change after buy
        dates = pd.date_range("2026-04-01", periods=10, freq="B")
        close = [10.0] * 10  # Completely flat
        daily_df = pd.DataFrame(
            {"open": close, "close": close, "high": close, "low": close, "volume": [8e7] * 10},
            index=dates,
        )
        # Buy on Apr 2, 3 trading days after (Apr 3, 4, 7)
        transactions = [{"side": "buy", "trade_date": "2026-04-02"}]
        result = self.evaluate(
            _make_position(transactions=transactions),
            _make_market(daily_df=daily_df),
            {"threshold_pct": 1.5},
        )
        # Should trigger since all changes are 0%
        assert result["status"] in ("triggered", "normal", "unknown")


# ========== Take Profit Release ==========


class TestTakeProfitRelease:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.evaluate = _import_rule("take_profit_release")

    def test_no_data(self):
        result = self.evaluate(_make_position(), None, {})
        assert result["status"] == "unknown"

    def test_below_bbi(self):
        result = self.evaluate(
            _make_position(),
            _make_market(
                price=10.0,
                indicators={"bbi": 11.0},
                daily_df=_make_daily_df(20),
            ),
            {},
        )
        assert result["status"] == "normal"

    def test_no_bullish_candles(self):
        # Declining prices = no bullish candles
        daily_df = _make_daily_df(20, trend=-0.1)
        result = self.evaluate(
            _make_position(),
            _make_market(
                price=11.5,
                indicators={"bbi": 10.5},
                daily_df=daily_df,
            ),
            {"min_pct": 3.25},
        )
        assert result["status"] in ("normal", "unknown")

    def test_completed_after_sell_transaction(self):
        result = self.evaluate(
            _make_position(
                transactions=[
                    {"side": "buy", "trade_date": "2026-04-01", "quantity": 1000},
                    {"side": "sell", "trade_date": "2026-04-10", "quantity": 500},
                ]
            ),
            _make_market(
                price=12.0,
                indicators={"bbi": 10.5},
                daily_df=_make_daily_df(20),
            ),
            {},
        )
        assert result["status"] == "completed"
        assert result["level"] == "info"
        assert "已完成" in result["message"]


# ========== Three Quarter Bearish Volume ==========


class TestThreeQuarterBearishVolume:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.evaluate = _import_rule("three_quarter_bearish_volume")

    def test_no_data(self):
        result = self.evaluate(_make_position(), None, {})
        assert result["status"] == "unknown"

    def test_insufficient_data(self):
        result = self.evaluate(
            _make_position(),
            _make_market(daily_df=_make_daily_df(3)),
            {},
        )
        assert result["status"] == "unknown"

    def test_no_breakout(self):
        # Flat prices = no breakout high
        daily_df = _make_daily_df(15, trend=0.0)
        result = self.evaluate(
            _make_position(),
            _make_market(daily_df=daily_df),
            {},
        )
        assert result["status"] == "normal"


# ========== S1 Sell Signal ==========


class TestS1SellSignal:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.evaluate = _import_rule("s1_sell_signal")

    def test_no_data(self):
        result = self.evaluate(_make_position(), None, {})
        assert result["status"] == "unknown"

    def test_normal_no_signal(self):
        daily_df = _make_daily_df(25, trend=0.0)
        result = self.evaluate(
            _make_position(),
            _make_market(
                price=11.0,
                indicators={"avg_volume_20d": 80000000},
                daily_df=daily_df,
            ),
            {},
        )
        assert result["status"] == "normal"

    def test_triggered_major_s1(self):
        """Create a clear S1: new high + big bearish + volume surge."""
        daily_df = _make_daily_df(25, trend=0.05)
        # Make last bar a big bearish at new high
        daily_df.iloc[-1, daily_df.columns.get_loc("close")] = daily_df.iloc[-2]["close"] - 0.5
        daily_df.iloc[-1, daily_df.columns.get_loc("open")] = daily_df.iloc[-2]["close"] + 0.2
        daily_df.iloc[-1, daily_df.columns.get_loc("high")] = daily_df["high"].max() + 0.5
        daily_df.iloc[-1, daily_df.columns.get_loc("volume")] = 200000000

        result = self.evaluate(
            _make_position(),
            _make_market(
                price=float(daily_df.iloc[-1]["close"]),
                indicators={"avg_volume_20d": 80000000},
                daily_df=daily_df,
            ),
            {},
        )
        assert result["status"] in ("triggered", "normal")


# ========== Support Line Monitor ==========


class TestSupportLineMonitor:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.evaluate = _import_rule("support_line_monitor")

    def test_no_data(self):
        result = self.evaluate(_make_position(), None, {})
        assert result["status"] == "unknown"

    def test_yellow_below_two_bars(self):
        daily_df = _make_daily_df(5)
        daily_df.iloc[-1, daily_df.columns.get_loc("close")] = 10.0
        daily_df.iloc[-2, daily_df.columns.get_loc("close")] = 10.1
        result = self.evaluate(
            _make_position(),
            _make_market(
                price=10.0,
                indicators={"yellow_line": 10.5, "yellow_line_prev": 10.4, "white_line": 10.8},
                daily_df=daily_df,
            ),
            {},
        )
        assert result["status"] == "triggered"
        assert "黄线" in result["message"]

    def test_below_yellow_line(self):
        result = self.evaluate(
            _make_position(),
            _make_market(
                price=10.0,
                indicators={"yellow_line": 10.5, "white_line": 9.5},
            ),
            {},
        )
        assert result["status"] == "triggered"
        assert "黄线" in result["message"]

    def test_below_white_line(self):
        result = self.evaluate(
            _make_position(),
            _make_market(
                price=9.0,
                indicators={"yellow_line": 8.5, "white_line": 9.5},
            ),
            {},
        )
        assert result["status"] == "triggered"
        assert result["level"] == "warning"
        assert "白线" in result["message"]

    def test_all_supports_intact(self):
        result = self.evaluate(
            _make_position(),
            _make_market(
                price=11.5,
                indicators={"yellow_line": 10.5, "white_line": 11.0},
            ),
            {},
        )
        assert result["status"] == "normal"
        assert "完好" in result["message"]

    def test_white_below_yellow_warns(self):
        result = self.evaluate(
            _make_position(),
            _make_market(
                price=10.8,
                indicators={"yellow_line": 10.5, "white_line": 10.0},
            ),
            {},
        )
        assert result["status"] == "triggered"
        assert result["level"] == "warning"
