#!/usr/bin/env python3
"""AKQuant 持仓管理 CLI.

用法:
    python scripts/positions_cli.py init
    python scripts/positions_cli.py buy --symbol 000001 --name 平安银行 --date 2026-05-08 --quantity 1000 --price 10.50 --fee 5
    python scripts/positions_cli.py sell --symbol 000001 --date 2026-05-10 --quantity 500 --price 11.00 --fee 5
    python scripts/positions_cli.py list
    python scripts/positions_cli.py validate
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add backend to path so we can import app modules
_backend_dir = Path(__file__).resolve().parents[1] / "apps" / "akquant_platform" / "backend"
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
    print(f"Buy transaction added: {txn.id[:8]}... {args.symbol} {args.quantity}@{args.price}")


def cmd_sell(service: PositionService, args: argparse.Namespace) -> None:
    txn = service.add_sell(
        symbol=args.symbol,
        trade_date=args.date,
        quantity=args.quantity,
        price=args.price,
        fee=args.fee,
        notes=args.notes,
    )
    if txn is None:
        print(f"Error: cannot sell {args.quantity} of {args.symbol} (insufficient holdings or position not found)", file=sys.stderr)
        sys.exit(1)
    print(f"Sell transaction added: {txn.id[:8]}... {args.symbol} {args.quantity}@{args.price}")


def cmd_list(service: PositionService) -> None:
    result = service.list_positions()
    if not result.positions:
        print("No positions.")
        return

    print(f"{'Symbol':<8} {'Name':<10} {'Qty':>6} {'AvgCost':>10} {'Price':>10} {'MV':>12} {'PnL':>12} {'Weight':>8} {'Status':<8}")
    print("-" * 94)
    for p in result.positions:
        price_str = f"{p.latest_price:.2f}" if p.latest_price else "N/A"
        mv_str = f"{p.market_value:.2f}" if p.market_value else "0.00"
        pnl = p.realized_pnl + p.unrealized_pnl
        print(
            f"{p.symbol:<8} {p.name:<10} {p.remaining_quantity:>6} "
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AKQuant 持仓管理 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", type=str, default=None, help="Platform config file path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    subparsers.add_parser("init", help="Initialize positions file")

    # buy
    buy_parser = subparsers.add_parser("buy", help="Add a buy transaction")
    buy_parser.add_argument("--symbol", required=True)
    buy_parser.add_argument("--name", default="")
    buy_parser.add_argument("--date", required=True)
    buy_parser.add_argument("--quantity", type=int, required=True)
    buy_parser.add_argument("--price", type=float, required=True)
    buy_parser.add_argument("--fee", type=float, default=0)
    buy_parser.add_argument("--notes", default="")

    # sell
    sell_parser = subparsers.add_parser("sell", help="Add a sell transaction")
    sell_parser.add_argument("--symbol", required=True)
    sell_parser.add_argument("--date", required=True)
    sell_parser.add_argument("--quantity", type=int, required=True)
    sell_parser.add_argument("--price", type=float, required=True)
    sell_parser.add_argument("--fee", type=float, default=0)
    sell_parser.add_argument("--notes", default="")

    # list
    subparsers.add_parser("list", help="List all positions")

    # validate
    subparsers.add_parser("validate", help="Validate positions file")

    args = parser.parse_args()
    config = load_config(args.config)
    service = PositionService(config)
    service.init()

    if args.command == "init":
        cmd_init(service)
    elif args.command == "buy":
        cmd_buy(service, args)
    elif args.command == "sell":
        cmd_sell(service, args)
    elif args.command == "list":
        cmd_list(service)
    elif args.command == "validate":
        cmd_validate(service)


if __name__ == "__main__":
    main()
