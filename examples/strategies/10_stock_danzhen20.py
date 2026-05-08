"""
单针下20 交易策略 (Danzhen20 / Ticket-Supplement Strategy).

================================================

Z哥原创策略，用于在强势股上涨途中"补票上车"，抓短线一根阳线就走。

策略逻辑:
- 基于"四线归零"改编的双线指标（红线=机构控盘线，白线=散户走光线）
- 信号触发: 红线 >= 80 且 白线 <= 20
- 确认信号: 白线回升到 20 以上，红线保持 80 以上
- 买入: 确认后次日开盘买入
- 卖出: 持有1天，次日开盘卖出（超短线）

参考文档:
- AKQuant LLM 编程指南: docs/zh/advanced/llm.md
- Obsidian 策略笔记: wiki/concepts/单针下30.md
"""

from typing import Any

import akquant as aq
import numpy as np
import pandas as pd
from akquant import Bar, Strategy


def calculate_danzhen_indicator(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    volume: np.ndarray,
    red_period: int = 20,
    white_period: int = 5,
) -> tuple[np.ndarray, np.ndarray]:
    """
    计算单针指标（红线+白线）。

    基于"四线归零"原理:
    - 红线: 长期资金行为，反映机构/主力控盘力度
    - 白线: 短期资金行为，反映散户/游资活动

    计算方法:
    - 使用价格动量和成交量加权的组合指标
    - 红线使用较长周期平滑，白线使用较短周期

    :param close: 收盘价数组
    :param high: 最高价数组
    :param low: 最低价数组
    :param volume: 成交量数组
    :param red_period: 红线计算周期（默认20）
    :param white_period: 白线计算周期（默认5）
    :return: (红线数组, 白线数组)
    """
    n = len(close)
    red_line = np.full(n, np.nan)
    white_line = np.full(n, np.nan)

    # 计算价格动量：(close - low) / (high - low) 归一化到 0-100
    price_range = high - low
    price_range[price_range == 0] = 1e-10  # 避免除零
    price_position = (close - low) / price_range * 100

    # 计算成交量加权因子
    # 成交量越大，权重越高
    vol_ma = pd.Series(volume).rolling(window=20, min_periods=1).mean().values
    vol_factor = np.where(vol_ma > 0, volume / vol_ma, 1.0)
    vol_factor = np.clip(vol_factor, 0.5, 2.0)  # 限制在 0.5-2.0 范围

    # 红线: 长期资金行为（机构控盘线）
    # 使用较长周期的指数移动平均，反映机构持续控盘力度
    red_raw = price_position * vol_factor
    red_ema = pd.Series(red_raw).ewm(span=red_period, adjust=False).mean().values
    # 归一化到 0-100
    red_min = np.nanmin(red_ema)
    red_max = np.nanmax(red_ema)
    if red_max > red_min:
        red_line = (red_ema - red_min) / (red_max - red_min) * 100
    else:
        red_line = np.full(n, 50.0)

    # 白线: 短期资金行为（散户走光线）
    # 使用较短周期的简单移动平均，反映散户短期情绪波动
    white_raw = price_position / np.maximum(vol_factor, 0.8)
    white_sma = pd.Series(white_raw).rolling(window=white_period, min_periods=1).mean().values
    # 归一化到 0-100
    white_min = np.nanmin(white_sma)
    white_max = np.nanmax(white_sma)
    if white_max > white_min:
        white_line = (white_sma - white_min) / (white_max - white_min) * 100
    else:
        white_line = np.full(n, 50.0)

    return red_line, white_line


class Danzhen20Strategy(Strategy):
    """
    单针下20 交易策略。

    核心规则:
    - 信号: 红线 >= 80 且 白线 <= 20
    - 确认: 白线回升到 20 以上，红线保持 80 以上
    - 买入: 确认后次日开盘买入
    - 卖出: 持有1天，次日开盘卖出
    - 仓位: 总资金的 5%（补票战法，极小仓位）

    适用场景:
    - 强势股上涨途中的回调补票
    - N型结构连续上升的图形
    - 大盘突破时的超短线操作
    """

    def __init__(
        self,
        red_threshold: float = 80.0,
        white_threshold: float = 20.0,
        red_period: int = 20,
        white_period: int = 5,
        position_pct: float = 0.05,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        初始化策略参数。

        :param red_threshold: 红线买入阈值（默认80）
        :param white_threshold: 白线买入阈值（默认20）
        :param red_period: 红线计算周期
        :param white_period: 白线计算周期
        :param position_pct: 仓位比例（默认5%）
        """
        super().__init__(*args, **kwargs)
        self.red_threshold = red_threshold
        self.white_threshold = white_threshold
        self.red_period = red_period
        self.white_period = white_period
        self.position_pct = position_pct

        # 预热期需要足够计算指标
        self.warmup_period = max(red_period, white_period) + 10

        # 状态跟踪
        self.signal_day = None  # 信号触发日
        self.waiting_for_confirm = False  # 等待确认

    def on_bar(self, bar: Bar) -> None:
        """处理每个 Bar 数据。"""
        symbol = bar.symbol

        # 获取历史数据
        count = self.warmup_period + 5
        closes = self.get_history(count, symbol, "close")
        highs = self.get_history(count, symbol, "high")
        lows = self.get_history(count, symbol, "low")
        volumes = self.get_history(count, symbol, "volume")

        # 数据充分性检查
        if len(closes) < self.warmup_period:
            return

        # 计算单针指标
        red_line, white_line = calculate_danzhen_indicator(
            closes, highs, lows, volumes,
            red_period=self.red_period,
            white_period=self.white_period,
        )

        # 获取当前值
        current_red = red_line[-1]
        current_white = white_line[-1]
        prev_red = red_line[-2] if len(red_line) > 1 else current_red
        prev_white = white_line[-2] if len(white_line) > 1 else current_white

        # 获取当前持仓
        current_pos = self.get_position(symbol)

        # ========== 交易逻辑 ==========

        # 卖出逻辑: 持有1天后次日开盘卖出
        if current_pos > 0 and self.signal_day is not None:
            # 超短线策略: 只做一天，次日卖出
            days_held = bar.timestamp.date() - self.signal_day
            if days_held.days >= 1:
                self.sell(symbol, current_pos)
                print(
                    f"[{bar.timestamp_str}] SELL (hold 1 day): "
                    f"Price={bar.close:.2f}, Red={current_red:.1f}, White={current_white:.1f}"
                )
                self.signal_day = None
                return

        # 买入逻辑: 等待确认信号
        if current_pos == 0:
            # 步骤1: 检查是否触发信号（红线>=80 且 白线<=20）
            if (
                current_red >= self.red_threshold
                and current_white <= self.white_threshold
            ):
                # 记录信号日
                self.signal_day = bar.timestamp.date()
                self.waiting_for_confirm = True
                print(
                    f"[{bar.timestamp_str}] SIGNAL: Red={current_red:.1f} >= {self.red_threshold}, "
                    f"White={current_white:.1f} <= {self.white_threshold}"
                )

            # 步骤2: 等待确认（白线回升到20以上，红线保持80以上）
            elif self.waiting_for_confirm and self.signal_day is not None:
                # 检查是否收回
                days_since_signal = bar.timestamp.date() - self.signal_day
                if (
                    days_since_signal.days >= 1
                    and current_white > self.white_threshold
                    and current_red >= self.red_threshold
                ):
                    # 确认信号，买入
                    self.order_target_percent(
                        symbol=symbol,
                        target_percent=self.position_pct,
                    )
                    print(
                        f"[{bar.timestamp_str}] BUY (confirmed): "
                        f"Price={bar.close:.2f}, Red={current_red:.1f}, White={current_white:.1f}"
                    )
                    self.waiting_for_confirm = False
                    # 保持 signal_day 用于卖出计时

                # 信号超时（3天内未确认，放弃）
                elif days_since_signal.days >= 3:
                    self.waiting_for_confirm = False
                    self.signal_day = None
                    print(
                        f"[{bar.timestamp_str}] SIGNAL TIMEOUT: "
                        f"Red={current_red:.1f}, White={current_white:.1f}"
                    )


if __name__ == "__main__":
    import akshare as ak

    # 1. 准备数据
    # 以平安银行 (sz000001) 为例
    symbol = "sz000001"
    df = ak.stock_zh_a_daily(
        symbol=symbol, start_date="20220101", end_date="20231231", adjust="qfq"
    )

    # 2. 运行回测
    result = aq.run_backtest(
        data=df,
        strategy=Danzhen20Strategy,
        symbols=symbol,
        initial_cash=100_000.0,
        commission_rate=0.0003,  # 万三佣金
        min_commission=5.0,  # 最低5元
        stamp_tax_rate=0.001,  # 千一印花税（仅卖出）
        lot_size=100,  # A股每手100股
    )

    # 3. 输出结果
    print("\n=== 单针下20 回测结果 ===")
    print(result)
