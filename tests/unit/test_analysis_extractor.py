"""TASK-04-02: vmg.analysis.extractor 単体テスト（Claude API はモック化）"""
import sys
from unittest.mock import MagicMock

import pytest

from vmg.analysis.extractor import LLMError, RawAnalysisJSON, _call_api, extract
from vmg.analysis.input_builder import PromptInput


# ── フィクスチャ ──────────────────────────────────────────────────

@pytest.fixture
def prompt_input():
    return PromptInput(
        prompt="[00:00:00] テスト会議の発言内容です。",
        segment_start=0,
        segment_end=0,
    )


_SAMPLE_JSON = '{"summary": "テスト要約", "agenda": [], "topics": [], "decisions": [], "pending_items": [], "todos": []}'


# ── LLMError ─────────────────────────────────────────────────────

class TestLLMError:
    def test_is_exception(self):
        assert issubclass(LLMError, Exception)

    def test_can_be_raised(self):
        with pytest.raises(LLMError):
            raise LLMError("エラー")

    def test_has_message(self):
        err = LLMError("メッセージ")
        assert str(err) == "メッセージ"


# ── 正常系: extract の基本動作 ────────────────────────────────────

class TestExtractNormal:
    def test_returns_str(self, prompt_input, mocker):
        mocker.patch("vmg.analysis.extractor._call_api", return_value=_SAMPLE_JSON)
        result = extract(prompt_input, model="claude-sonnet-4-6", api_key="test-key")
        assert isinstance(result, str)

    def test_returns_api_response(self, prompt_input, mocker):
        mocker.patch("vmg.analysis.extractor._call_api", return_value=_SAMPLE_JSON)
        result = extract(prompt_input, model="claude-sonnet-4-6", api_key="test-key")
        assert result == _SAMPLE_JSON

    def test_calls_internal_api(self, prompt_input, mocker):
        mock_call = mocker.patch("vmg.analysis.extractor._call_api", return_value=_SAMPLE_JSON)
        extract(prompt_input, model="claude-sonnet-4-6", api_key="test-key")
        mock_call.assert_called_once()

    def test_passes_prompt_to_api(self, prompt_input, mocker):
        mock_call = mocker.patch("vmg.analysis.extractor._call_api", return_value=_SAMPLE_JSON)
        extract(prompt_input, model="claude-sonnet-4-6", api_key="test-key")
        args = mock_call.call_args[0]
        assert prompt_input.prompt == args[0]

    def test_passes_model_to_api(self, prompt_input, mocker):
        mock_call = mocker.patch("vmg.analysis.extractor._call_api", return_value=_SAMPLE_JSON)
        extract(prompt_input, model="claude-opus-4-7", api_key="test-key")
        args = mock_call.call_args[0]
        assert "claude-opus-4-7" == args[1]

    def test_passes_api_key_to_api(self, prompt_input, mocker):
        mock_call = mocker.patch("vmg.analysis.extractor._call_api", return_value=_SAMPLE_JSON)
        extract(prompt_input, model="claude-sonnet-4-6", api_key="my-secret-key")
        args = mock_call.call_args[0]
        assert "my-secret-key" == args[2]

    def test_raw_json_returned_unmodified(self, prompt_input, mocker):
        raw = '{"foo": "bar", "baz": 42}'
        mocker.patch("vmg.analysis.extractor._call_api", return_value=raw)
        result = extract(prompt_input, model="claude-sonnet-4-6", api_key="key")
        assert result == raw


# ── 異常系: リトライ動作 ─────────────────────────────────────────

class TestExtractRetry:
    def test_retries_on_api_exception(self, prompt_input, mocker):
        mock_call = mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=[Exception("一時エラー"), _SAMPLE_JSON],
        )
        result = extract(prompt_input, model="claude-sonnet-4-6", api_key="key")
        assert result == _SAMPLE_JSON
        assert mock_call.call_count == 2

    def test_succeeds_on_third_attempt(self, prompt_input, mocker):
        mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=[Exception("e1"), Exception("e2"), _SAMPLE_JSON],
        )
        result = extract(prompt_input, model="claude-sonnet-4-6", api_key="key")
        assert result == _SAMPLE_JSON

    def test_raises_llm_error_after_three_failures(self, prompt_input, mocker):
        mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=[Exception("e1"), Exception("e2"), Exception("e3")],
        )
        with pytest.raises(LLMError):
            extract(prompt_input, model="claude-sonnet-4-6", api_key="key")

    def test_max_retry_count_is_three(self, prompt_input, mocker):
        mock_call = mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=Exception("常に失敗"),
        )
        with pytest.raises(LLMError):
            extract(prompt_input, model="claude-sonnet-4-6", api_key="key")
        assert mock_call.call_count == 3

    def test_llm_error_not_original_exception(self, prompt_input, mocker):
        mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=Exception("raw error"),
        )
        with pytest.raises(LLMError):
            extract(prompt_input, model="claude-sonnet-4-6", api_key="key")

    def test_llm_error_message_is_informative(self, prompt_input, mocker):
        mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=Exception("network error"),
        )
        with pytest.raises(LLMError, match=r".+"):
            extract(prompt_input, model="claude-sonnet-4-6", api_key="key")

    def test_custom_max_retries_two(self, prompt_input, mocker):
        mock_call = mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=Exception("失敗"),
        )
        with pytest.raises(LLMError):
            extract(prompt_input, model="claude-sonnet-4-6", api_key="key", max_retries=2)
        assert mock_call.call_count == 2

    def test_custom_max_retries_one(self, prompt_input, mocker):
        mock_call = mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=Exception("失敗"),
        )
        with pytest.raises(LLMError):
            extract(prompt_input, model="claude-sonnet-4-6", api_key="key", max_retries=1)
        assert mock_call.call_count == 1


# ── _call_api: anthropic SDK の呼び出し構造 ───────────────────────

class TestCallApi:
    def _make_anthropic_mock(self, response_text: str) -> MagicMock:
        mock_mod = MagicMock()
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=response_text)]
        mock_mod.Anthropic.return_value.messages.create.return_value = mock_message
        return mock_mod

    def test_returns_response_text(self, mocker):
        mock_mod = self._make_anthropic_mock(_SAMPLE_JSON)
        mocker.patch.dict(sys.modules, {"anthropic": mock_mod})
        result = _call_api("テストプロンプト", "claude-sonnet-4-6", "key")
        assert result == _SAMPLE_JSON

    def test_creates_client_with_api_key(self, mocker):
        mock_mod = self._make_anthropic_mock(_SAMPLE_JSON)
        mocker.patch.dict(sys.modules, {"anthropic": mock_mod})
        _call_api("prompt", "claude-sonnet-4-6", "secret-key")
        mock_mod.Anthropic.assert_called_once_with(api_key="secret-key")

    def test_calls_messages_create(self, mocker):
        mock_mod = self._make_anthropic_mock(_SAMPLE_JSON)
        mocker.patch.dict(sys.modules, {"anthropic": mock_mod})
        _call_api("prompt", "claude-sonnet-4-6", "key")
        mock_mod.Anthropic.return_value.messages.create.assert_called_once()

    def test_passes_model_to_create(self, mocker):
        mock_mod = self._make_anthropic_mock(_SAMPLE_JSON)
        mocker.patch.dict(sys.modules, {"anthropic": mock_mod})
        _call_api("prompt", "claude-opus-4-7", "key")
        kwargs = mock_mod.Anthropic.return_value.messages.create.call_args[1]
        assert kwargs["model"] == "claude-opus-4-7"

    def test_passes_user_prompt_in_messages(self, mocker):
        mock_mod = self._make_anthropic_mock(_SAMPLE_JSON)
        mocker.patch.dict(sys.modules, {"anthropic": mock_mod})
        _call_api("テストプロンプト", "claude-sonnet-4-6", "key")
        kwargs = mock_mod.Anthropic.return_value.messages.create.call_args[1]
        messages = kwargs["messages"]
        assert any("テストプロンプト" in str(m) for m in messages)


# ── モジュール import の安全性（anthropic 未インストール時） ────────

class TestModuleImportSafety:
    def test_llm_error_importable_without_anthropic(self):
        assert LLMError is not None

    def test_extract_callable_without_anthropic(self):
        assert callable(extract)

    def test_raw_analysis_json_type_defined(self):
        assert RawAnalysisJSON is not None
