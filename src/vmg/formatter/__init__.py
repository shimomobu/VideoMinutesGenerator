"""formatter — 議事録フォーマッタ（FormatterProvider 実装）"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from vmg.common.interfaces import FormatterProvider
from vmg.common.models import AnalysisResult, MeetingInfo, Transcript

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _seconds_to_hms(seconds: float) -> str:
    s = int(seconds)
    h, remainder = divmod(s, 3600)
    m, sec = divmod(remainder, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


class StandardFormatter(FormatterProvider):
    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=False,
            keep_trailing_newline=True,
        )
        self._env.filters["seconds_to_hms"] = _seconds_to_hms

    def format(
        self,
        meeting_info: MeetingInfo,
        analysis: AnalysisResult,
        transcript: Transcript,
    ) -> str:
        tmpl = self._env.get_template("standard.md.j2")
        return tmpl.render(
            meeting_info=meeting_info,
            analysis=analysis,
            transcript=transcript,
        )
