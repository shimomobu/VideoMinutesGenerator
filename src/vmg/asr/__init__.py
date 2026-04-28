"""音声認識 (ASR) — WhisperLocalProvider と transcript.json 入出力"""
from __future__ import annotations

from pathlib import Path

from vmg.common.interfaces import ASRProvider
from vmg.common.models import Transcript, TranscriptSegment


def seconds_to_hms(seconds: float) -> str:
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


class WhisperLocalProvider(ASRProvider):
    def __init__(self, model_name: str = "base") -> None:
        self._model_name = model_name
        self._model = None

    def transcribe(self, audio_path: str, language: str) -> Transcript:
        if self._model is None:
            import whisper
            self._model = whisper.load_model(self._model_name, device="cpu")
        result = self._model.transcribe(audio_path, language=language)
        segments = [
            TranscriptSegment(
                start=float(seg["start"]),
                end=float(seg["end"]),
                text=seg["text"],
                speaker=None,
            )
            for seg in result.get("segments", [])
        ]
        return Transcript(
            language=result.get("language", language),
            segments=segments,
            full_text=result.get("text", ""),
        )


def save_transcript(
    transcript: Transcript,
    job_id: str,
    work_dir: str | Path = "data/work",
) -> Path:
    output_dir = Path(work_dir) / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "transcript.json"
    path.write_text(transcript.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_transcript(
    job_id: str,
    work_dir: str | Path = "data/work",
) -> Transcript:
    path = Path(work_dir) / job_id / "transcript.json"
    return Transcript.model_validate_json(path.read_text(encoding="utf-8"))
