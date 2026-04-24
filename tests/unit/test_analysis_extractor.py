"""TASK-04-02: vmg.analysis.extractor 単体テスト（Ollama は httpx でモック化）"""
from unittest.mock import MagicMock

import pytest

from vmg.analysis.extractor import LLMError, RawAnalysisJSON, _call_api, extract
from vmg.analysis.input_builder import PromptInput

_BASE_URL = "http://localhost:11434/v1"
_MODEL = "gemma4"


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
        result = extract(prompt_input, model=_MODEL, base_url=_BASE_URL)
        assert isinstance(result, str)

    def test_returns_api_response(self, prompt_input, mocker):
        mocker.patch("vmg.analysis.extractor._call_api", return_value=_SAMPLE_JSON)
        result = extract(prompt_input, model=_MODEL, base_url=_BASE_URL)
        assert result == _SAMPLE_JSON

    def test_calls_internal_api(self, prompt_input, mocker):
        mock_call = mocker.patch("vmg.analysis.extractor._call_api", return_value=_SAMPLE_JSON)
        extract(prompt_input, model=_MODEL, base_url=_BASE_URL)
        mock_call.assert_called_once()

    def test_passes_prompt_to_api(self, prompt_input, mocker):
        mock_call = mocker.patch("vmg.analysis.extractor._call_api", return_value=_SAMPLE_JSON)
        extract(prompt_input, model=_MODEL, base_url=_BASE_URL)
        args = mock_call.call_args[0]
        assert prompt_input.prompt == args[0]

    def test_passes_model_to_api(self, prompt_input, mocker):
        mock_call = mocker.patch("vmg.analysis.extractor._call_api", return_value=_SAMPLE_JSON)
        extract(prompt_input, model="custom-model", base_url=_BASE_URL)
        args = mock_call.call_args[0]
        assert "custom-model" == args[1]

    def test_passes_base_url_to_api(self, prompt_input, mocker):
        mock_call = mocker.patch("vmg.analysis.extractor._call_api", return_value=_SAMPLE_JSON)
        extract(prompt_input, model=_MODEL, base_url="http://custom:11434/v1")
        args = mock_call.call_args[0]
        assert "http://custom:11434/v1" == args[2]

    def test_raw_json_returned_unmodified(self, prompt_input, mocker):
        raw = '{"foo": "bar", "baz": 42}'
        mocker.patch("vmg.analysis.extractor._call_api", return_value=raw)
        result = extract(prompt_input, model=_MODEL, base_url=_BASE_URL)
        assert result == raw


# ── 異常系: リトライ動作 ─────────────────────────────────────────

class TestExtractRetry:
    def test_retries_on_api_exception(self, prompt_input, mocker):
        mock_call = mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=[Exception("一時エラー"), _SAMPLE_JSON],
        )
        result = extract(prompt_input, model=_MODEL, base_url=_BASE_URL)
        assert result == _SAMPLE_JSON
        assert mock_call.call_count == 2

    def test_succeeds_on_third_attempt(self, prompt_input, mocker):
        mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=[Exception("e1"), Exception("e2"), _SAMPLE_JSON],
        )
        result = extract(prompt_input, model=_MODEL, base_url=_BASE_URL)
        assert result == _SAMPLE_JSON

    def test_raises_llm_error_after_three_failures(self, prompt_input, mocker):
        mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=[Exception("e1"), Exception("e2"), Exception("e3")],
        )
        with pytest.raises(LLMError):
            extract(prompt_input, model=_MODEL, base_url=_BASE_URL)

    def test_max_retry_count_is_three(self, prompt_input, mocker):
        mock_call = mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=Exception("常に失敗"),
        )
        with pytest.raises(LLMError):
            extract(prompt_input, model=_MODEL, base_url=_BASE_URL)
        assert mock_call.call_count == 3

    def test_llm_error_not_original_exception(self, prompt_input, mocker):
        mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=Exception("raw error"),
        )
        with pytest.raises(LLMError):
            extract(prompt_input, model=_MODEL, base_url=_BASE_URL)

    def test_llm_error_message_is_informative(self, prompt_input, mocker):
        mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=Exception("network error"),
        )
        with pytest.raises(LLMError, match=r".+"):
            extract(prompt_input, model=_MODEL, base_url=_BASE_URL)

    def test_custom_max_retries_two(self, prompt_input, mocker):
        mock_call = mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=Exception("失敗"),
        )
        with pytest.raises(LLMError):
            extract(prompt_input, model=_MODEL, base_url=_BASE_URL, max_retries=2)
        assert mock_call.call_count == 2

    def test_custom_max_retries_one(self, prompt_input, mocker):
        mock_call = mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=Exception("失敗"),
        )
        with pytest.raises(LLMError):
            extract(prompt_input, model=_MODEL, base_url=_BASE_URL, max_retries=1)
        assert mock_call.call_count == 1

    def test_timeout_seconds_passed_to_call_api(self, prompt_input, mocker):
        """timeout_seconds が _call_api に渡されること"""
        mock_call = mocker.patch("vmg.analysis.extractor._call_api", return_value=_SAMPLE_JSON)
        extract(prompt_input, model=_MODEL, base_url=_BASE_URL, timeout_seconds=300)
        assert mock_call.call_args.kwargs.get("timeout_seconds") == 300


# ── _call_api: httpx による Ollama 呼び出し構造 ───────────────────

class TestCallApi:
    def _make_httpx_mock(self, response_text: str, mocker):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": response_text}}]
        }
        mock_response.raise_for_status = MagicMock()
        return mocker.patch("httpx.post", return_value=mock_response)

    def test_returns_response_text(self, mocker):
        self._make_httpx_mock(_SAMPLE_JSON, mocker)
        result = _call_api("テストプロンプト", _MODEL, _BASE_URL)
        assert result == _SAMPLE_JSON

    def test_calls_httpx_post(self, mocker):
        mock_post = self._make_httpx_mock(_SAMPLE_JSON, mocker)
        _call_api("prompt", _MODEL, _BASE_URL)
        mock_post.assert_called_once()

    def test_posts_to_correct_url(self, mocker):
        mock_post = self._make_httpx_mock(_SAMPLE_JSON, mocker)
        _call_api("prompt", _MODEL, _BASE_URL)
        args = mock_post.call_args[0]
        assert args[0] == f"{_BASE_URL}/chat/completions"

    def test_passes_model_in_payload(self, mocker):
        mock_post = self._make_httpx_mock(_SAMPLE_JSON, mocker)
        _call_api("prompt", "custom-model", _BASE_URL)
        kwargs = mock_post.call_args[1]
        assert kwargs["json"]["model"] == "custom-model"

    def test_passes_user_prompt_in_messages(self, mocker):
        mock_post = self._make_httpx_mock(_SAMPLE_JSON, mocker)
        _call_api("テストプロンプト", _MODEL, _BASE_URL)
        kwargs = mock_post.call_args[1]
        messages = kwargs["json"]["messages"]
        assert any("テストプロンプト" in str(m) for m in messages)

    def test_passes_timeout_to_httpx(self, mocker):
        """timeout_seconds が httpx.post の timeout 引数として渡されること"""
        mock_post = self._make_httpx_mock(_SAMPLE_JSON, mocker)
        _call_api("prompt", _MODEL, _BASE_URL, timeout_seconds=300)
        assert mock_post.call_args.kwargs["timeout"] == 300.0


# ── モジュール import の安全性（httpx は遅延importで保護） ─────────

class TestModuleImportSafety:
    def test_llm_error_importable(self):
        assert LLMError is not None

    def test_extract_callable(self):
        assert callable(extract)

    def test_raw_analysis_json_type_defined(self):
        assert RawAnalysisJSON is not None
