"""Tests for job runner."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.jobs.runner import JobRunner


@pytest.fixture
def runner(tmp_path: Path) -> JobRunner:
    return JobRunner(tmp_path / "jobs.db")


def test_create_job(runner: JobRunner):
    job_id = runner.create_job("intraday_update", {"symbols": ["000001"]})
    assert job_id
    job = runner.get_job(job_id)
    assert job is not None
    assert job["job_type"] == "intraday_update"
    assert job["status"] == "queued"


def test_start_and_finish(runner: JobRunner):
    job_id = runner.create_job("test")
    runner.start_job(job_id)
    job = runner.get_job(job_id)
    assert job["status"] == "running"
    assert job["started_at"] is not None

    runner.finish_job(job_id, result={"rows": 10})
    job = runner.get_job(job_id)
    assert job["status"] == "success"
    assert job["finished_at"] is not None


def test_finish_with_error(runner: JobRunner):
    job_id = runner.create_job("test")
    runner.start_job(job_id)
    runner.finish_job(job_id, error="connection failed")
    job = runner.get_job(job_id)
    assert job["status"] == "failed"
    assert job["error"] == "connection failed"


def test_find_running(runner: JobRunner):
    j1 = runner.create_job("intraday_update")
    runner.start_job(j1)
    j2 = runner.create_job("intraday_update")

    found = runner.find_running("intraday_update")
    assert found == j1


def test_find_running_none(runner: JobRunner):
    assert runner.find_running("nonexistent") is None


def test_list_jobs(runner: JobRunner):
    runner.create_job("type_a")
    runner.create_job("type_b")
    runner.create_job("type_a")
    jobs = runner.list_jobs()
    assert len(jobs) == 3

    a_jobs = runner.list_jobs("type_a")
    assert len(a_jobs) == 2


def test_nonexistent_job(runner: JobRunner):
    assert runner.get_job("nonexistent") is None
