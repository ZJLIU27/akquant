"""Position service — orchestrates repository, calculator, rules, and intraday."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ..config import PlatformConfig
from ..intraday.cache import IntradayCache
from .calculator import calculate_position, calculate_position_weights
from .indicators import (
    compute_bbi,
    compute_brick_series,
    compute_indicators,
    compute_single_pin_series,
    compute_white_line,
)
from .models import (
    Position,
    PositionDetail,
    PositionListResponse,
    PositionRule,
    PositionSummary,
    RuleResult,
    Transaction,
)
from .repository import PositionRepository
from .rules import RuleRegistry, evaluate_rules


class PositionService:
    """High-level position operations used by both CLI and API."""

    def __init__(self, config: PlatformConfig) -> None:
        self.config = config
        self.repo = PositionRepository(config.positions_file)
        self.registry = RuleRegistry(config.registry_file, config.workspace_dir)
        self.cache = IntradayCache(
            config.intraday_data_dir,
            ttl_seconds=config.intraday_cache_ttl_seconds,
            retention_days=config.intraday_cache_retention_days,
            tz=config.timezone,
        )

    def init(self) -> None:
        """Initialize positions file and load registry."""
        self.repo.init_file()
        self.registry.load()

    def _load_daily_df(self, symbol: str, days: int = 130) -> pd.DataFrame | None:
        """Load daily OHLCV data for a symbol."""
        parquet_path = Path(self.config.daily_data_dir) / f"{symbol}.parquet"
        if not parquet_path.exists():
            return None
        try:
            df = pd.read_parquet(parquet_path)
            if len(df) > days:
                df = df.iloc[-days:]
            return df
        except Exception:
            return None

    # --- Read operations ---

    def list_positions(self) -> PositionListResponse:
        """List all positions with computed summaries."""
        positions = self.repo.list_positions()
        summaries: list[PositionSummary] = []

        for pos in positions:
            price, source = self.cache.resolve_price(
                pos.symbol, self.config.daily_data_dir
            )
            summary = calculate_position(pos, price, source)
            summaries.append(summary)

        summaries = calculate_position_weights(summaries)
        total_mv = sum(s.market_value for s in summaries if s.status == "open")

        return PositionListResponse(
            positions=summaries,
            total_market_value=round(total_mv, 2),
        )

    def get_position_detail(self, symbol: str) -> PositionDetail | None:
        """Get full position detail with rules evaluation."""
        pos = self.repo.get_position(symbol)
        if pos is None:
            return None

        price, source = self.cache.resolve_price(
            symbol, self.config.daily_data_dir
        )
        summary = calculate_position(pos, price, source)

        daily_df = self._load_daily_df(symbol)
        indicators = compute_indicators(daily_df)

        market = None
        if price is not None:
            market = {
                "latest_price": price,
                "price_source": source,
                "intraday_df": self.cache.get_intraday_df(symbol),
                "daily_df": daily_df,
                "indicators": indicators,
            }

        rule_results = evaluate_rules(
            pos, summary, market, pos.rules, self.registry
        )

        return PositionDetail(
            position=pos,
            summary=summary,
            rule_results=rule_results,
        )

    def get_daily_chart(self, symbol: str, days: int = 130) -> dict[str, Any]:
        """Return daily OHLCV data plus indicator series for charting."""
        df = self._load_daily_df(symbol, days=days)
        if df is None or df.empty:
            return {"symbol": symbol, "data": None, "rows": 0, "status": "missing"}

        df = df.copy()
        df.index = pd.to_datetime(df.index)
        close = df["close"].astype(float)
        bbi = compute_bbi(close)
        white = compute_white_line(close)
        single_pin = compute_single_pin_series(df)
        brick = compute_brick_series(df)
        brick_prev = brick.shift(1).fillna(0.0)
        brick_delta = brick - brick_prev

        records: list[dict[str, Any]] = []
        for idx, row in df.iterrows():
            brick_value = brick.loc[idx]
            brick_base = brick_prev.loc[idx]
            brick_change = brick_delta.loc[idx]
            
            open_val = row.get("open")
            close_val = row.get("close")
            volume_color = "#F6465D" if (close_val is not None and open_val is not None and close_val >= open_val) else "#0ECB81"

            records.append(
                {
                    "date": idx.strftime("%Y-%m-%d"),
                    "open": _float_or_none(open_val),
                    "close": _float_or_none(close_val),
                    "high": _float_or_none(row.get("high")),
                    "low": _float_or_none(row.get("low")),
                    "volume": _float_or_none(row.get("volume")),
                    "volume_color": volume_color,
                    "yellow_line": _float_or_none(bbi.loc[idx]),
                    "white_line": _float_or_none(white.loc[idx]),
                    "single_pin_short": _float_or_none(single_pin["single_pin_short"].loc[idx]),
                    "single_pin_mid": _float_or_none(single_pin["single_pin_mid"].loc[idx]),
                    "single_pin_mid_long": _float_or_none(single_pin["single_pin_mid_long"].loc[idx]),
                    "single_pin_long": _float_or_none(single_pin["single_pin_long"].loc[idx]),
                    "brick": _float_or_none(brick_value),
                    "brick_base": _float_or_none(min(float(brick_base), float(brick_value)) if not pd.isna(brick_value) else None),
                    "brick_delta": _float_or_none(abs(float(brick_change)) if not pd.isna(brick_change) else None),
                    "brick_color": "#F6465D" if not pd.isna(brick_change) and float(brick_change) >= 0 else "#0ECB81",
                }
            )

        return {
            "symbol": symbol,
            "data": records,
            "rows": len(records),
            "status": "ok",
        }

    # --- Write operations ---

    def add_buy(
        self,
        symbol: str,
        trade_date: str,
        quantity: int,
        price: float,
        fee: float = 0.0,
        name: str = "",
        notes: str = "",
        source: str = "manual",
        tags: list[str] | None = None,
    ) -> Transaction:
        """Add a buy transaction. Creates position if new."""
        was_new = self.repo.get_position(symbol) is None
        txn = self.repo.add_transaction(
            symbol=symbol,
            side="buy",
            trade_date=trade_date,
            quantity=quantity,
            price=price,
            fee=fee,
            name=name,
            notes=notes,
            source=source,
            tags=tags,
        )
        # If new position becomes open, trigger intraday refresh
        if was_new:
            self._trigger_intraday_refresh(symbol)
        return txn

    def add_sell(
        self,
        symbol: str,
        trade_date: str,
        quantity: int,
        price: float,
        fee: float = 0.0,
        notes: str = "",
        source: str = "manual",
        tags: list[str] | None = None,
    ) -> Transaction | None:
        """Add a sell transaction. Validates remaining quantity first."""
        pos = self.repo.get_position(symbol)
        if pos is None:
            return None

        summary = calculate_position(pos)
        if summary.remaining_quantity < quantity:
            return None

        return self.repo.add_transaction(
            symbol=symbol,
            side="sell",
            trade_date=trade_date,
            quantity=quantity,
            price=price,
            fee=fee,
            notes=notes,
            source=source,
            tags=tags,
        )

    def edit_transaction(
        self, symbol: str, transaction_id: str, **updates: Any
    ) -> Transaction | None:
        return self.repo.edit_transaction(symbol, transaction_id, **updates)

    def void_transaction(
        self, symbol: str, transaction_id: str, void_reason: str = ""
    ) -> Transaction | None:
        return self.repo.void_transaction(symbol, transaction_id, void_reason)

    # --- Rules ---

    def add_rule(
        self,
        symbol: str,
        category: str,
        script_id: str,
        params: dict[str, Any] | None = None,
    ) -> PositionRule | None:
        """Add a rule. Validates script_id against registry."""
        if not self.registry.validate_script_id(script_id):
            return None
        return self.repo.add_rule(symbol, category, script_id, params)

    def delete_rule(self, symbol: str, rule_id: str) -> bool:
        return self.repo.delete_rule(symbol, rule_id)

    def get_available_rules(self) -> list[dict[str, Any]]:
        return self.registry.get_script_ids()

    # --- Validation ---

    def validate(self) -> list[str]:
        return self.repo.validate()

    # --- Intraday ---

    def get_intraday_df(self, symbol: str) -> Any:
        """Get intraday DataFrame for a symbol."""
        return self.cache.get_intraday_df(symbol)

    def needs_intraday_refresh(self, symbol: str) -> bool:
        """Check if symbol needs intraday data refresh."""
        return not self.cache.is_cache_valid(symbol)

    def get_open_symbols(self) -> list[str]:
        """Get list of symbols with open positions."""
        positions = self.repo.list_positions()
        symbols = []
        for pos in positions:
            summary = calculate_position(pos)
            if summary.status == "open":
                symbols.append(pos.symbol)
        return symbols

    def _trigger_intraday_refresh(self, symbol: str) -> None:
        """Trigger intraday refresh for a symbol. Best-effort, non-blocking."""
        try:
            from ..intraday.cache import download_intraday

            df = download_intraday(symbol)
            if df is not None:
                self.cache.save_intraday(symbol, df)
        except Exception:
            pass


def _float_or_none(value: Any) -> float | None:
    if pd.isna(value):
        return None
    return round(float(value), 4)
