"""TASK-06-01/06-02: export モジュールのテスト"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vmg.common.models import (
    AnalysisResult,
    MeetingInfo,
    MinutesOutput,
    OutputManifest,
    Todo,
    Topic,
    Transcript,
    TranscriptSegment,
)
from vmg.export import OutputError, write_json, write_markdown


@pytest.fixture()
def sample_minutes() -> MinutesOutput:
    return MinutesOutput(
        meeting_info=MeetingInfo(
            title="週次定例",
            datetime="2026-04-23T10:00:00",
            participants=["田中", "佐藤"],
            source_file="meeting.mp4",
            duration_seconds=3600,
        ),
        analysis=AnalysisResult(
            summary="今週の進捗を確認した。",
            agenda=["進捗確認", "課題整理"],
            topics=[
                Topic(
                    title="進捗確認",
                    summary="各タスクは順調。",
                    key_points=["タスクA完了"],
                )
            ],
            decisions=["次回は来週月曜日に開催"],
            pending_items=["予算確認"],
            todos=[
                Todo(
                    task="議事録作成",
                    owner_candidate="田中",
                    due_date_candidate="来週金曜",
                    notes="Markdown形式で",
                )
            ],
        ),
        transcript=Transcript(
            language="ja",
            segments=[
                TranscriptSegment(start=0.0, end=5.0, text="会議を始めます。")
            ],
            full_text="会議を始めます。",
        ),
        manifest=OutputManifest(
            job_id="job_001",
            generated_at="2026-04-23T10:00:00",
            files=["minutes.md", "minutes.json"],
        ),
    )


class TestWriteMarkdown:
    def test_returns_path(self, tmp_path):
        """戻り値が Path オブジェクトであること"""
        result = write_markdown("# 議事録\n", job_id="job_001", output_dir=tmp_path)
        assert isinstance(result, Path)

    def test_file_is_created(self, tmp_path):
        """minutes.md ファイルが作成されること"""
        result = write_markdown("# 議事録\n", job_id="job_001", output_dir=tmp_path)
        assert result.exists()
        assert result.name == "minutes.md"

    def test_output_path_structure(self, tmp_path):
        """出力パスが {output_dir}/{job_id}/minutes.md であること"""
        result = write_markdown("# 議事録\n", job_id="job_abc", output_dir=tmp_path)
        assert result == tmp_path / "job_abc" / "minutes.md"

    def test_content_preserved(self, tmp_path):
        """ファイル内容が正しく書き出されること"""
        content = "# 議事録\n\n## 1. 会議情報\n- 会議名: テスト\n"
        result = write_markdown(content, job_id="job_001", output_dir=tmp_path)
        assert result.read_text(encoding="utf-8") == content

    def test_first_line_is_heading(self, tmp_path):
        """書き出したファイルの先頭行が '# 議事録' であること"""
        content = "# 議事録\n\n## 2. 会議要約\n"
        result = write_markdown(content, job_id="job_001", output_dir=tmp_path)
        assert result.read_text(encoding="utf-8").splitlines()[0] == "# 議事録"

    def test_output_dir_created_automatically(self, tmp_path):
        """存在しない出力ディレクトリが自動作成されること"""
        new_base = tmp_path / "does_not_exist_yet"
        result = write_markdown("# 議事録\n", job_id="job_001", output_dir=new_base)
        assert result.parent.exists()

    def test_nested_output_dir_created(self, tmp_path):
        """ネストした出力ディレクトリも自動作成されること"""
        nested = tmp_path / "a" / "b" / "c"
        result = write_markdown("# 議事録\n", job_id="job_001", output_dir=nested)
        assert result.exists()

    def test_output_error_on_permission_denied(self, tmp_path):
        """書き込み権限なし時に OutputError が発生すること"""
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o555)
        try:
            with pytest.raises(OutputError):
                write_markdown("# 議事録\n", job_id="job_001", output_dir=readonly_dir)
        finally:
            readonly_dir.chmod(0o755)

    def test_accepts_str_output_dir(self, tmp_path):
        """output_dir に文字列を渡しても動作すること"""
        result = write_markdown("# 議事録\n", job_id="job_001", output_dir=str(tmp_path))
        assert result.exists()


class TestWriteJson:
    def test_returns_path(self, tmp_path, sample_minutes):
        """戻り値が Path オブジェクトであること"""
        result = write_json(sample_minutes, job_id="job_001", output_dir=tmp_path)
        assert isinstance(result, Path)

    def test_file_is_created(self, tmp_path, sample_minutes):
        """minutes.json ファイルが作成されること"""
        result = write_json(sample_minutes, job_id="job_001", output_dir=tmp_path)
        assert result.exists()
        assert result.name == "minutes.json"

    def test_output_path_structure(self, tmp_path, sample_minutes):
        """出力パスが {output_dir}/{job_id}/minutes.json であること"""
        result = write_json(sample_minutes, job_id="job_abc", output_dir=tmp_path)
        assert result == tmp_path / "job_abc" / "minutes.json"

    def test_json_schema(self, tmp_path, sample_minutes):
        """JSON に全フィールドが含まれること"""
        result = write_json(sample_minutes, job_id="job_001", output_dir=tmp_path)
        data = json.loads(result.read_text(encoding="utf-8"))
        assert "meeting_info" in data
        assert "analysis" in data
        assert "transcript" in data
        assert "manifest" in data

    def test_roundtrip(self, tmp_path, sample_minutes):
        """シリアライズ → デシリアライズの往復で元のオブジェクトが復元できること"""
        result = write_json(sample_minutes, job_id="job_001", output_dir=tmp_path)
        restored = MinutesOutput.model_validate_json(result.read_text(encoding="utf-8"))
        assert restored == sample_minutes

    def test_owner_candidate_in_output(self, tmp_path, sample_minutes):
        """owner_candidate / due_date_candidate が JSON に出力されること"""
        result = write_json(sample_minutes, job_id="job_001", output_dir=tmp_path)
        data = json.loads(result.read_text(encoding="utf-8"))
        todo = data["analysis"]["todos"][0]
        assert todo["owner_candidate"] == "田中"
        assert todo["due_date_candidate"] == "来週金曜"

    def test_pretty_print(self, tmp_path, sample_minutes):
        """JSON がインデント付き（pretty-print）で出力されること"""
        result = write_json(sample_minutes, job_id="job_001", output_dir=tmp_path)
        raw = result.read_text(encoding="utf-8")
        assert "\n" in raw
        assert "  " in raw  # インデントの存在確認

    def test_output_dir_created_automatically(self, tmp_path, sample_minutes):
        """存在しない出力ディレクトリが自動作成されること"""
        new_base = tmp_path / "does_not_exist_yet"
        result = write_json(sample_minutes, job_id="job_001", output_dir=new_base)
        assert result.parent.exists()

    def test_output_error_on_permission_denied(self, tmp_path, sample_minutes):
        """書き込み権限なし時に OutputError が発生すること"""
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o555)
        try:
            with pytest.raises(OutputError):
                write_json(sample_minutes, job_id="job_001", output_dir=readonly_dir)
        finally:
            readonly_dir.chmod(0o755)

    def test_accepts_str_output_dir(self, tmp_path, sample_minutes):
        """output_dir に文字列を渡しても動作すること"""
        result = write_json(sample_minutes, job_id="job_001", output_dir=str(tmp_path))
        assert result.exists()
