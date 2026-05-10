#!/usr/bin/env python3
"""AKQuant 持仓管理 CLI.

用法:
    python scripts/positions_cli.py init
    python scripts/positions_cli.py open --symbol 000001 --name 平安银行 --date 2026-05-08 --quantity 1000 --price 10.50 --fee 5
    python scripts/positions_cli.py transact --position-id <id> --side sell --date 2026-05-10 --quantity 500 --price 11.00 --fee 5
    python scripts/positions_cli.py list
    python scripts/positions_cli.py validate
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add backend to path so we can import app modules
_backend_dir = (
    Path(__file__).resolve().parents[1] / "apps" / "akquant_platform" / "backend"
)
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from app.config import load_config
from app.positions.service import PositionService


def cmd_init(service: PositionService) -> None:
    service.init()
    print("Positions file initialized.")


def cmd_buy(service: PositionService, args: argparse.Namespace) -> None:
    txn = service.add_buy(
        symbol=args.symbol,
        trade_date=args.date,
        quantity=args.quantity,
        price=args.price,
        fee=args.fee,
        name=args.name,
        notes=args.notes,
    )
    positions = service.repo.get_positions_by_symbol(args.symbol)
    position_id = positions[-1].id if positions else ""
    print(
        f"New position opened: {position_id} | transaction {txn.id[:8]}... {args.symbol} {args.quantity}@{args.price}"
    )


def cmd_transact(service: PositionService, args: argparse.Namespace) -> None:
    txn = service.add_position_transaction(
        position_id=args.position_id,
        side=args.side,
        trade_date=args.date,
        quantity=args.quantity,
        price=args.price,
        fee=args.fee,
        notes=args.notes,
    )
    if txn is None:
        print(
            f"Error: cannot add {args.side} transaction to {args.position_id} (insufficient holdings or position not found)",
            file=sys.stderr,
        )
        sys.exit(1)
    print(
        f"Transaction added: {txn.id[:8]}... {args.position_id} {args.side} {args.quantity}@{args.price}"
    )


def cmd_list(service: PositionService) -> None:
    result = service.list_positions()
    if not result.positions:
        print("No positions.")
        return

    print(
        f"{'Position ID':<36} {'Symbol':<8} {'Name':<10} {'Qty':>6} {'AvgCost':>10} {'Price':>10} {'MV':>12} {'PnL':>12} {'Weight':>8} {'Status':<8}"
    )
    print("-" * 133)
    for p in result.positions:
        price_str = f"{p.latest_price:.2f}" if p.latest_price else "N/A"
        mv_str = f"{p.market_value:.2f}" if p.market_value else "0.00"
        pnl = p.realized_pnl + p.unrealized_pnl
        print(
            f"{p.id:<36} {p.symbol:<8} {p.name:<10} {p.remaining_quantity:>6} "
            f"{p.avg_cost:>10.4f} {price_str:>10} {mv_str:>12} "
            f"{pnl:>12.2f} {p.position_weight * 100:>7.1f}% {p.status:<8}"
        )
    print(f"\nTotal market value: {result.total_market_value:.2f}")


def cmd_validate(service: PositionService) -> None:
    errors = service.validate()
    if not errors:
        print("All positions valid.")
    else:
        print(f"Found {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)


def cmd_ai_context(service: PositionService, args: argparse.Namespace) -> None:
    context = service.export_ai_context(
        symbol=args.symbol,
        all_open=args.all_open,
        include_transactions=not args.no_transactions,
        include_rule_results=not args.no_rule_results,
        include_daily=args.include_daily,
        days=args.days,
    )
    if args.format == "json":
        print(json.dumps(context, ensure_ascii=False, indent=2, sort_keys=False))
    else:
        raise ValueError(f"Unsupported format: {args.format}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AKQuant 持仓管理 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config", type=str, default=None, help="Platform config file path"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    subparsers.add_parser("init", help="Initialize positions file")

    # open / buy
    buy_parser = subparsers.add_parser("open", help="Open a new independent position")
    buy_parser.add_argument("--symbol", required=True)
    buy_parser.add_argument("--name", default="")
    buy_parser.add_argument("--date", required=True)
    buy_parser.add_argument("--quantity", type=int, required=True)
    buy_parser.add_argument("--price", type=float, required=True)
    buy_parser.add_argument("--fee", type=float, default=0)
    buy_parser.add_argument("--notes", default="")

    buy_alias_parser = subparsers.add_parser("buy", help="Alias for open")
    buy_alias_parser.add_argument("--symbol", required=True)
    buy_alias_parser.add_argument("--name", default="")
    buy_alias_parser.add_argument("--date", required=True)
    buy_alias_parser.add_argument("--quantity", type=int, required=True)
    buy_alias_parser.add_argument("--price", type=float, required=True)
    buy_alias_parser.add_argument("--fee", type=float, default=0)
    buy_alias_parser.add_argument("--notes", default="")

    # transact
    txn_parser = subparsers.add_parser("transact", help="Add a buy/sell operation to an existing position")
    txn_parser.add_argument("--position-id", required=True)
    txn_parser.add_argument("--side", choices=["buy", "sell"], required=True)
    txn_parser.add_argument("--date", required=True)
    txn_parser.add_argument("--quantity", type=int, required=True)
    txn_parser.add_argument("--price", type=float, required=True)
    txn_parser.add_argument("--fee", type=float, default=0)
    txn_parser.add_argument("--notes", default="")

    # list
    subparsers.add_parser("list", help="List all positions")

    # validate
    subparsers.add_parser("validate", help="Validate positions file")

    # ai-context
    ai_parser = subparsers.add_parser(
        "ai-context",
        help="Export read-only position context for external agents",
    )
    ai_target = ai_parser.add_mutually_exclusive_group(required=True)
    ai_target.add_argument("--symbol", help="Export one symbol")
    ai_target.add_argument(
        "--all-open", action="store_true", help="Export all open positions"
    )
    ai_parser.add_argument("--format", choices=["json"], default="json")
    ai_parser.add_argument("--no-transactions", action="store_true")
    ai_parser.add_argument("--no-rule-results", action="store_true")
    ai_parser.add_argument(
        "--include-rule-results",
        action="store_false",
        dest="no_rule_results",
        help="Include full rule_results in each exported position (default)",
    )
    ai_parser.add_argument(
        "--include-daily",
        action="store_true",
        help="Include daily OHLCV and indicator series in market.daily",
    )
    ai_parser.add_argument(
        "--days",
        type=int,
        default=130,
        help="Number of daily bars to include when --include-daily is set",
    )

    args = parser.parse_args()
    config = load_config(args.config)
    service = PositionService(config)

    if args.command == "ai-context":
        cmd_ai_context(service, args)
        return

    service.init()

    if args.command == "init":
        cmd_init(service)
    elif args.command in {"open", "buy"}:
        cmd_buy(service, args)
    elif args.command == "transact":
        cmd_transact(service, args)
    elif args.command == "list":
        cmd_list(service)
    elif args.command == "validate":
        cmd_validate(service)


if __name__ == "__main__":
    main()
