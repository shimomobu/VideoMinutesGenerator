"""pipeline — 全ステージを順番に実行する Pipeline Runner（スキップ機構付き）"""
from __future__ import annotations

import functools
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from vmg.analysis.extractor import extract
from vmg.analysis.input_builder import build_prompt
from vmg.analysis.postprocess import postprocess as run_postprocess
from vmg.analysis.validator import validate as validate_analysis
from vmg.asr import save_transcript
from vmg.asr.corrector import TranscriptCorrector
from vmg.common.interfaces import ASRProvider, FormatterProvider
from vmg.common.logger import StructuredLogger
from vmg.common.models import AnalysisResult, MeetingInfo, MinutesOutput, OutputManifest, Transcript
from vmg.export import write_json, write_manifest, write_markdown
from vmg.ingest import create_job, validate_input_file
from vmg.preprocess import extract_audio, validate_audio


class PipelineError(Exception):
    def __init__(self, stage: str, cause: Exception) -> None:
        self.stage = stage
        self.cause = cause
        super().__init__(f"[{stage}] パイプラインが失敗しました: {cause}")


class PipelineResult(BaseModel):
    job_id: str
    markdown_path: str
    json_path: str
    manifest_path: str


def run_pipeline(
    input_path: str | Path,
    title: str,
    datetime_str: str,
    participants: list[str],
    asr_provider: ASRProvider,
    formatter_provider: FormatterProvider,
    timeout_seconds: int,
    model: str = "gemma4",
    base_url: str = "http://localhost:11434/v1",
    work_dir: str | Path = "data/work",
    output_dir: str | Path = "data/output",
    log_dir: str | Path = "logs",
    language: str = "ja",
    force: bool = False,
    job_id: str | None = None,
    max_retries: int = 3,
    correction_rules: list[dict] | None = None,
    correction_enabled: bool = True,
) -> PipelineResult:
    input_path = Path(input_path)
    work_dir = Path(work_dir)
    output_dir = Path(output_dir)

    # --- Stage 1: ingest ---
    try:
        ingest_result = validate_input_file(input_path)
        job_meta = create_job(ingest_result, work_dir, forced_job_id=job_id)
    except Exception as e:
        raise PipelineError(stage="ingest", cause=e) from e

    logger = StructuredLogger(job_id=job_meta.job_id, log_dir=log_dir)

    # --- Stage 2: preprocess ---
    audio_wav = work_dir / job_meta.job_id / "audio.wav"
    if not force and audio_wav.exists():
        logger.info(stage="preprocess", message="audio.wav が存在するためスキップ")
        preprocess_result = _run(logger, "preprocess.validate", validate_audio, str(audio_wav), job_meta.job_id, logger)
    else:
        preprocess_result = _run(logger, "preprocess", extract_audio, ingest_result, job_meta.job_id, work_dir)
        preprocess_result = _run(logger, "preprocess.validate", validate_audio, preprocess_result.audio_path, job_meta.job_id, logger)

    # --- Stage 3: asr ---
    transcript_json = work_dir / job_meta.job_id / "transcript.json"
    if not force and transcript_json.exists():
        transcript = _try_load_json(transcript_json, Transcript, logger, "asr")
        if transcript is None:
            transcript = _run(logger, "asr", asr_provider.transcribe, preprocess_result.audio_path, language)
            _run(logger, "asr.save", save_transcript, transcript, job_meta.job_id, work_dir)
        else:
            logger.info(stage="asr", message="transcript.json が存在するためスキップ")
    else:
        transcript = _run(logger, "asr", asr_provider.transcribe, preprocess_result.audio_path, language)
        _run(logger, "asr.save", save_transcript, transcript, job_meta.job_id, work_dir)

    transcript = TranscriptCorrector(rules=correction_rules or [], enabled=correction_enabled).correct(transcript)

    # --- Stage 4: analysis ---
    analysis_json = work_dir / job_meta.job_id / "analysis.json"
    if not force and analysis_json.exists():
        analysis_result = _try_load_json(analysis_json, AnalysisResult, logger, "analysis")
        if analysis_result is None:
            analysis_result = _execute_analysis(logger, transcript, model, base_url, job_meta.job_id, work_dir, timeout_seconds, max_retries)
        else:
            logger.info(stage="analysis", message="analysis.json が存在するためスキップ")
    else:
        analysis_result = _execute_analysis(logger, transcript, model, base_url, job_meta.job_id, work_dir, timeout_seconds, max_retries)

    # --- Stage 5: formatter ---
    meeting_info = MeetingInfo(
        title=title,
        datetime=datetime_str,
        participants=participants,
        source_file=str(input_path),
        duration_seconds=int(preprocess_result.duration_seconds or 0),
    )
    md_content = _run(logger, "formatter", formatter_provider.format, meeting_info, analysis_result, transcript)

    # --- Stage 6: export ---
    generated_at = datetime.now(timezone.utc).isoformat()
    transcript_path = str(work_dir / job_meta.job_id / "transcript.json")

    minutes_output = MinutesOutput(
        meeting_info=meeting_info,
        analysis=analysis_result,
        transcript=transcript,
        manifest=OutputManifest(
            job_id=job_meta.job_id,
            generated_at=generated_at,
            files=["minutes.md", "minutes.json"],
            source_transcript=transcript_path,
        ),
    )

    md_path = _run(logger, "export.markdown", write_markdown, md_content, job_meta.job_id, output_dir)
    json_path = _run(logger, "export.json", write_json, minutes_output, job_meta.job_id, output_dir)
    manifest_path = _run(
        logger, "export.manifest", write_manifest,
        job_meta.job_id, generated_at, ["minutes.md", "minutes.json"],
        transcript_path, output_dir,
    )

    logger.info(stage="pipeline", message="パイプライン完了")
    return PipelineResult(
        job_id=job_meta.job_id,
        markdown_path=str(md_path),
        json_path=str(json_path),
        manifest_path=str(manifest_path),
    )


def _execute_analysis(
    logger: StructuredLogger,
    transcript: Transcript,
    model: str,
    base_url: str,
    job_id: str,
    work_dir: Path,
    timeout_seconds: int,
    max_retries: int = 3,
) -> AnalysisResult:
    chunks = _run(logger, "analysis.input_builder", build_prompt, transcript)
    if chunks:
        _extract = functools.partial(extract, logger=logger)
        raw_results = [_run(logger, "analysis.extractor", _extract, chunk, model, base_url, max_retries=max_retries, timeout_seconds=timeout_seconds) for chunk in chunks]
        validated_results = [_run(logger, "analysis.validator", validate_analysis, raw) for raw in raw_results]
        merged = _merge_validated(validated_results)
    else:
        merged = AnalysisResult(
            summary="", agenda=[], topics=[], decisions=[], pending_items=[], todos=[]
        )
    return _run(logger, "analysis.postprocess", run_postprocess, merged, job_id, work_dir)


def _try_load_json(path: Path, model_type: Any, logger: StructuredLogger, stage: str) -> Any:
    """JSONファイルを読み込む。失敗時は None を返す（破損ファイルは再実行扱い）"""
    try:
        return model_type.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(stage=stage, message=f"中間ファイルが破損しています。再実行します: {e}")
        return None


def _run(logger: StructuredLogger, stage: str, fn: Any, *args: Any, **kwargs: Any) -> Any:
    start = time.time()
    logger.info(stage=stage, message=f"{stage} 開始")
    try:
        result = fn(*args, **kwargs)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(stage=stage, message=f"{stage} 完了", duration_ms=duration_ms)
        return result
    except PipelineError:
        raise
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        logger.error(stage=stage, message=f"{stage} 失敗: {e}", duration_ms=duration_ms)
        raise PipelineError(stage=stage, cause=e) from e


def _merge_validated(results: list[AnalysisResult]) -> AnalysisResult:
    if not results:
        return AnalysisResult(
            summary="", agenda=[], topics=[], decisions=[], pending_items=[], todos=[]
        )
    first = results[0]
    return AnalysisResult(
        summary=first.summary,
        agenda=first.agenda,
        topics=[t for r in results for t in r.topics],
        decisions=[d for r in results for d in r.decisions],
        pending_items=[p for r in results for p in r.pending_items],
        todos=[t for r in results for t in r.todos],
    )
