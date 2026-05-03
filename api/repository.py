"""SQLite によるジョブ状態永続化"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .models import JobStatus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobRepository:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._write_lock, self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id        TEXT PRIMARY KEY,
                    status        TEXT NOT NULL DEFAULT 'pending',
                    created_at    TEXT NOT NULL,
                    started_at    TEXT,
                    finished_at   TEXT,
                    error         TEXT,
                    markdown_path TEXT,
                    json_path     TEXT,
                    manifest_path TEXT
                )
            """)

    def insert(self, job_id: str) -> None:
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs (job_id, status, created_at) VALUES (?, ?, ?)",
                (job_id, JobStatus.pending.value, _now()),
            )

    def set_running(self, job_id: str) -> None:
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status=?, started_at=? WHERE job_id=?",
                (JobStatus.running.value, _now(), job_id),
            )

    def set_completed(
        self,
        job_id: str,
        markdown_path: str,
        json_path: str,
        manifest_path: str,
    ) -> None:
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status=?, finished_at=?, markdown_path=?, json_path=?, manifest_path=? WHERE job_id=?",
                (JobStatus.completed.value, _now(), markdown_path, json_path, manifest_path, job_id),
            )

    def set_failed(self, job_id: str, error: str) -> None:
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status=?, finished_at=?, error=? WHERE job_id=?",
                (JobStatus.failed.value, _now(), error, job_id),
            )

    def get(self, job_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            return dict(row) if row else None

    def clear_all(self) -> None:
        """テスト用: 全ジョブを削除する"""
        with self._write_lock, self._connect() as conn:
            conn.execute("DELETE FROM jobs")
