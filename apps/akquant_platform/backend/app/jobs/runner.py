"""SQLite-backed job runner for async tasks (data updates, etc.)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    params TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    error TEXT,
    result TEXT
);
"""


class JobRunner:
    """Simple SQLite job tracker for background tasks."""

    def __init__(self, db_path: str | Path = "workspace/jobs.db") -> None:
        self._db = Path(db_path)
        self._db.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db))
        conn.row_factory = sqlite3.Row
        return conn

    def create_job(self, job_type: str, params: dict[str, Any] | None = None) -> str:
        """Create a new job and return its ID."""
        job_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs (job_id, job_type, params, created_at) VALUES (?, ?, ?, ?)",
                (job_id, job_type, json.dumps(params or {}), now),
            )
        return job_id

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get job status by ID."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return dict(row)

    def find_running(self, job_type: str) -> str | None:
        """Find a running job of the given type, if any."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT job_id FROM jobs WHERE job_type = ? AND status = 'running' ORDER BY created_at DESC LIMIT 1",
                (job_type,),
            ).fetchone()
        return row["job_id"] if row else None

    def start_job(self, job_id: str) -> None:
        """Mark job as running."""
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status = 'running', started_at = ? WHERE job_id = ?",
                (now, job_id),
            )

    def finish_job(self, job_id: str, result: Any = None, error: str | None = None) -> None:
        """Mark job as success or failed."""
        now = datetime.now().isoformat()
        status = "failed" if error else "success"
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, finished_at = ?, result = ?, error = ? WHERE job_id = ?",
                (status, now, json.dumps(result) if result else None, error, job_id),
            )

    def list_jobs(self, job_type: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        """List recent jobs."""
        with self._connect() as conn:
            if job_type:
                rows = conn.execute(
                    "SELECT * FROM jobs WHERE job_type = ? ORDER BY created_at DESC LIMIT ?",
                    (job_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]
