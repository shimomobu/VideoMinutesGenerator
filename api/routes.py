"""FastAPI エンドポイント定義"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse

from . import service
from .models import CreateJobResponse, JobStatus, JobStatusResponse

router = APIRouter()

_SUPPORTED_SUFFIXES = {".mp4", ".mov", ".mkv", ".wav", ".mp3", ".m4a"}
_ALLOWED_RESULT_FORMATS = {"json", "md"}
_MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB
_CHUNK_SIZE = 1 * 1024 * 1024  # 1 MB
_UPLOAD_DIR = Path("data/upload")


@router.post("/jobs", status_code=202, response_model=CreateJobResponse)
async def create_job(
    file: UploadFile,
    title: str = Form(...),
    datetime: str = Form(...),
    participants: str = Form(...),
) -> CreateJobResponse:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"対応していないファイル形式です: {suffix}")

    participants_list = [p.strip() for p in participants.split(",") if p.strip()]

    job_id = f"api_{uuid.uuid4().hex[:12]}"
    upload_dir = _UPLOAD_DIR / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / f"original{suffix}"

    def _cleanup_upload() -> None:
        upload_path.unlink(missing_ok=True)
        try:
            upload_dir.rmdir()
        except OSError:
            pass

    written = 0
    too_large = False
    try:
        with open(upload_path, "wb") as f:
            while True:
                chunk = await file.read(_CHUNK_SIZE)
                if not chunk:
                    break
                written += len(chunk)
                if written > _MAX_UPLOAD_BYTES:
                    too_large = True
                    break
                f.write(chunk)
    except Exception:
        _cleanup_upload()
        raise HTTPException(status_code=500, detail="ファイルの保存中にエラーが発生しました")

    if too_large:
        _cleanup_upload()
        raise HTTPException(status_code=413, detail="ファイルサイズが上限（2 GB）を超えています")

    service.create_job(job_id)
    service.submit_job(
        job_id=job_id,
        upload_path=upload_path,
        title=title,
        datetime_str=datetime,
        participants=participants_list,
    )

    return CreateJobResponse(job_id=job_id)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str) -> JobStatusResponse:
    snapshot = service.get_job_snapshot(job_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")
    status, _, error = snapshot
    return JobStatusResponse(job_id=job_id, status=status, error=error)


@router.get("/jobs/{job_id}/result", response_model=None)
def get_job_result(job_id: str, format: str = "json") -> JSONResponse | PlainTextResponse:
    if format not in _ALLOWED_RESULT_FORMATS:
        raise HTTPException(status_code=400, detail=f"未対応のフォーマットです: {format}（json / md を指定してください）")

    snapshot = service.get_job_snapshot(job_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")

    status, result, _ = snapshot
    if status != JobStatus.completed:
        raise HTTPException(status_code=409, detail=f"結果がまだ準備できていません: {status}")
    if result is None:
        raise HTTPException(status_code=500, detail="結果データが存在しません")

    if format == "md":
        md_path = Path(result.markdown_path)
        if not md_path.exists():
            raise HTTPException(status_code=404, detail="結果ファイルが見つかりません")
        return PlainTextResponse(content=md_path.read_text(encoding="utf-8"), media_type="text/markdown; charset=utf-8")

    json_path = Path(result.json_path)
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="結果ファイルが見つかりません")
    json_data = json.loads(json_path.read_text(encoding="utf-8"))
    return JSONResponse(content=json_data)
