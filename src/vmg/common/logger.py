"""構造化ロガー — JSON Lines 形式で logs/{job_id}.jsonl に追記する"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class StructuredLogger:
    def __init__(self, job_id: str, log_dir: str | Path = "logs") -> None:
        self.job_id = job_id
        self._log_path = Path(log_dir) / f"{job_id}.jsonl"
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        stage: str,
        level: str,
        message: str,
        duration_ms: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "job_id": self.job_id,
            "stage": stage,
            "level": level,
            "message": message,
            "duration_ms": duration_ms,
            "extra": extra if extra is not None else {},
        }
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def info(self, stage: str, message: str, duration_ms: int | None = None, extra: dict[str, Any] | None = None) -> None:
        self.log(stage, "INFO", message, duration_ms, extra)

    def warning(self, stage: str, message: str, duration_ms: int | None = None, extra: dict[str, Any] | None = None) -> None:
        self.log(stage, "WARNING", message, duration_ms, extra)

    def error(self, stage: str, message: str, duration_ms: int | None = None, extra: dict[str, Any] | None = None) -> None:
        self.log(stage, "ERROR", message, duration_ms, extra)
