"""同音異義語誤変換補正 — ASR 出力の transcript に辞書ベース置換を適用する"""
from __future__ import annotations

from vmg.common.models import Transcript, TranscriptSegment


class TranscriptCorrector:
    def __init__(self, rules: list[dict], enabled: bool = True) -> None:
        self._rules: list[tuple[str, str]] = [(r["wrong"], r["correct"]) for r in rules]
        self._enabled = enabled

    def correct(self, transcript: Transcript) -> Transcript:
        if not self._enabled or not self._rules:
            return transcript

        def apply(text: str) -> str:
            for wrong, correct in self._rules:
                text = text.replace(wrong, correct)
            return text

        return Transcript(
            language=transcript.language,
            segments=[
                TranscriptSegment(
                    start=seg.start,
                    end=seg.end,
                    text=apply(seg.text),
                    speaker=seg.speaker,
                )
                for seg in transcript.segments
            ],
            full_text=apply(transcript.full_text),
        )
