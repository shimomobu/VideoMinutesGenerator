"""抽象インターフェース定義 — ASR / Formatter / Diarization の差し替え可能な基底クラス"""
from __future__ import annotations

from abc import ABC, abstractmethod

from vmg.common.models import AnalysisResult, MeetingInfo, Transcript


class ASRProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str, language: str) -> Transcript:
        ...


class FormatterProvider(ABC):
    @abstractmethod
    def format(
        self,
        meeting_info: MeetingInfo,
        analysis: AnalysisResult,
        transcript: Transcript,
    ) -> str:
        ...


class DiarizationProvider(ABC):
    @abstractmethod
    def diarize(self, transcript: Transcript, audio_path: str) -> Transcript:
        ...
