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
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


def _first_valid_value(df: pd.DataFrame, column: str, default: str = "") -> str:
    """Return the first non-null value from a column as string."""
    if column not in df.columns:
        return default
    values = df[column].dropna()
    if values.empty:
        return default
    return str(values.iloc[0])


def _stock_metadata(df: pd.DataFrame, code: str) -> tuple[str, str]:
    """Get stock symbol/name metadata from an existing local data file."""
    symbol = _first_valid_value(df, "symbol", code)
    name = _first_valid_value(df, "name", "")
    return symbol, name


def _fill_metadata(df: pd.DataFrame, symbol: str, name: str) -> bool:
    """Fill missing symbol/name values in-place and report whether changed."""
    changed = False
    if "symbol" in df.columns:
        mask = df["symbol"].isna()
        if mask.any():
            df.loc[mask, "symbol"] = symbol
            changed = True
    if "name" in df.columns and name:
        mask = df["name"].isna()
        if mask.any():
            df.loc[mask, "name"] = name
            changed = True
    return changed


def _normalize_new_volume(df_new: pd.DataFrame) -> bool:
    """Convert AKShare daily share volume to the local lot-based unit."""
    if "volume" not in df_new.columns:
        return False

    new_volume = pd.to_numeric(df_new["volume"], errors="coerce").dropna()
    if new_volume.empty:
        return False

    # stock_zh_a_daily returns shares, while the local parquet data uses lots.
    df_new["volume"] = pd.to_numeric(df_new["volume"], errors="coerce") / 100
    return True


def _repair_volume_unit_spikes(df: pd.DataFrame) -> int:
    """Repair rows that were appended in shares to a lot-based volume series."""
    if "volume" not in df.columns:
        return 0

    volumes = pd.to_numeric(df["volume"], errors="coerce").copy()
    repaired_count = 0
    history: list[float] = []
    repaired_values = volumes.copy()

    for idx, value in volumes.items():
        if pd.isna(value) or value <= 0:
            continue

        if len(history) >= 20:
            baseline = pd.Series(history[-60:]).median()
            fixed_value = value / 100
            fixed_ratio = fixed_value / baseline
            if baseline > 0 and value / baseline >= 50 and 0.2 <= fixed_ratio <= 5:
                repaired_values.loc[idx] = fixed_value
                value = fixed_value
                repaired_count += 1

        history.append(float(value))

    if repaired_count:
        df["volume"] = repaired_values
    return repaired_count


def update_single_stock(
    code: str,
    data_dir: Path,
    end_date: str,
    start_date: str | None = None,
) -> tuple[str, bool, str]:
    """更新单只股票数据，返回 (code, success, message)。"""
    file_path = data_dir / f"{code}.parquet"
    had_file = file_path.exists()

    try:
        if had_file:
            df_existing = pd.read_parquet(file_path)
            symbol, name = _stock_metadata(df_existing, code)
            metadata_repaired = _fill_metadata(df_existing, symbol, name)
            volume_repairs = _repair_volume_unit_spikes(df_existing)
            if start_date is None:
                last_date = df_existing.index.max()
                new_start = (last_date + timedelta(days=1)).strftime("%Y%m%d")
                if new_start > end_date:
                    if metadata_repaired or volume_repairs:
                        df_existing.to_parquet(file_path, compression="snappy")
                        if metadata_repaired and not volume_repairs:
                            return code, True, "metadata repaired"
                        repairs = []
                        if metadata_repaired:
                            repairs.append("metadata")
                        if volume_repairs:
                            repairs.append(f"volume x{volume_repairs}")
                        return code, True, f"repaired {'/'.join(repairs)}"
                    return code, True, "already up-to-date"
            else:
                new_start = start_date
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
        if had_file:
            keep_cols = list(df_existing.columns)
        else:
            # 新文件：只保留标准列
            std_cols = ["open", "close", "high", "low", "volume", "symbol", "name"]
            keep_cols = [c for c in std_cols if c in df_new.columns]
            for col in ("symbol", "name"):
                if col not in keep_cols:
                    keep_cols.append(col)

        _normalize_new_volume(df_new)

        # 设置 symbol 和 name 列
        if "symbol" in keep_cols and (
            "symbol" not in df_new.columns or df_new["symbol"].isna().any()
        ):
            df_new["symbol"] = symbol
        if "name" in keep_cols and (
            "name" not in df_new.columns or df_new["name"].isna().any()
        ):
            df_new["name"] = name

        missing_cols = [c for c in keep_cols if c not in df_new.columns]
        if missing_cols:
            return code, False, f"new data missing columns: {missing_cols}"
        df_new = df_new[keep_cols]

        if had_file:
            df_merged = pd.concat([df_existing, df_new])
            df_merged = df_merged[~df_merged.index.duplicated(keep="last")]
            df_merged.sort_index(inplace=True)
        else:
            df_merged = df_new.sort_index()

        df_merged.to_parquet(file_path, compression="snappy")
        rows_added = len(df_merged) - len(df_existing) if had_file else len(df_new)
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
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="指定结束日期，格式 YYYYMMDD (默认: 今天)",
    )
    parser.add_argument(
        "--until-yesterday",
        action="store_true",
        help="只更新到昨天，适合需要避开当天盘后未完成数据的场景",
    )
    parser.add_argument(
        "--progress-seconds",
        type=float,
        default=10.0,
        help="无任务完成时打印进度心跳的间隔秒数 (默认: 10)",
    )
    parser.add_argument(
        "--print-skips",
        action="store_true",
        help="打印每一只已是最新的股票，默认只定期打印汇总进度",
    )
    args = parser.parse_args()

    if args.end_date and args.until_yesterday:
        print(
            "Error: --end-date and --until-yesterday cannot be used together",
            file=sys.stderr,
        )
        sys.exit(1)

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
    if args.until_yesterday:
        end_date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    else:
        end_date = args.end_date or today

    total = len(symbols)
    print(
        f"Updating {total} stocks (end={end_date}, workers={args.workers})",
        flush=True,
    )

    success_count = 0
    skip_count = 0
    fail_count = 0
    failed_symbols = []
    completed_count = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                update_single_stock, code, data_dir, end_date, args.start_date
            ): code
            for code in symbols
        }

        pending = set(futures)
        while pending:
            done, pending = wait(
                pending,
                timeout=max(args.progress_seconds, 0.1),
                return_when=FIRST_COMPLETED,
            )
            if not done:
                print(
                    "[progress] "
                    f"{completed_count}/{total} done, "
                    f"{len(pending)} pending "
                    f"({success_count} updated, {skip_count} skipped, "
                    f"{fail_count} failed)",
                    flush=True,
                )
                continue

            for future in done:
                code, ok, msg = future.result()
                completed_count += 1
                status = "OK" if ok else "FAIL"
                if "up-to-date" in msg:
                    status = "SKIP"
                    skip_count += 1
                elif ok:
                    success_count += 1
                else:
                    fail_count += 1
                    failed_symbols.append(code)

                should_print = (
                    status != "SKIP"
                    or args.print_skips
                    or completed_count == total
                    or completed_count % 100 == 0
                )
                if should_print:
                    print(
                        f"[{completed_count}/{total}] {code}: {status} ({msg})",
                        flush=True,
                    )

    print(
        f"\nDone: {success_count} updated, {skip_count} skipped, {fail_count} failed",
        flush=True,
    )
    if failed_symbols:
        print(f"Failed: {', '.join(failed_symbols[:20])}", flush=True)


if __name__ == "__main__":
    main()
