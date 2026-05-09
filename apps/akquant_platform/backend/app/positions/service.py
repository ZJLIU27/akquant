"""Position service — orchestrates repository, calculator, rules, and intraday."""

from __future__ import annotations

import json
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
        try:
            indicators = compute_indicators(daily_df)
        except Exception:
            indicators = {}

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

    def export_ai_context(
        self,
        symbol: str | None = None,
        all_open: bool = False,
        include_transactions: bool = True,
        include_rule_results: bool = True,
    ) -> dict[str, Any]:
        """Export read-only position context for external agents."""
        generated_at = _now_iso()

        if all_open:
            listed = self.list_positions()
            positions = []
            for summary in listed.positions:
                if summary.status != "open":
                    continue
                detail = self.get_position_detail(summary.symbol)
                raw_position = detail.position if detail is not None else None
                positions.append(
                    self._position_ai_summary(
                        summary,
                        position=raw_position,
                        include_rule_summary=True,
                    )
                )
            return {
                "schema_version": 1,
                "generated_at": generated_at,
                "source": "akquant",
                "positions": positions,
                "portfolio_summary": {
                    "open_position_count": len(positions),
                    "total_market_value": round(listed.total_market_value, 2),
                    "total_unrealized_pnl": round(
                        sum(p.get("unrealized_pnl", 0.0) for p in positions), 2
                    ),
                },
                "data_warnings": [],
            }

        if not symbol:
            return {
                "schema_version": 1,
                "generated_at": generated_at,
                "source": "akquant",
                "symbol": None,
                "position": None,
                "transactions": [],
                "market": None,
                "rule_results": [],
                "data_warnings": ["symbol is required unless all_open is true"],
            }

        detail = self.get_position_detail(symbol)
        if detail is None:
            return {
                "schema_version": 1,
                "generated_at": generated_at,
                "source": "akquant",
                "symbol": symbol,
                "position": None,
                "transactions": [],
                "market": self._market_ai_context(symbol),
                "rule_results": [],
                "data_warnings": [f"position not found: {symbol}"],
            }

        warnings: list[str] = []
        if detail.summary.status == "invalid":
            warnings.append(f"position is invalid: {symbol}")
        if detail.summary.price_source == "missing":
            warnings.append(f"latest price is missing: {symbol}")

        rule_results = (
            [
                self._rule_result_ai_context(
                    r,
                    {rule.id: rule for rule in detail.position.rules}.get(r.rule_id),
                    detail.position,
                )
                for r in detail.rule_results
            ]
            if include_rule_results
            else []
        )
        for result in rule_results:
            if result["status"] == "error":
                warnings.append(
                    f"rule error: {result['script_id']} ({result['message']})"
                )

        position_context = self._position_ai_summary(
            detail.summary,
            position=detail.position,
        )
        position_context["id"] = detail.position.id
        position_context["holding_days"] = self._holding_days(detail.position)

        return {
            "schema_version": 1,
            "generated_at": generated_at,
            "source": "akquant",
            "symbol": symbol,
            "position": position_context,
            "transactions": (
                [self._transaction_ai_context(t) for t in detail.position.transactions]
                if include_transactions
                else []
            ),
            "market": self._market_ai_context(symbol),
            "rule_results": rule_results,
            "data_warnings": warnings,
        }

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

    def _position_ai_summary(
        self,
        summary: PositionSummary,
        position: Position | None = None,
        include_rule_summary: bool = False,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "symbol": summary.symbol,
            "name": summary.name,
            "status": summary.status,
            "strategy_id": position.strategy_id if position is not None else "",
            "strategy_tags": position.strategy_tags if position is not None else [],
            "strategy_note_paths": (
                position.strategy_note_paths if position is not None else []
            ),
            "quantity": summary.remaining_quantity,
            "avg_cost": summary.avg_cost,
            "latest_price": summary.latest_price,
            "price_source": summary.price_source,
            "market_value": summary.market_value,
            "realized_pnl": summary.realized_pnl,
            "unrealized_pnl": summary.unrealized_pnl,
            "unrealized_pnl_pct": _pct(summary.unrealized_pnl, summary.cost_amount),
            "position_weight": summary.position_weight,
            "notes": summary.notes,
        }
        if include_rule_summary:
            detail = self.get_position_detail(summary.symbol)
            counts = {"danger": 0, "warning": 0, "info": 0}
            if detail is not None:
                for rule_result in detail.rule_results:
                    counts[rule_result.level] = counts.get(rule_result.level, 0) + 1
            data["rule_summary"] = counts
        return data

    def _transaction_ai_context(self, txn: Transaction) -> dict[str, Any]:
        return {
            "id": txn.id,
            "side": txn.side,
            "trade_date": str(txn.trade_date),
            "quantity": txn.quantity,
            "price": txn.price,
            "fee": txn.fee,
            "source": txn.source,
            "tags": txn.tags,
            "notes": txn.notes,
            "voided": txn.voided,
        }

    def _rule_result_ai_context(
        self,
        result: RuleResult,
        rule: PositionRule | None = None,
        position: Position | None = None,
    ) -> dict[str, Any]:
        return {
            "rule_id": result.rule_id,
            "script_id": result.script_id,
            "strategy_id": (
                rule.strategy_id
                if rule is not None and rule.strategy_id
                else position.strategy_id
                if position is not None
                else ""
            ),
            "category": rule.category if rule is not None else None,
            "status": result.status,
            "level": result.level,
            "message": result.message,
        }

    def _market_ai_context(self, symbol: str) -> dict[str, Any]:
        price, source = self.cache.resolve_price(symbol, self.config.daily_data_dir)
        intraday_df = self.cache.get_intraday_df(symbol)
        daily_df = self._load_daily_df(symbol, days=1)
        intraday_meta = self._latest_intraday_meta(symbol)
        daily_last_date = None
        if daily_df is not None and not daily_df.empty:
            last_index = pd.to_datetime(daily_df.index[-1])
            daily_last_date = last_index.strftime("%Y-%m-%d")
        return {
            "symbol": symbol,
            "latest_price": price,
            "price_source": source,
            "daily_last_date": daily_last_date,
            "intraday_updated_at": intraday_meta.get("updated_at"),
            "intraday_rows": (
                len(intraday_df) if intraday_df is not None else intraday_meta.get("rows")
            ),
        }

    def _latest_intraday_meta(self, symbol: str) -> dict[str, Any]:
        symbol_dir = Path(self.config.intraday_data_dir) / symbol
        if not symbol_dir.exists():
            return {}
        meta_files = sorted(symbol_dir.glob("*.meta.json"), reverse=True)
        for meta_file in meta_files:
            try:
                with open(meta_file, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                continue
        return {}

    def _holding_days(self, position: Position) -> int | None:
        buy_dates = [
            txn.trade_date
            for txn in position.transactions
            if txn.side == "buy" and not txn.voided
        ]
        if not buy_dates:
            return None
        first_buy_date = min(buy_dates)
        today = pd.Timestamp.now(tz="Asia/Shanghai").date()
        return max((today - first_buy_date).days, 0)


def _float_or_none(value: Any) -> float | None:
    if pd.isna(value):
        return None
    return round(float(value), 4)


def _now_iso() -> str:
    return pd.Timestamp.now(tz="Asia/Shanghai").isoformat()


def _pct(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator * 100, 2)
