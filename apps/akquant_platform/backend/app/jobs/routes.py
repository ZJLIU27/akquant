"""FastAPI routes for job status."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..jobs.runner import JobRunner

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

_runner: JobRunner | None = None


def _get_runner() -> JobRunner:
    global _runner
    if _runner is None:
        _runner = JobRunner()
    return _runner


@router.get("/{job_id}")
def get_job(job_id: str) -> dict:
    runner = _get_runner()
    job = runner.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
