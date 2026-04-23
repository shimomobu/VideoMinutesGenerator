"""TASK-04-04: vmg.analysis.postprocess 単体テスト"""
import json

import pytest

from vmg.analysis.postprocess import postprocess, save_analysis
from vmg.analysis.validator import ValidatedAnalysisJSON
from vmg.common.models import AnalysisResult, Todo, Topic


# ── フィクスチャ ──────────────────────────────────────────────────

def _make_validated(**overrides) -> ValidatedAnalysisJSON:
    base = dict(
        summary="会議の要約",
        agenda=["議題A"],
        topics=[Topic(title="T", summary="説明", key_points=["P1"])],
        decisions=["決定1"],
        pending_items=["保留1"],
        todos=[Todo(task="タスク1", owner_candidate="田中", due_date_candidate="来週")],
    )
    base.update(overrides)
    return AnalysisResult(**base)


# ── 正常系: 基本動作 ──────────────────────────────────────────────

class TestPostprocessNormal:
    def test_returns_analysis_result(self, tmp_path):
        validated = _make_validated()
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert isinstance(result, AnalysisResult)

    def test_summary_preserved(self, tmp_path):
        validated = _make_validated(summary="テスト要約")
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert result.summary == "テスト要約"

    def test_agenda_preserved(self, tmp_path):
        validated = _make_validated(agenda=["議題X", "議題Y"])
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert result.agenda == ["議題X", "議題Y"]

    def test_topics_preserved(self, tmp_path):
        validated = _make_validated()
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert len(result.topics) == 1
        assert result.topics[0].title == "T"

    def test_pending_items_preserved(self, tmp_path):
        validated = _make_validated(pending_items=["保留X"])
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert result.pending_items == ["保留X"]

    def test_owner_candidate_preserved(self, tmp_path):
        validated = _make_validated(
            todos=[Todo(task="報告", owner_candidate="鈴木")]
        )
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert result.todos[0].owner_candidate == "鈴木"

    def test_due_date_candidate_preserved(self, tmp_path):
        validated = _make_validated(
            todos=[Todo(task="提出", due_date_candidate="来週金曜")]
        )
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert result.todos[0].due_date_candidate == "来週金曜"

    def test_notes_preserved(self, tmp_path):
        validated = _make_validated(
            todos=[Todo(task="確認", notes="承認後に対応")]
        )
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert result.todos[0].notes == "承認後に対応"

    def test_owner_candidate_none_preserved(self, tmp_path):
        validated = _make_validated(todos=[Todo(task="調査", owner_candidate=None)])
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert result.todos[0].owner_candidate is None

    def test_empty_decisions_preserved(self, tmp_path):
        validated = _make_validated(decisions=[])
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert result.decisions == []

    def test_empty_todos_preserved(self, tmp_path):
        validated = _make_validated(todos=[])
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert result.todos == []


# ── 正常系: 重複除去 ─────────────────────────────────────────────

class TestPostprocessDeduplicate:
    def test_duplicate_decisions_removed(self, tmp_path):
        validated = _make_validated(decisions=["決定A", "決定A", "決定B"])
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert result.decisions == ["決定A", "決定B"]

    def test_triplicate_decisions_deduplicated(self, tmp_path):
        validated = _make_validated(decisions=["X", "X", "X"])
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert result.decisions == ["X"]

    def test_unique_decisions_all_kept(self, tmp_path):
        validated = _make_validated(decisions=["A", "B", "C"])
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert result.decisions == ["A", "B", "C"]

    def test_decisions_first_occurrence_order_preserved(self, tmp_path):
        validated = _make_validated(decisions=["B", "A", "B", "C", "A"])
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert result.decisions == ["B", "A", "C"]

    def test_duplicate_todos_removed_by_task(self, tmp_path):
        validated = _make_validated(todos=[
            Todo(task="タスクA", owner_candidate="田中"),
            Todo(task="タスクA", owner_candidate="鈴木"),
            Todo(task="タスクB"),
        ])
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert len(result.todos) == 2

    def test_duplicate_todos_first_occurrence_kept(self, tmp_path):
        validated = _make_validated(todos=[
            Todo(task="タスクA", owner_candidate="田中"),
            Todo(task="タスクA", owner_candidate="鈴木"),
        ])
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert result.todos[0].owner_candidate == "田中"

    def test_unique_todos_all_kept(self, tmp_path):
        validated = _make_validated(todos=[
            Todo(task="タスク1"),
            Todo(task="タスク2"),
            Todo(task="タスク3"),
        ])
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert len(result.todos) == 3


# ── 正常系: 曖昧表現の保持 ───────────────────────────────────────

class TestPostprocessAmbiguousExpression:
    def test_ambiguous_due_date_preserved(self, tmp_path):
        validated = _make_validated(
            todos=[Todo(task="報告", due_date_candidate="来週")]
        )
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert result.todos[0].due_date_candidate == "来週"

    def test_month_end_expression_preserved(self, tmp_path):
        validated = _make_validated(
            todos=[Todo(task="提出", due_date_candidate="月末")]
        )
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert result.todos[0].due_date_candidate == "月末"

    def test_asap_expression_preserved(self, tmp_path):
        validated = _make_validated(
            todos=[Todo(task="確認", due_date_candidate="なるはや")]
        )
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert result.todos[0].due_date_candidate == "なるはや"

    def test_ambiguous_owner_preserved(self, tmp_path):
        validated = _make_validated(
            todos=[Todo(task="連絡", owner_candidate="山田さん")]
        )
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert result.todos[0].owner_candidate == "山田さん"


# ── analysis.json 保存 ────────────────────────────────────────────

class TestPostprocessSaveFile:
    def test_analysis_json_created(self, tmp_path):
        validated = _make_validated()
        postprocess(validated, job_id="job-001", work_dir=tmp_path)
        assert (tmp_path / "job-001" / "analysis.json").exists()

    def test_analysis_json_is_valid_json(self, tmp_path):
        validated = _make_validated()
        postprocess(validated, job_id="job-001", work_dir=tmp_path)
        text = (tmp_path / "job-001" / "analysis.json").read_text(encoding="utf-8")
        data = json.loads(text)
        assert isinstance(data, dict)

    def test_analysis_json_has_summary(self, tmp_path):
        validated = _make_validated(summary="保存テスト")
        postprocess(validated, job_id="job-001", work_dir=tmp_path)
        text = (tmp_path / "job-001" / "analysis.json").read_text(encoding="utf-8")
        data = json.loads(text)
        assert data["summary"] == "保存テスト"

    def test_analysis_json_roundtrip(self, tmp_path):
        validated = _make_validated()
        result = postprocess(validated, job_id="job-001", work_dir=tmp_path)
        text = (tmp_path / "job-001" / "analysis.json").read_text(encoding="utf-8")
        restored = AnalysisResult.model_validate_json(text)
        assert restored == result

    def test_job_dir_created_automatically(self, tmp_path):
        validated = _make_validated()
        postprocess(validated, job_id="new-job", work_dir=tmp_path)
        assert (tmp_path / "new-job").is_dir()

    def test_save_analysis_returns_path(self, tmp_path):
        result = _make_validated()
        path = save_analysis(result, job_id="job-001", work_dir=tmp_path)
        assert path.name == "analysis.json"
        assert path.exists()
