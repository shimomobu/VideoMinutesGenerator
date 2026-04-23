"""TASK-00-02: vmg.common.models の単体テスト"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from vmg.common.models import (
    MeetingInfo,
    TranscriptSegment,
    Transcript,
    Topic,
    Todo,
    AnalysisResult,
    OutputManifest,
    MinutesOutput,
)


class TestMeetingInfo:
    def test_normal_construction(self):
        info = MeetingInfo(
            title="週次定例",
            datetime="2026-04-22T10:00:00",
            participants=["山田", "鈴木"],
            source_file="meeting.mp4",
            duration_seconds=3600,
        )
        assert info.title == "週次定例"
        assert info.participants == ["山田", "鈴木"]
        assert info.duration_seconds == 3600

    def test_empty_participants(self):
        info = MeetingInfo(
            title="1on1",
            datetime="2026-04-22T10:00:00",
            participants=[],
            source_file="meeting.mp4",
            duration_seconds=1800,
        )
        assert info.participants == []

    def test_missing_title_raises(self):
        with pytest.raises(ValidationError):
            MeetingInfo(
                datetime="2026-04-22T10:00:00",
                participants=[],
                source_file="meeting.mp4",
                duration_seconds=0,
            )

    def test_missing_datetime_raises(self):
        with pytest.raises(ValidationError):
            MeetingInfo(title="test", participants=[], source_file="meeting.mp4", duration_seconds=0)

    def test_json_roundtrip(self):
        info = MeetingInfo(
            title="test",
            datetime="2026-04-22T10:00:00",
            participants=["A"],
            source_file="meeting.mp4",
            duration_seconds=60,
        )
        restored = MeetingInfo.model_validate_json(info.model_dump_json())
        assert restored == info


class TestTranscriptSegment:
    def test_speaker_none_allowed(self):
        seg = TranscriptSegment(start=0.0, end=5.0, text="こんにちは", speaker=None)
        assert seg.speaker is None

    def test_speaker_str_allowed(self):
        seg = TranscriptSegment(start=0.0, end=5.0, text="こんにちは", speaker="話者A")
        assert seg.speaker == "話者A"

    def test_speaker_defaults_none(self):
        seg = TranscriptSegment(start=0.0, end=5.0, text="test")
        assert seg.speaker is None

    def test_missing_start_raises(self):
        with pytest.raises(ValidationError):
            TranscriptSegment(end=5.0, text="test")

    def test_missing_text_raises(self):
        with pytest.raises(ValidationError):
            TranscriptSegment(start=0.0, end=5.0)

    def test_json_roundtrip(self):
        seg = TranscriptSegment(start=1.5, end=3.0, text="hello", speaker="A")
        restored = TranscriptSegment.model_validate_json(seg.model_dump_json())
        assert restored == seg


class TestTranscript:
    def test_normal_with_segments(self):
        seg = TranscriptSegment(start=0.0, end=2.0, text="test")
        t = Transcript(language="ja", segments=[seg], full_text="test")
        assert len(t.segments) == 1

    def test_empty_segments(self):
        t = Transcript(language="ja", segments=[], full_text="")
        assert t.segments == []

    def test_missing_language_raises(self):
        with pytest.raises(ValidationError):
            Transcript(segments=[], full_text="")

    def test_json_roundtrip(self):
        seg = TranscriptSegment(start=0.0, end=1.0, text="x")
        t = Transcript(language="en", segments=[seg], full_text="x")
        restored = Transcript.model_validate_json(t.model_dump_json())
        assert restored == t


class TestTopic:
    def test_normal_construction(self):
        topic = Topic(title="予算", summary="Q2の予算を確認", key_points=["削減", "承認"])
        assert topic.title == "予算"
        assert len(topic.key_points) == 2

    def test_empty_key_points(self):
        topic = Topic(title="雑談", summary="軽い話題", key_points=[])
        assert topic.key_points == []

    def test_missing_title_raises(self):
        with pytest.raises(ValidationError):
            Topic(summary="...", key_points=[])

    def test_json_roundtrip(self):
        topic = Topic(title="A", summary="B", key_points=["C"])
        restored = Topic.model_validate_json(topic.model_dump_json())
        assert restored == topic


class TestTodo:
    def test_all_candidates_none(self):
        todo = Todo(task="資料作成")
        assert todo.owner_candidate is None
        assert todo.due_date_candidate is None

    def test_candidates_as_str(self):
        todo = Todo(task="確認", owner_candidate="鈴木", due_date_candidate="来週金曜")
        assert todo.owner_candidate == "鈴木"
        assert todo.due_date_candidate == "来週金曜"

    def test_ambiguous_due_date_preserved(self):
        todo = Todo(task="対応", due_date_candidate="なるはや")
        assert todo.due_date_candidate == "なるはや"

    def test_notes_defaults_none(self):
        todo = Todo(task="資料作成")
        assert todo.notes is None

    def test_notes_as_str(self):
        todo = Todo(task="確認", notes="承認後に実施")
        assert todo.notes == "承認後に実施"

    def test_missing_task_raises(self):
        with pytest.raises(ValidationError):
            Todo(owner_candidate="A")

    def test_json_roundtrip(self):
        todo = Todo(task="T", owner_candidate="X", due_date_candidate="明日", notes="備考")
        restored = Todo.model_validate_json(todo.model_dump_json())
        assert restored == todo


class TestAnalysisResult:
    def test_normal_construction(self):
        result = AnalysisResult(
            summary="要約テスト",
            agenda=["議題1"],
            topics=[Topic(title="A", summary="B", key_points=[])],
            decisions=["決定事項1"],
            pending_items=["保留事項1"],
            todos=[Todo(task="C")],
        )
        assert result.summary == "要約テスト"
        assert result.agenda == ["議題1"]
        assert result.decisions == ["決定事項1"]
        assert result.pending_items == ["保留事項1"]

    def test_empty_lists(self):
        result = AnalysisResult(
            summary="空",
            agenda=[],
            topics=[],
            decisions=[],
            pending_items=[],
            todos=[],
        )
        assert result.agenda == []
        assert result.topics == []
        assert result.decisions == []
        assert result.pending_items == []
        assert result.todos == []

    def test_missing_summary_raises(self):
        with pytest.raises(ValidationError):
            AnalysisResult(agenda=[], topics=[], decisions=[], pending_items=[], todos=[])

    def test_missing_agenda_raises(self):
        with pytest.raises(ValidationError):
            AnalysisResult(summary="S", topics=[], decisions=[], pending_items=[], todos=[])

    def test_missing_decisions_raises(self):
        with pytest.raises(ValidationError):
            AnalysisResult(summary="S", agenda=[], topics=[], pending_items=[], todos=[])

    def test_missing_pending_items_raises(self):
        with pytest.raises(ValidationError):
            AnalysisResult(summary="S", agenda=[], topics=[], decisions=[], todos=[])

    def test_json_roundtrip(self):
        result = AnalysisResult(
            summary="S",
            agenda=["A1"],
            topics=[Topic(title="T", summary="U", key_points=["V"])],
            decisions=["D1"],
            pending_items=["P1"],
            todos=[Todo(task="W")],
        )
        restored = AnalysisResult.model_validate_json(result.model_dump_json())
        assert restored == result


class TestOutputManifest:
    def test_normal_construction(self):
        manifest = OutputManifest(
            job_id="job-001",
            generated_at="2026-04-22T10:00:00",
            files=["minutes.md", "minutes.json"],
            source_transcript="data/work/job-001/transcript.json",
        )
        assert manifest.job_id == "job-001"
        assert len(manifest.files) == 2

    def test_empty_files(self):
        manifest = OutputManifest(
            job_id="job-002",
            generated_at="2026-04-22T10:00:00",
            files=[],
            source_transcript="data/work/job-002/transcript.json",
        )
        assert manifest.files == []

    def test_missing_job_id_raises(self):
        with pytest.raises(ValidationError):
            OutputManifest(
                generated_at="2026-04-22T10:00:00",
                files=[],
                source_transcript="data/work/x/transcript.json",
            )

    def test_json_roundtrip(self):
        manifest = OutputManifest(
            job_id="j",
            generated_at="2026-04-22T10:00:00",
            files=["a.md"],
            source_transcript="data/work/j/transcript.json",
        )
        restored = OutputManifest.model_validate_json(manifest.model_dump_json())
        assert restored == manifest


class TestMinutesOutput:
    def test_normal_construction(self):
        info = MeetingInfo(
            title="週次",
            datetime="2026-04-22T10:00:00",
            participants=[],
            source_file="meeting.mp4",
            duration_seconds=0,
        )
        analysis = AnalysisResult(
            summary="要約", agenda=[], topics=[], decisions=[], pending_items=[], todos=[]
        )
        transcript = Transcript(language="ja", segments=[], full_text="")
        manifest = OutputManifest(
            job_id="j1",
            generated_at="2026-04-22T10:00:00",
            files=[],
            source_transcript="data/work/j1/transcript.json",
        )
        output = MinutesOutput(
            meeting_info=info,
            analysis=analysis,
            transcript=transcript,
            manifest=manifest,
        )
        assert output.meeting_info.title == "週次"

    def test_missing_meeting_info_raises(self):
        with pytest.raises(ValidationError):
            MinutesOutput(
                analysis=AnalysisResult(
                    summary="S", agenda=[], topics=[], decisions=[], pending_items=[], todos=[]
                ),
                transcript=Transcript(language="ja", segments=[], full_text=""),
                manifest=OutputManifest(
                    job_id="j",
                    generated_at="2026-04-22T10:00:00",
                    files=[],
                    source_transcript="data/work/j/transcript.json",
                ),
            )

    def test_json_roundtrip(self):
        info = MeetingInfo(
            title="t",
            datetime="2026-04-22T10:00:00",
            participants=["A"],
            source_file="meeting.mp4",
            duration_seconds=100,
        )
        analysis = AnalysisResult(
            summary="s",
            agenda=["A1"],
            topics=[Topic(title="T", summary="U", key_points=[])],
            decisions=["D1"],
            pending_items=["P1"],
            todos=[Todo(task="W")],
        )
        transcript = Transcript(language="ja", segments=[], full_text="text")
        manifest = OutputManifest(
            job_id="jj",
            generated_at="2026-04-22T10:00:00",
            files=["out.md"],
            source_transcript="data/work/jj/transcript.json",
        )
        output = MinutesOutput(
            meeting_info=info,
            analysis=analysis,
            transcript=transcript,
            manifest=manifest,
        )
        restored = MinutesOutput.model_validate_json(output.model_dump_json())
        assert restored == output
