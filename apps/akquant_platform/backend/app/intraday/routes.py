"""FastAPI routes for data update jobs."""

from __future__ import annotations

import threading
from typing import Any

from fastapi import APIRouter, HTTPException

from ..config import PlatformConfig, load_config
from ..intraday.cache import IntradayCache, download_intraday
from ..jobs.runner import JobRunner
from ..positions.service import PositionService

router = APIRouter(prefix="/api/data", tags=["data"])

_job_runner: JobRunner | None = None
_service: PositionService | None = None


def _get_job_runner() -> JobRunner:
    global _job_runner
    if _job_runner is None:
        _job_runner = JobRunner()
    return _job_runner


def _get_service() -> PositionService:
    global _service
    if _service is None:
        _service = PositionService(load_config())
        _service.init()
    return _service


def _run_intraday_update(job_id: str, symbols: list[str], config: PlatformConfig) -> None:
    """Background thread for intraday data update."""
    runner = _get_job_runner()
    runner.start_job(job_id)
    cache = IntradayCache(config.intraday_data_dir)
    results: dict[str, str] = {}
    try:
        for symbol in symbols:
            df = download_intraday(symbol)
            if df is not None:
                cache.save_intraday(symbol, df)
                results[symbol] = "ok"
            elif cache.get_intraday_df(symbol) is not None:
                results[symbol] = "cached"
            else:
                results[symbol] = "failed"
        cache.cleanup_old_cache()
        runner.finish_job(job_id, result=results)
    except Exception as e:
        runner.finish_job(job_id, error=str(e))


@router.post("/update-intraday")
def trigger_intraday_update(body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Trigger intraday data update for all open positions or specified symbols."""
    runner = _get_job_runner()

    # Check for already running job
    existing = runner.find_running("intraday_update")
    if existing:
        return {"job_id": existing, "status": "already_running"}

    symbols = (body or {}).get("symbols")
    force = (body or {}).get("force", False)

    if not symbols:
        symbols = _get_service().get_open_symbols()

    if not symbols:
        return {"job_id": None, "status": "no_symbols"}

    # Filter to symbols that need refresh (unless force)
    config = load_config()
    if not force:
        cache = IntradayCache(config.intraday_data_dir)
        symbols = [s for s in symbols if not cache.is_cache_valid(s)]

    if not symbols:
        return {"job_id": None, "status": "all_cached"}

    job_id = runner.create_job("intraday_update", {"symbols": symbols, "force": force})

    thread = threading.Thread(target=_run_intraday_update, args=(job_id, symbols, config), daemon=True)
    thread.start()

    return {"job_id": job_id, "status": "started"}


@router.post("/update-daily")
def trigger_daily_update(body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Trigger daily data update via scripts/update_data.py."""
    runner = _get_job_runner()

    existing = runner.find_running("daily_update")
    if existing:
        return {"job_id": existing, "status": "already_running"}

    symbols = (body or {}).get("symbols")
    config = load_config()
    params: dict[str, Any] = {}
    if symbols:
        params["symbols"] = symbols

    job_id = runner.create_job("daily_update", params)

    def _run():
        import subprocess
        import sys
        runner.start_job(job_id)
        cmd = [sys.executable, "scripts/update_data.py", "--data-dir", config.daily_data_dir]
        if symbols:
            cmd.extend(["--symbols", ",".join(symbols)])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            runner.finish_job(job_id, result={"exit_code": result.returncode, "stdout": result.stdout[-2000:]})
        except Exception as e:
            runner.finish_job(job_id, error=str(e))

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return {"job_id": job_id, "status": "started"}


@router.get("/status")
def data_status() -> dict[str, Any]:
    """Return data status for all open positions."""
    svc = _get_service()
    positions = svc.list_positions()
    status_list: list[dict[str, Any]] = []
    for p in positions.positions:
        if p.status == "open":
            status_list.append({
                "symbol": p.symbol,
                "name": p.name,
                "latest_price": p.latest_price,
                "price_source": p.price_source,
                "market_value": p.market_value,
            })
    return {"positions": status_list, "total_market_value": positions.total_market_value}
