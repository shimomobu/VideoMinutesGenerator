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

    file_bytes = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(file_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="ファイルサイズが上限（2 GB）を超えています")

    participants_list = [p.strip() for p in participants.split(",") if p.strip()]

    job_id = f"api_{uuid.uuid4().hex[:12]}"
    service.create_job(job_id)
    service.submit_job(
        job_id=job_id,
        file_bytes=file_bytes,
        file_suffix=suffix,
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
        md_text = Path(result.markdown_path).read_text(encoding="utf-8")
        return PlainTextResponse(content=md_text, media_type="text/markdown; charset=utf-8")

    json_data = json.loads(Path(result.json_path).read_text(encoding="utf-8"))
    return JSONResponse(content=json_data)
