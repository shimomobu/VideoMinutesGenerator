"""TASK-05-01/05-02: 標準議事録テンプレートおよび StandardFormatter のテスト"""
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

from vmg.common.interfaces import FormatterProvider
from vmg.common.models import (
    AnalysisResult,
    MeetingInfo,
    Todo,
    Topic,
    Transcript,
    TranscriptSegment,
)
from vmg.formatter import StandardFormatter, _duration_to_hms

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "src" / "vmg" / "formatter" / "templates"


def _seconds_to_hms(seconds: float) -> str:
    s = int(seconds)
    h, remainder = divmod(s, 3600)
    m, sec = divmod(remainder, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


@pytest.fixture
def jinja_env():
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,
        keep_trailing_newline=True,
    )
    env.filters["seconds_to_hms"] = _seconds_to_hms
    env.filters["duration_hms"] = _duration_to_hms
    return env


@pytest.fixture
def sample_meeting_info():
    return MeetingInfo(
        title="週次定例会議",
        datetime="2026-04-23T10:00:00+09:00",
        participants=["田中", "鈴木", "佐藤"],
        source_file="weekly_meeting_2026-04-23.mp4",
        duration_seconds=3600,
    )


@pytest.fixture
def sample_analysis():
    return AnalysisResult(
        summary="プロジェクトの進捗を確認し、課題を整理した。",
        agenda=["進捗確認", "課題整理"],
        topics=[
            Topic(
                title="進捗確認",
                summary="全体的に順調。",
                key_points=["スケジュール通り", "品質問題なし"],
            )
        ],
        decisions=["次回リリースは月末に決定"],
        pending_items=["予算の最終確認"],
        todos=[
            Todo(
                task="リリース資料作成",
                owner_candidate="田中",
                due_date_candidate="月末",
                notes="ドラフト版でよい",
            )
        ],
    )


@pytest.fixture
def sample_transcript():
    return Transcript(
        language="ja",
        segments=[
            TranscriptSegment(start=0.0, end=5.0, text="会議を始めます。", speaker="田中"),
            TranscriptSegment(start=65.0, end=70.0, text="了解です。", speaker=None),
        ],
        full_text="会議を始めます。了解です。",
    )


@pytest.fixture
def empty_analysis():
    return AnalysisResult(
        summary="",
        agenda=[],
        topics=[],
        decisions=[],
        pending_items=[],
        todos=[],
    )


class TestStandardTemplate:
    def test_template_loads_without_error(self, jinja_env):
        """テンプレートが構文エラーなくロードできること"""
        tmpl = jinja_env.get_template("standard.md.j2")
        assert tmpl is not None

    def test_heading_starts_with_minutes(self, jinja_env, sample_meeting_info, sample_analysis, sample_transcript):
        """出力が '# 議事録' で始まること"""
        tmpl = jinja_env.get_template("standard.md.j2")
        result = tmpl.render(
            meeting_info=sample_meeting_info,
            analysis=sample_analysis,
            transcript=sample_transcript,
        )
        assert result.strip().startswith("# 議事録")

    def test_all_8_sections_present(self, jinja_env, sample_meeting_info, sample_analysis, sample_transcript):
        """全8セクション（##見出し）が出力に含まれること"""
        tmpl = jinja_env.get_template("standard.md.j2")
        result = tmpl.render(
            meeting_info=sample_meeting_info,
            analysis=sample_analysis,
            transcript=sample_transcript,
        )
        assert "## 1. 会議情報" in result
        assert "## 2. 会議要約" in result
        assert "## 3. 議題" in result
        assert "## 4. 議論内容" in result
        assert "## 5. 決定事項" in result
        assert "## 6. 保留事項" in result
        assert "## 7. ToDo" in result
        assert "## 8. 参考ログ" in result

    def test_meeting_info_rendered(self, jinja_env, sample_meeting_info, sample_analysis, sample_transcript):
        """会議情報（タイトル・日時・参加者）が出力に含まれること"""
        tmpl = jinja_env.get_template("standard.md.j2")
        result = tmpl.render(
            meeting_info=sample_meeting_info,
            analysis=sample_analysis,
            transcript=sample_transcript,
        )
        assert "週次定例会議" in result
        assert "2026-04-23T10:00:00+09:00" in result
        assert "田中" in result
        assert "鈴木" in result
        assert "佐藤" in result

    def test_empty_decisions_no_error(self, jinja_env, sample_meeting_info, empty_analysis, sample_transcript):
        """decisions が空でもセクション5が正常出力されること"""
        tmpl = jinja_env.get_template("standard.md.j2")
        result = tmpl.render(
            meeting_info=sample_meeting_info,
            analysis=empty_analysis,
            transcript=sample_transcript,
        )
        assert "## 5. 決定事項" in result

    def test_empty_todos_no_error(self, jinja_env, sample_meeting_info, empty_analysis, sample_transcript):
        """todos が空でもセクション7が正常出力されること"""
        tmpl = jinja_env.get_template("standard.md.j2")
        result = tmpl.render(
            meeting_info=sample_meeting_info,
            analysis=empty_analysis,
            transcript=sample_transcript,
        )
        assert "## 7. ToDo" in result

    def test_todo_table_has_required_columns(self, jinja_env, sample_meeting_info, sample_analysis, sample_transcript):
        """ToDoテーブルに「タスク / 担当候補 / 期限候補 / 備考」の列が含まれること"""
        tmpl = jinja_env.get_template("standard.md.j2")
        result = tmpl.render(
            meeting_info=sample_meeting_info,
            analysis=sample_analysis,
            transcript=sample_transcript,
        )
        assert "タスク" in result
        assert "担当候補" in result
        assert "期限候補" in result
        assert "備考" in result

    def test_todo_data_rendered(self, jinja_env, sample_meeting_info, sample_analysis, sample_transcript):
        """ToDoの内容（task・owner_candidate・due_date_candidate）が出力されること"""
        tmpl = jinja_env.get_template("standard.md.j2")
        result = tmpl.render(
            meeting_info=sample_meeting_info,
            analysis=sample_analysis,
            transcript=sample_transcript,
        )
        assert "リリース資料作成" in result
        assert "月末" in result

    def test_transcript_hms_format(self, jinja_env, sample_meeting_info, sample_analysis, sample_transcript):
        """参考ログに [HH:MM:SS] 形式のタイムスタンプが含まれること"""
        tmpl = jinja_env.get_template("standard.md.j2")
        result = tmpl.render(
            meeting_info=sample_meeting_info,
            analysis=sample_analysis,
            transcript=sample_transcript,
        )
        assert "[00:00:00]" in result
        assert "[00:01:05]" in result

    def test_empty_transcript_no_error(self, jinja_env, sample_meeting_info, sample_analysis):
        """transcript が空でもセクション8が正常出力されること"""
        empty_transcript = Transcript(language="ja", segments=[], full_text="")
        tmpl = jinja_env.get_template("standard.md.j2")
        result = tmpl.render(
            meeting_info=sample_meeting_info,
            analysis=sample_analysis,
            transcript=empty_transcript,
        )
        assert "## 8. 参考ログ" in result


class TestStandardFormatter:
    def test_is_formatter_provider(self):
        """StandardFormatter が FormatterProvider を実装していること"""
        assert issubclass(StandardFormatter, FormatterProvider)

    def test_format_returns_str(self, sample_meeting_info, sample_analysis, sample_transcript):
        """format() が文字列を返すこと"""
        formatter = StandardFormatter()
        result = formatter.format(sample_meeting_info, sample_analysis, sample_transcript)
        assert isinstance(result, str)

    def test_format_heading(self, sample_meeting_info, sample_analysis, sample_transcript):
        """出力が '# 議事録' で始まること"""
        formatter = StandardFormatter()
        result = formatter.format(sample_meeting_info, sample_analysis, sample_transcript)
        assert result.strip().startswith("# 議事録")

    def test_format_all_8_sections(self, sample_meeting_info, sample_analysis, sample_transcript):
        """全8セクションが出力に含まれること"""
        formatter = StandardFormatter()
        result = formatter.format(sample_meeting_info, sample_analysis, sample_transcript)
        assert "## 1. 会議情報" in result
        assert "## 2. 会議要約" in result
        assert "## 3. 議題" in result
        assert "## 4. 議論内容" in result
        assert "## 5. 決定事項" in result
        assert "## 6. 保留事項" in result
        assert "## 7. ToDo" in result
        assert "## 8. 参考ログ" in result

    def test_format_meeting_info_in_output(self, sample_meeting_info, sample_analysis, sample_transcript):
        """会議情報（タイトル・日時・元動画ファイル）が出力に含まれること"""
        formatter = StandardFormatter()
        result = formatter.format(sample_meeting_info, sample_analysis, sample_transcript)
        assert "週次定例会議" in result
        assert "2026-04-23T10:00:00+09:00" in result
        assert "weekly_meeting_2026-04-23.mp4" in result

    def test_format_empty_data_no_error(self, sample_meeting_info, empty_analysis, sample_transcript):
        """decisions/todos が空でも破綻しないこと"""
        formatter = StandardFormatter()
        result = formatter.format(sample_meeting_info, empty_analysis, sample_transcript)
        assert "## 5. 決定事項" in result
        assert "## 7. ToDo" in result

    def test_format_hms_timestamps(self, sample_meeting_info, sample_analysis, sample_transcript):
        """参考ログに [HH:MM:SS] 形式のタイムスタンプが含まれること"""
        formatter = StandardFormatter()
        result = formatter.format(sample_meeting_info, sample_analysis, sample_transcript)
        assert "[00:00:00]" in result
        assert "[00:01:05]" in result

    def test_format_todo_columns(self, sample_meeting_info, sample_analysis, sample_transcript):
        """ToDoテーブルに所定の列が含まれること"""
        formatter = StandardFormatter()
        result = formatter.format(sample_meeting_info, sample_analysis, sample_transcript)
        assert "タスク" in result
        assert "担当候補" in result
        assert "期限候補" in result
        assert "備考" in result

    def test_format_empty_transcript_no_error(self, sample_meeting_info, sample_analysis):
        """transcript が空でも破綻しないこと"""
        formatter = StandardFormatter()
        empty_transcript = Transcript(language="ja", segments=[], full_text="")
        result = formatter.format(sample_meeting_info, sample_analysis, empty_transcript)
        assert "## 8. 参考ログ" in result


class TestDurationToHms:
    def test_zero(self):
        assert _duration_to_hms(0) == "0秒"

    def test_seconds_only(self):
        assert _duration_to_hms(45) == "45秒"

    def test_exactly_one_minute(self):
        assert _duration_to_hms(60) == "1分0秒"

    def test_minutes_and_seconds(self):
        assert _duration_to_hms(90) == "1分30秒"

    def test_hours_minutes_seconds(self):
        assert _duration_to_hms(3661) == "1時間1分1秒"

    def test_exactly_one_hour(self):
        assert _duration_to_hms(3600) == "1時間0分0秒"


class TestDurationInTemplate:
    def test_duration_seconds_displayed(self, jinja_env, sample_analysis, sample_transcript):
        """duration_seconds=3600 が 1時間0分0秒 と表示されること"""
        info = MeetingInfo(
            title="T", datetime="2026-01-01T10:00:00", participants=[],
            source_file="t.mp4", duration_seconds=3600,
        )
        result = jinja_env.get_template("standard.md.j2").render(
            meeting_info=info, analysis=sample_analysis, transcript=sample_transcript,
        )
        assert "1時間0分0秒" in result

    def test_duration_90_seconds(self, jinja_env, sample_analysis, sample_transcript):
        """duration_seconds=90 が 1分30秒 と表示されること"""
        info = MeetingInfo(
            title="T", datetime="2026-01-01T10:00:00", participants=[],
            source_file="t.mp4", duration_seconds=90,
        )
        result = jinja_env.get_template("standard.md.j2").render(
            meeting_info=info, analysis=sample_analysis, transcript=sample_transcript,
        )
        assert "1分30秒" in result

    def test_duration_45_seconds(self, jinja_env, sample_analysis, sample_transcript):
        """duration_seconds=45 が 45秒 と表示されること"""
        info = MeetingInfo(
            title="T", datetime="2026-01-01T10:00:00", participants=[],
            source_file="t.mp4", duration_seconds=45,
        )
        result = jinja_env.get_template("standard.md.j2").render(
            meeting_info=info, analysis=sample_analysis, transcript=sample_transcript,
        )
        assert "45秒" in result

    def test_duration_zero(self, jinja_env, sample_analysis, sample_transcript):
        """duration_seconds=0 が 0秒 と表示されること"""
        info = MeetingInfo(
            title="T", datetime="2026-01-01T10:00:00", participants=[],
            source_file="t.mp4", duration_seconds=0,
        )
        result = jinja_env.get_template("standard.md.j2").render(
            meeting_info=info, analysis=sample_analysis, transcript=sample_transcript,
        )
        assert "0秒" in result
