"""音声抽出・バリデーション — 動画から 16kHz モノラル WAV を生成し、有効性を検証する"""
from __future__ import annotations

import subprocess
import wave
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from vmg.ingest import IngestResult


class ProcessingError(Exception):
    pass


class PreprocessResult(BaseModel):
    audio_path: str
    job_id: str
    duration_seconds: float | None = None
    sample_rate: int | None = None


def extract_audio(
    ingest_result: IngestResult,
    job_id: str,
    work_dir: str | Path = "data/work",
) -> PreprocessResult:
    output_dir = Path(work_dir) / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "audio.wav"

    cmd = [
        "ffmpeg",
        "-y",
        "-i", ingest_result.file_path,
        "-ar", "16000",
        "-ac", "1",
        "-f", "wav",
        str(output_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, check=False)
    except FileNotFoundError:
        raise ProcessingError(
            "ffmpeg が見つかりません。ffmpeg をインストールしてください。"
        )

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise ProcessingError(
            f"FFmpeg の実行に失敗しました（終了コード: {result.returncode}）: {stderr}"
        )

    return PreprocessResult(audio_path=str(output_path), job_id=job_id)


def validate_audio(
    audio_path: str | Path,
    job_id: str,
    logger: Any | None = None,
) -> PreprocessResult:
    path = Path(audio_path)

    try:
        with wave.open(str(path), "rb") as wf:
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            duration_seconds = float(n_frames) / sample_rate if sample_rate > 0 else 0.0
            raw_data = wf.readframes(n_frames)
    except (wave.Error, EOFError) as e:
        raise ProcessingError(f"WAV ファイルが破損しています: {e}") from e
    except OSError as e:
        raise ProcessingError(f"WAV ファイルを開けません: {e}") from e

    if duration_seconds < 5.0 and logger is not None:
        logger.warning(
            stage="preprocess",
            message=f"音声が短すぎます: {duration_seconds:.1f} 秒（5秒未満）",
        )

    if raw_data and all(b == 0 for b in raw_data) and logger is not None:
        logger.warning(
            stage="preprocess",
            message="無音ファイルが検出されました",
        )

    return PreprocessResult(
        audio_path=str(path),
        job_id=job_id,
        duration_seconds=duration_seconds,
        sample_rate=sample_rate,
    )
