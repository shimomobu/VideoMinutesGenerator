"""動画ファイル取込・バリデーション・ジョブID発行"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

SUPPORTED_FORMATS = {"mp4", "mov", "mkv"}


class ValidationError(Exception):
    pass


class IngestResult(BaseModel):
    file_path: str
    file_format: str
    file_size_bytes: int


def validate_video_file(file_path: str | Path) -> IngestResult:
    path = Path(file_path)

    if not path.exists():
        raise ValidationError(f"ファイルが存在しません: {path.name}")

    ext = path.suffix.lstrip(".").lower()
    if not ext:
        raise ValidationError(f"拡張子がありません: {path.name}")

    if ext not in SUPPORTED_FORMATS:
        raise ValidationError(
            f"非対応の形式です: {ext}（対応形式: {', '.join(sorted(SUPPORTED_FORMATS))}）"
        )

    return IngestResult(
        file_path=str(path),
        file_format=ext,
        file_size_bytes=path.stat().st_size,
    )


class JobMeta(BaseModel):
    job_id: str
    executed_at: str
    input_file_path: str


def create_job(
    ingest_result: IngestResult,
    work_dir: str | Path = "data/work",
) -> JobMeta:
    job_id = _generate_job_id()
    job_dir = Path(work_dir) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    meta = JobMeta(
        job_id=job_id,
        executed_at=datetime.now(timezone.utc).isoformat(),
        input_file_path=ingest_result.file_path,
    )
    (job_dir / "job_meta.json").write_text(
        meta.model_dump_json(indent=2), encoding="utf-8"
    )
    return meta


def _generate_job_id() -> str:
    now = datetime.now(timezone.utc)
    suffix = uuid.uuid4().hex[:6]
    return f"job_{now.strftime('%Y%m%d_%H%M%S')}_{suffix}"
