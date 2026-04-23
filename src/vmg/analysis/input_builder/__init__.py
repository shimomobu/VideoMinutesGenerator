"""analysis.input_builder — Transcript を Claude API 送信用 PromptInput に変換する"""
from __future__ import annotations

from pydantic import BaseModel

from vmg.common.models import Transcript, TranscriptSegment


class PromptInput(BaseModel):
    prompt: str
    segment_start: int
    segment_end: int


def build_prompt(
    transcript: Transcript,
    max_chars: int = 10000,
) -> list[PromptInput]:
    if not transcript.segments:
        return []

    chunks: list[PromptInput] = []
    current_lines: list[str] = []
    current_start = 0
    current_chars = 0

    for i, seg in enumerate(transcript.segments):
        line = _format_segment(seg)
        line_len = len(line) + 1  # +1 は区切り改行分

        if current_lines and current_chars + line_len > max_chars:
            chunks.append(PromptInput(
                prompt="\n".join(current_lines),
                segment_start=current_start,
                segment_end=i - 1,
            ))
            current_lines = [line]
            current_start = i
            current_chars = line_len
        else:
            current_lines.append(line)
            current_chars += line_len

    if current_lines:
        chunks.append(PromptInput(
            prompt="\n".join(current_lines),
            segment_start=current_start,
            segment_end=len(transcript.segments) - 1,
        ))

    return chunks


def _format_segment(seg: TranscriptSegment) -> str:
    total = int(seg.start)
    h, m, s = total // 3600, (total % 3600) // 60, total % 60
    ts = f"{h:02d}:{m:02d}:{s:02d}"
    if seg.speaker:
        return f"[{ts}] {seg.speaker}: {seg.text}"
    return f"[{ts}] {seg.text}"
