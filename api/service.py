"""ジョブ状態管理とバックグラウンド実行"""
from __future__ import annotations

import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from vmg.asr import WhisperLocalProvider
from vmg.common.config import load_config
from vmg.formatter import StandardFormatter
from vmg.pipeline import PipelineResult, run_pipeline

from .models import JobStatus

_jobs: dict[str, "JobRecord"] = {}
_lock = threading.Lock()


@dataclass
class JobRecord:
    job_id: str
    status: JobStatus = field(default=JobStatus.pending)
    result: PipelineResult | None = None
    error: str | None = None


def create_job(job_id: str) -> JobRecord:
    record = JobRecord(job_id=job_id)
    with _lock:
        _jobs[job_id] = record
    return record


def get_job(job_id: str) -> JobRecord | None:
    with _lock:
        return _jobs.get(job_id)


def get_job_snapshot(job_id: str) -> tuple[JobStatus, PipelineResult | None, str | None] | None:
    """status・result・error をロック内でアトミックに取得する"""
    with _lock:
        rec = _jobs.get(job_id)
        if rec is None:
            return None
        return rec.status, rec.result, rec.error


def submit_job(
    job_id: str,
    file_bytes: bytes,
    file_suffix: str,
    title: str,
    datetime_str: str,
    participants: list[str],
    on_complete: Callable[[], None] | None = None,
) -> None:
    """バックグラウンドスレッドでパイプラインを実行する"""

    def _run() -> None:
        with _lock:
            _jobs[job_id].status = JobStatus.running

        tmp_path: Path | None = None
        try:
            config = load_config()
            asr_provider = WhisperLocalProvider(
                model_name=config.whisper_model,
                initial_prompt=config.whisper_initial_prompt,
            )
            formatter_provider = StandardFormatter()

            with tempfile.NamedTemporaryFile(suffix=file_suffix, delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = Path(tmp.name)

            result = run_pipeline(
                input_path=tmp_path,
                title=title,
                datetime_str=datetime_str,
                participants=participants,
                asr_provider=asr_provider,
                formatter_provider=formatter_provider,
                model=config.llm_model,
                base_url=config.ollama_base_url,
                timeout_seconds=config.llm_timeout_seconds,
                max_retries=config.llm_max_retries,
                correction_rules=config.correction_rules,
                correction_enabled=config.correction_enabled,
                job_id=job_id,
            )

            with _lock:
                _jobs[job_id].status = JobStatus.completed
                _jobs[job_id].result = result

        except Exception as e:
            with _lock:
                _jobs[job_id].status = JobStatus.failed
                _jobs[job_id].error = str(e)

        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)
            if on_complete is not None:
                on_complete()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
