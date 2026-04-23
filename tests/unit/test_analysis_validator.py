"""TASK-04-03: vmg.analysis.validator 単体テスト"""
import json

import pytest

from vmg.analysis.extractor import LLMError
from vmg.analysis.validator import ValidatedAnalysisJSON, validate


# ── サンプルデータ ────────────────────────────────────────────────

_VALID_JSON = json.dumps({
    "summary": "会議の要約テキスト",
    "agenda": ["議題A", "議題B"],
    "topics": [
        {
            "title": "議題1",
            "summary": "議題1の説明",
            "key_points": ["ポイント1", "ポイント2"],
        }
    ],
    "decisions": ["決定事項1"],
    "pending_items": ["保留事項1"],
    "todos": [
        {
            "task": "タスク1",
            "owner_candidate": "田中",
            "due_date_candidate": "来週",
        }
    ],
})

_VALID_EMPTY_LISTS = json.dumps({
    "summary": "空リストの会議",
    "agenda": [],
    "topics": [],
    "decisions": [],
    "pending_items": [],
    "todos": [],
})


# ── 型・インターフェース ──────────────────────────────────────────

class TestValidatorInterface:
    def test_validated_analysis_json_is_defined(self):
        assert ValidatedAnalysisJSON is not None

    def test_validate_is_callable(self):
        assert callable(validate)


# ── 正常系 ────────────────────────────────────────────────────────

class TestValidateNormal:
    def test_returns_non_none(self):
        result = validate(_VALID_JSON)
        assert result is not None

    def test_summary_accessible(self):
        result = validate(_VALID_JSON)
        assert result.summary == "会議の要約テキスト"

    def test_agenda_accessible(self):
        result = validate(_VALID_JSON)
        assert result.agenda == ["議題A", "議題B"]

    def test_topics_accessible(self):
        result = validate(_VALID_JSON)
        assert len(result.topics) == 1
        assert result.topics[0].title == "議題1"

    def test_decisions_accessible(self):
        result = validate(_VALID_JSON)
        assert result.decisions == ["決定事項1"]

    def test_pending_items_accessible(self):
        result = validate(_VALID_JSON)
        assert result.pending_items == ["保留事項1"]

    def test_todos_accessible(self):
        result = validate(_VALID_JSON)
        assert len(result.todos) == 1
        assert result.todos[0].task == "タスク1"

    def test_empty_agenda_passes(self):
        result = validate(_VALID_EMPTY_LISTS)
        assert result.agenda == []

    def test_empty_topics_passes(self):
        result = validate(_VALID_EMPTY_LISTS)
        assert result.topics == []

    def test_empty_decisions_passes(self):
        result = validate(_VALID_EMPTY_LISTS)
        assert result.decisions == []

    def test_empty_pending_items_passes(self):
        result = validate(_VALID_EMPTY_LISTS)
        assert result.pending_items == []

    def test_empty_todos_passes(self):
        result = validate(_VALID_EMPTY_LISTS)
        assert result.todos == []

    def test_owner_candidate_none_passes(self):
        raw = json.dumps({
            **_ALL_FIELDS,
            "todos": [{"task": "タスク", "owner_candidate": None, "due_date_candidate": None}],
        })
        result = validate(raw)
        assert result.todos[0].owner_candidate is None

    def test_due_date_candidate_none_passes(self):
        raw = json.dumps({
            **_ALL_FIELDS,
            "todos": [{"task": "タスク", "due_date_candidate": None}],
        })
        result = validate(raw)
        assert result.todos[0].due_date_candidate is None

    def test_ambiguous_due_date_preserved(self):
        raw = json.dumps({
            **_ALL_FIELDS,
            "todos": [{"task": "報告", "due_date_candidate": "月末"}],
        })
        result = validate(raw)
        assert result.todos[0].due_date_candidate == "月末"


# ── 異常系: 必須フィールド欠落 ────────────────────────────────────

_ALL_FIELDS = {"summary": "要約", "agenda": [], "topics": [], "decisions": [], "pending_items": [], "todos": []}


class TestValidateMissingFields:
    def test_missing_summary_raises_llm_error(self):
        raw = json.dumps({k: v for k, v in _ALL_FIELDS.items() if k != "summary"})
        with pytest.raises(LLMError):
            validate(raw)

    def test_missing_agenda_raises_llm_error(self):
        raw = json.dumps({k: v for k, v in _ALL_FIELDS.items() if k != "agenda"})
        with pytest.raises(LLMError):
            validate(raw)

    def test_missing_topics_raises_llm_error(self):
        raw = json.dumps({k: v for k, v in _ALL_FIELDS.items() if k != "topics"})
        with pytest.raises(LLMError):
            validate(raw)

    def test_missing_decisions_raises_llm_error(self):
        raw = json.dumps({k: v for k, v in _ALL_FIELDS.items() if k != "decisions"})
        with pytest.raises(LLMError):
            validate(raw)

    def test_missing_pending_items_raises_llm_error(self):
        raw = json.dumps({k: v for k, v in _ALL_FIELDS.items() if k != "pending_items"})
        with pytest.raises(LLMError):
            validate(raw)

    def test_missing_todos_raises_llm_error(self):
        raw = json.dumps({k: v for k, v in _ALL_FIELDS.items() if k != "todos"})
        with pytest.raises(LLMError):
            validate(raw)

    def test_empty_object_raises_llm_error(self):
        with pytest.raises(LLMError):
            validate("{}")

    def test_llm_error_message_is_informative(self):
        raw = json.dumps({k: v for k, v in _ALL_FIELDS.items() if k != "summary"})
        with pytest.raises(LLMError, match=r".+"):
            validate(raw)


# ── 異常系: 型不一致 ─────────────────────────────────────────────

class TestValidateTypeMismatch:
    def test_summary_none_raises_llm_error(self):
        raw = json.dumps({**_ALL_FIELDS, "summary": None})
        with pytest.raises(LLMError):
            validate(raw)

    def test_agenda_not_list_raises_llm_error(self):
        raw = json.dumps({**_ALL_FIELDS, "agenda": "リストではない"})
        with pytest.raises(LLMError):
            validate(raw)

    def test_topics_not_list_raises_llm_error(self):
        raw = json.dumps({**_ALL_FIELDS, "topics": "リストではない"})
        with pytest.raises(LLMError):
            validate(raw)

    def test_decisions_not_list_raises_llm_error(self):
        raw = json.dumps({**_ALL_FIELDS, "decisions": "リストではない"})
        with pytest.raises(LLMError):
            validate(raw)

    def test_todos_not_list_raises_llm_error(self):
        raw = json.dumps({**_ALL_FIELDS, "todos": "リストではない"})
        with pytest.raises(LLMError):
            validate(raw)

    def test_topic_missing_title_raises_llm_error(self):
        raw = json.dumps({**_ALL_FIELDS, "topics": [{"summary": "説明", "key_points": []}]})
        with pytest.raises(LLMError):
            validate(raw)

    def test_topic_missing_key_points_raises_llm_error(self):
        raw = json.dumps({**_ALL_FIELDS, "topics": [{"title": "議題", "summary": "説明"}]})
        with pytest.raises(LLMError):
            validate(raw)

    def test_todo_missing_task_raises_llm_error(self):
        raw = json.dumps({**_ALL_FIELDS, "todos": [{"owner_candidate": "田中"}]})
        with pytest.raises(LLMError):
            validate(raw)


# ── 異常系: JSON parse 失敗 ───────────────────────────────────────

class TestValidateParseError:
    def test_invalid_json_raises_llm_error(self):
        with pytest.raises(LLMError):
            validate("not valid json")

    def test_empty_string_raises_llm_error(self):
        with pytest.raises(LLMError):
            validate("")

    def test_partial_json_raises_llm_error(self):
        with pytest.raises(LLMError):
            validate('{"summary": "テスト"')

    def test_json_array_raises_llm_error(self):
        with pytest.raises(LLMError):
            validate('["not", "an", "object"]')

    def test_llm_error_is_raised_not_original_exception(self):
        with pytest.raises(LLMError):
            validate("not json at all")
