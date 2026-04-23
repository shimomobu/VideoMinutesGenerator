"""TASK-00-05: vmg.common.interfaces の単体テスト"""
import pytest

from vmg.common.interfaces import ASRProvider, DiarizationProvider, FormatterProvider
from vmg.common.models import (
    AnalysisResult,
    MeetingInfo,
    Transcript,
    TranscriptSegment,
)


# ── テスト用ヘルパー ──────────────────────────────────────────────

def _make_transcript() -> Transcript:
    return Transcript(
        language="ja",
        segments=[TranscriptSegment(start=0.0, end=5.0, text="テスト発言")],
        full_text="テスト発言",
    )


def _make_meeting_info() -> MeetingInfo:
    return MeetingInfo(
        title="テスト会議",
        datetime="2026-04-22T10:00:00",
        participants=["山田", "鈴木"],
        source_file="meeting.mp4",
        duration_seconds=3600,
    )


def _make_analysis_result() -> AnalysisResult:
    return AnalysisResult(
        summary="会議の要約", agenda=[], topics=[], decisions=[], pending_items=[], todos=[]
    )


# ── ASRProvider ───────────────────────────────────────────────────

class TestASRProvider:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            ASRProvider()  # type: ignore[abstract]

    def test_missing_transcribe_raises_type_error(self):
        class IncompleteASR(ASRProvider):
            pass  # transcribe を実装しない

        with pytest.raises(TypeError):
            IncompleteASR()

    def test_minimal_implementation_can_be_instantiated(self):
        class MinimalASR(ASRProvider):
            def transcribe(self, audio_path: str, language: str) -> Transcript:
                return _make_transcript()

        provider = MinimalASR()
        assert isinstance(provider, ASRProvider)

    def test_transcribe_returns_transcript(self):
        class MinimalASR(ASRProvider):
            def transcribe(self, audio_path: str, language: str) -> Transcript:
                return _make_transcript()

        result = MinimalASR().transcribe("audio.wav", "ja")
        assert isinstance(result, Transcript)

    def test_transcribe_receives_audio_path_and_language(self):
        received = {}

        class SpyASR(ASRProvider):
            def transcribe(self, audio_path: str, language: str) -> Transcript:
                received["audio_path"] = audio_path
                received["language"] = language
                return _make_transcript()

        SpyASR().transcribe("/data/work/job-001/audio.wav", "ja")
        assert received["audio_path"] == "/data/work/job-001/audio.wav"
        assert received["language"] == "ja"


# ── FormatterProvider ─────────────────────────────────────────────

class TestFormatterProvider:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            FormatterProvider()  # type: ignore[abstract]

    def test_missing_format_raises_type_error(self):
        class IncompleteFormatter(FormatterProvider):
            pass  # format を実装しない

        with pytest.raises(TypeError):
            IncompleteFormatter()

    def test_minimal_implementation_can_be_instantiated(self):
        class MinimalFormatter(FormatterProvider):
            def format(
                self,
                meeting_info: MeetingInfo,
                analysis: AnalysisResult,
                transcript: Transcript,
            ) -> str:
                return "# 議事録\n"

        provider = MinimalFormatter()
        assert isinstance(provider, FormatterProvider)

    def test_format_returns_str(self):
        class MinimalFormatter(FormatterProvider):
            def format(
                self,
                meeting_info: MeetingInfo,
                analysis: AnalysisResult,
                transcript: Transcript,
            ) -> str:
                return "# 議事録\n"

        result = MinimalFormatter().format(
            _make_meeting_info(), _make_analysis_result(), _make_transcript()
        )
        assert isinstance(result, str)

    def test_format_receives_correct_arguments(self):
        received = {}

        class SpyFormatter(FormatterProvider):
            def format(
                self,
                meeting_info: MeetingInfo,
                analysis: AnalysisResult,
                transcript: Transcript,
            ) -> str:
                received["meeting_info"] = meeting_info
                received["analysis"] = analysis
                received["transcript"] = transcript
                return ""

        info = _make_meeting_info()
        analysis = _make_analysis_result()
        transcript = _make_transcript()
        SpyFormatter().format(info, analysis, transcript)
        assert received["meeting_info"] is info
        assert received["analysis"] is analysis
        assert received["transcript"] is transcript


# ── DiarizationProvider ───────────────────────────────────────────

class TestDiarizationProvider:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            DiarizationProvider()  # type: ignore[abstract]

    def test_missing_diarize_raises_type_error(self):
        class IncompleteDiarization(DiarizationProvider):
            pass  # diarize を実装しない

        with pytest.raises(TypeError):
            IncompleteDiarization()

    def test_minimal_implementation_can_be_instantiated(self):
        class MinimalDiarization(DiarizationProvider):
            def diarize(self, transcript: Transcript, audio_path: str) -> Transcript:
                return transcript

        provider = MinimalDiarization()
        assert isinstance(provider, DiarizationProvider)

    def test_diarize_returns_transcript(self):
        class MinimalDiarization(DiarizationProvider):
            def diarize(self, transcript: Transcript, audio_path: str) -> Transcript:
                return transcript

        t = _make_transcript()
        result = MinimalDiarization().diarize(t, "audio.wav")
        assert isinstance(result, Transcript)

    def test_pass_through_returns_same_transcript(self):
        """MVPのPassThrough実装パターン: transcript をそのまま返す"""

        class PassThroughDiarization(DiarizationProvider):
            def diarize(self, transcript: Transcript, audio_path: str) -> Transcript:
                return transcript

        t = _make_transcript()
        result = PassThroughDiarization().diarize(t, "audio.wav")
        assert result is t

    def test_diarize_receives_transcript_and_audio_path(self):
        received = {}

        class SpyDiarization(DiarizationProvider):
            def diarize(self, transcript: Transcript, audio_path: str) -> Transcript:
                received["transcript"] = transcript
                received["audio_path"] = audio_path
                return transcript

        t = _make_transcript()
        SpyDiarization().diarize(t, "/data/work/job-001/audio.wav")
        assert received["transcript"] is t
        assert received["audio_path"] == "/data/work/job-001/audio.wav"
