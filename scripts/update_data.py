#!/usr/bin/env python3
"""
AKQuant 数据增量更新工具.

从 akshare 下载最新日线数据，增量合并到本地 Parquet 文件中.

用法:
    python scripts/update_data.py --data-dir ./data
    python scripts/update_data.py --data-dir ./data --symbols 000001,600000
    python scripts/update_data.py --data-dir ./data --workers 8
"""

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


def update_single_stock(
    code: str,
    data_dir: Path,
    end_date: str,
    start_date: str | None = None,
) -> tuple[str, bool, str]:
    """更新单只股票数据，返回 (code, success, message)。"""
    file_path = data_dir / f"{code}.parquet"

    try:
        if file_path.exists():
            df_existing = pd.read_parquet(file_path)
            if start_date is None:
                last_date = df_existing.index.max()
                # 只下载到昨天（今天的盘后数据可能尚未更新）
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
                new_start = (last_date + timedelta(days=1)).strftime("%Y%m%d")
                if new_start > yesterday:
                    return code, True, "already up-to-date"
            else:
                new_start = start_date
                # 读取旧的 symbol 和 name 信息
                if "symbol" in df_existing.columns:
                    symbol = df_existing["symbol"].iloc[0]
                    name = df_existing["name"].iloc[0] if "name" in df_existing.columns else ""
                else:
                    symbol = code
                    name = ""
        else:
            new_start = start_date or "20100101"
            symbol = code
            name = ""

        from akquant.utils import fetch_akshare_symbol

        df_new = fetch_akshare_symbol(code, new_start, end_date, adjust="qfq")

        if df_new.empty:
            return code, False, "no new data from akshare"

        # 标准化新数据
        if "date" in df_new.columns:
            df_new["date"] = pd.to_datetime(df_new["date"])
            df_new = df_new.set_index("date")

        # 只保留与原始数据一致的列，避免多余列污染
        if file_path.exists():
            keep_cols = [c for c in df_existing.columns if c in df_new.columns]
            df_new = df_new[keep_cols]
        else:
            # 新文件：只保留标准列
            std_cols = ["open", "close", "high", "low", "volume", "symbol", "name"]
            keep_cols = [c for c in std_cols if c in df_new.columns]
            df_new = df_new[keep_cols]

        # 设置 symbol 和 name 列
        if not file_path.exists() or "symbol" not in df_existing.columns:
            df_new["symbol"] = symbol
            if name:
                df_new["name"] = name

        if file_path.exists():
            df_merged = pd.concat([df_existing, df_new])
            df_merged = df_merged[~df_merged.index.duplicated(keep="last")]
            df_merged.sort_index(inplace=True)
        else:
            df_merged = df_new.sort_index()

        df_merged.to_parquet(file_path, compression="snappy")
        rows_added = len(df_new) if not file_path.exists() else len(df_merged) - len(df_existing)
        return code, True, f"+{max(rows_added, 0)} rows"

    except Exception as e:
        return code, False, str(e)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AKQuant 数据增量更新工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python scripts/update_data.py --data-dir ./data\n"
            "  python scripts/update_data.py --data-dir ./data --symbols 000001,600000\n"
            "  python scripts/update_data.py --data-dir ./data --workers 8\n"
        ),
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="./data",
        help="Parquet 数据目录路径 (默认: ./data)",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="指定更新的股票代码，逗号分隔 (默认: 全部)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="并行下载线程数 (默认: 4)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="强制指定起始日期，格式 YYYYMMDD (默认: 自动检测最后日期+1)",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    if not data_dir.exists():
        print(f"Error: data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    # 确定要更新的股票列表
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",")]
    else:
        symbols = sorted(f.stem for f in data_dir.glob("*.parquet"))

    if not symbols:
        print("No symbols to update.", file=sys.stderr)
        sys.exit(1)

    today = datetime.now().strftime("%Y%m%d")
    # end_date 使用昨天，确保盘后数据已更新
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    total = len(symbols)
    print(f"Updating {total} stocks (end={yesterday}, workers={args.workers})")

    success_count = 0
    skip_count = 0
    fail_count = 0
    failed_symbols = []

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                update_single_stock, code, data_dir, yesterday, args.start_date
            ): code
            for code in symbols
        }

        for i, future in enumerate(as_completed(futures), 1):
            code, ok, msg = future.result()
            status = "OK" if ok else "FAIL"
            if "up-to-date" in msg:
                status = "SKIP"
                skip_count += 1
            elif ok:
                success_count += 1
            else:
                fail_count += 1
                failed_symbols.append(code)

            if status != "SKIP" or i == total:
                print(f"[{i}/{total}] {code}: {status} ({msg})")

    print(f"\nDone: {success_count} updated, {skip_count} skipped, {fail_count} failed")
    if failed_symbols:
        print(f"Failed: {', '.join(failed_symbols[:20])}")


if __name__ == "__main__":
    main()
