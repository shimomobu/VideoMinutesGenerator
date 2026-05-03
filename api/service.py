"""ジョブ状態管理とバックグラウンド実行"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from vmg.asr import WhisperLocalProvider
from vmg.common.config import load_config
from vmg.formatter import StandardFormatter
from vmg.pipeline import PipelineResult, run_pipeline

from .models import JobStatus
from .repository import JobRepository

_DEFAULT_DB_PATH = Path("data/api/jobs.db")

_repo: JobRepository | None = None
_repo_lock = threading.Lock()


@dataclass
class JobRecord:
    job_id: str
    status: JobStatus = field(default=JobStatus.pending)
    error: str | None = None


def init_repo(db_path: str | Path) -> None:
    """リポジトリを指定パスで初期化する（テスト時の DB 差し替えにも使用）"""
    global _repo
    with _repo_lock:
        _repo = JobRepository(db_path)


def _get_repo() -> JobRepository:
    global _repo
    if _repo is None:
        with _repo_lock:
            if _repo is None:
                _repo = JobRepository(_DEFAULT_DB_PATH)
    return _repo


def create_job(job_id: str) -> JobRecord:
    _get_repo().insert(job_id)
    return JobRecord(job_id=job_id, status=JobStatus.pending)


def get_job(job_id: str) -> JobRecord | None:
    row = _get_repo().get(job_id)
    if row is None:
        return None
    return JobRecord(
        job_id=row["job_id"],
        status=JobStatus(row["status"]),
        error=row.get("error"),
    )


def get_job_snapshot(job_id: str) -> tuple[JobStatus, PipelineResult | None, str | None] | None:
    """status・result・error をアトミックに取得する"""
    row = _get_repo().get(job_id)
    if row is None:
        return None
    status = JobStatus(row["status"])
    error = row.get("error")
    result: PipelineResult | None = None
    if status == JobStatus.completed and row.get("markdown_path"):
        result = PipelineResult(
            job_id=job_id,
            markdown_path=row["markdown_path"],
            json_path=row["json_path"] or "",
            manifest_path=row["manifest_path"] or "",
        )
    return status, result, error


def submit_job(
    job_id: str,
    upload_path: Path,
    title: str,
    datetime_str: str,
    participants: list[str],
    on_complete: Callable[[], None] | None = None,
) -> None:
    """バックグラウンドスレッドでパイプラインを実行する"""

    def _run() -> None:
        repo = _get_repo()
        repo.set_running(job_id)

        try:
            config = load_config()
            asr_provider = WhisperLocalProvider(
                model_name=config.whisper_model,
                initial_prompt=config.whisper_initial_prompt,
            )
            formatter_provider = StandardFormatter()

            result = run_pipeline(
                input_path=upload_path,
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
                work_dir=config.paths.work_dir,
                output_dir=config.paths.output_dir,
                log_dir=config.paths.log_dir,
            )

            repo.set_completed(
                job_id,
                str(Path(result.markdown_path).resolve()),
                str(Path(result.json_path).resolve()),
                str(Path(result.manifest_path).resolve()),
            )

        except Exception as e:
            repo.set_failed(job_id, str(e))

        finally:
            upload_path.unlink(missing_ok=True)
            try:
                upload_path.parent.rmdir()
            except OSError:
                pass
            if on_complete is not None:
                on_complete()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
