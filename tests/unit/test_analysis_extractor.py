"""TASK-04-02: vmg.analysis.extractor 単体テスト（Ollama は httpx でモック化）"""
from unittest.mock import MagicMock

import httpx
import pytest

from vmg.analysis.extractor import LLMError, LLMTimeoutError, RawAnalysisJSON, _call_api, extract
from vmg.analysis.input_builder import PromptInput

_BASE_URL = "http://localhost:11434"
_MODEL = "gemma4"
_TIMEOUT = 900


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
        result = extract(prompt_input, model=_MODEL, base_url=_BASE_URL, timeout_seconds=_TIMEOUT)
        assert isinstance(result, str)

    def test_returns_api_response(self, prompt_input, mocker):
        mocker.patch("vmg.analysis.extractor._call_api", return_value=_SAMPLE_JSON)
        result = extract(prompt_input, model=_MODEL, base_url=_BASE_URL, timeout_seconds=_TIMEOUT)
        assert result == _SAMPLE_JSON

    def test_calls_internal_api(self, prompt_input, mocker):
        mock_call = mocker.patch("vmg.analysis.extractor._call_api", return_value=_SAMPLE_JSON)
        extract(prompt_input, model=_MODEL, base_url=_BASE_URL, timeout_seconds=_TIMEOUT)
        mock_call.assert_called_once()

    def test_passes_prompt_to_api(self, prompt_input, mocker):
        mock_call = mocker.patch("vmg.analysis.extractor._call_api", return_value=_SAMPLE_JSON)
        extract(prompt_input, model=_MODEL, base_url=_BASE_URL, timeout_seconds=_TIMEOUT)
        args = mock_call.call_args[0]
        assert prompt_input.prompt == args[0]

    def test_passes_model_to_api(self, prompt_input, mocker):
        mock_call = mocker.patch("vmg.analysis.extractor._call_api", return_value=_SAMPLE_JSON)
        extract(prompt_input, model="custom-model", base_url=_BASE_URL, timeout_seconds=_TIMEOUT)
        args = mock_call.call_args[0]
        assert "custom-model" == args[1]

    def test_passes_base_url_to_api(self, prompt_input, mocker):
        mock_call = mocker.patch("vmg.analysis.extractor._call_api", return_value=_SAMPLE_JSON)
        extract(prompt_input, model=_MODEL, base_url="http://custom:11434/v1", timeout_seconds=_TIMEOUT)
        args = mock_call.call_args[0]
        assert "http://custom:11434/v1" == args[2]

    def test_raw_json_returned_unmodified(self, prompt_input, mocker):
        raw = '{"foo": "bar", "baz": 42}'
        mocker.patch("vmg.analysis.extractor._call_api", return_value=raw)
        result = extract(prompt_input, model=_MODEL, base_url=_BASE_URL, timeout_seconds=_TIMEOUT)
        assert result == raw


# ── 異常系: リトライ動作 ─────────────────────────────────────────

class TestExtractRetry:
    def test_retries_on_api_exception(self, prompt_input, mocker):
        mock_call = mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=[Exception("一時エラー"), _SAMPLE_JSON],
        )
        result = extract(prompt_input, model=_MODEL, base_url=_BASE_URL, timeout_seconds=_TIMEOUT)
        assert result == _SAMPLE_JSON
        assert mock_call.call_count == 2

    def test_succeeds_on_third_attempt(self, prompt_input, mocker):
        mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=[Exception("e1"), Exception("e2"), _SAMPLE_JSON],
        )
        result = extract(prompt_input, model=_MODEL, base_url=_BASE_URL, timeout_seconds=_TIMEOUT)
        assert result == _SAMPLE_JSON

    def test_raises_llm_error_after_three_failures(self, prompt_input, mocker):
        mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=[Exception("e1"), Exception("e2"), Exception("e3")],
        )
        with pytest.raises(LLMError):
            extract(prompt_input, model=_MODEL, base_url=_BASE_URL, timeout_seconds=_TIMEOUT)

    def test_max_retry_count_is_three(self, prompt_input, mocker):
        mock_call = mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=Exception("常に失敗"),
        )
        with pytest.raises(LLMError):
            extract(prompt_input, model=_MODEL, base_url=_BASE_URL, timeout_seconds=_TIMEOUT)
        assert mock_call.call_count == 3

    def test_llm_error_not_original_exception(self, prompt_input, mocker):
        mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=Exception("raw error"),
        )
        with pytest.raises(LLMError):
            extract(prompt_input, model=_MODEL, base_url=_BASE_URL, timeout_seconds=_TIMEOUT)

    def test_llm_error_message_is_informative(self, prompt_input, mocker):
        mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=Exception("network error"),
        )
        with pytest.raises(LLMError, match=r".+"):
            extract(prompt_input, model=_MODEL, base_url=_BASE_URL, timeout_seconds=_TIMEOUT)

    def test_custom_max_retries_two(self, prompt_input, mocker):
        mock_call = mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=Exception("失敗"),
        )
        with pytest.raises(LLMError):
            extract(prompt_input, model=_MODEL, base_url=_BASE_URL, timeout_seconds=_TIMEOUT, max_retries=2)
        assert mock_call.call_count == 2

    def test_custom_max_retries_one(self, prompt_input, mocker):
        mock_call = mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=Exception("失敗"),
        )
        with pytest.raises(LLMError):
            extract(prompt_input, model=_MODEL, base_url=_BASE_URL, timeout_seconds=_TIMEOUT, max_retries=1)
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
            "message": {"content": response_text}
        }
        mock_response.raise_for_status = MagicMock()
        return mocker.patch("httpx.post", return_value=mock_response)

    def test_returns_response_text(self, mocker):
        self._make_httpx_mock(_SAMPLE_JSON, mocker)
        result = _call_api("テストプロンプト", _MODEL, _BASE_URL, timeout_seconds=_TIMEOUT)
        assert result == _SAMPLE_JSON

    def test_calls_httpx_post(self, mocker):
        mock_post = self._make_httpx_mock(_SAMPLE_JSON, mocker)
        _call_api("prompt", _MODEL, _BASE_URL, timeout_seconds=_TIMEOUT)
        mock_post.assert_called_once()

    def test_posts_to_correct_url(self, mocker):
        mock_post = self._make_httpx_mock(_SAMPLE_JSON, mocker)
        _call_api("prompt", _MODEL, _BASE_URL, timeout_seconds=_TIMEOUT)
        args = mock_post.call_args[0]
        assert args[0] == f"{_BASE_URL}/api/chat"

    def test_passes_model_in_payload(self, mocker):
        mock_post = self._make_httpx_mock(_SAMPLE_JSON, mocker)
        _call_api("prompt", "custom-model", _BASE_URL, timeout_seconds=_TIMEOUT)
        kwargs = mock_post.call_args[1]
        assert kwargs["json"]["model"] == "custom-model"

    def test_passes_user_prompt_in_messages(self, mocker):
        mock_post = self._make_httpx_mock(_SAMPLE_JSON, mocker)
        _call_api("テストプロンプト", _MODEL, _BASE_URL, timeout_seconds=_TIMEOUT)
        kwargs = mock_post.call_args[1]
        messages = kwargs["json"]["messages"]
        assert any("テストプロンプト" in str(m) for m in messages)

    def test_passes_timeout_to_httpx(self, mocker):
        """timeout_seconds が httpx.post の timeout 引数として渡されること"""
        mock_post = self._make_httpx_mock(_SAMPLE_JSON, mocker)
        _call_api("prompt", _MODEL, _BASE_URL, timeout_seconds=300)
        assert mock_post.call_args.kwargs["timeout"] == 300.0

    def test_strips_markdown_code_block(self, mocker):
        """```json ... ``` 形式の応答からコードブロックが除去されること"""
        wrapped = '```json\n' + _SAMPLE_JSON + '\n```'
        self._make_httpx_mock(wrapped, mocker)
        result = _call_api("prompt", _MODEL, _BASE_URL, timeout_seconds=_TIMEOUT)
        assert result.startswith("{")
        assert "```" not in result

    def test_strips_plain_code_block(self, mocker):
        """``` ... ``` 形式（言語指定なし）でもコードブロックが除去されること"""
        wrapped = '```\n' + _SAMPLE_JSON + '\n```'
        self._make_httpx_mock(wrapped, mocker)
        result = _call_api("prompt", _MODEL, _BASE_URL, timeout_seconds=_TIMEOUT)
        assert result.startswith("{")
        assert "```" not in result

    def test_raises_llm_timeout_error_on_read_timeout(self, mocker):
        """httpx.ReadTimeout が LLMTimeoutError に変換されること"""
        mocker.patch("httpx.post", side_effect=httpx.ReadTimeout("timed out"))
        with pytest.raises(LLMTimeoutError):
            _call_api("prompt", _MODEL, _BASE_URL, timeout_seconds=_TIMEOUT)

    def test_passes_temperature_zero_in_payload(self, mocker):
        """temperature=0 がペイロードに含まれること（greedy decoding による再現性確保）"""
        mock_post = self._make_httpx_mock(_SAMPLE_JSON, mocker)
        _call_api("prompt", _MODEL, _BASE_URL, timeout_seconds=_TIMEOUT)
        kwargs = mock_post.call_args[1]
        assert kwargs["json"]["options"]["temperature"] == 0

    def test_passes_seed_in_payload(self, mocker):
        """seed=42 がペイロードに含まれること（再現性確保）"""
        mock_post = self._make_httpx_mock(_SAMPLE_JSON, mocker)
        _call_api("prompt", _MODEL, _BASE_URL, timeout_seconds=_TIMEOUT)
        kwargs = mock_post.call_args[1]
        assert kwargs["json"]["options"]["seed"] == 42


# ── timeout 時のリトライ制御 ────────────────────────────────────────

class TestExtractTimeoutBehavior:

    def test_does_not_retry_on_read_timeout(self, prompt_input, mocker):
        """_call_api が LLMTimeoutError を返した場合、max_retries に関わらずリトライしないこと"""
        mock_call = mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=LLMTimeoutError("timed out"),
        )
        with pytest.raises(LLMTimeoutError):
            extract(prompt_input, model=_MODEL, base_url=_BASE_URL, timeout_seconds=_TIMEOUT, max_retries=3)
        assert mock_call.call_count == 1

    def test_raises_llm_timeout_error_on_timeout(self, prompt_input, mocker):
        """LLMTimeoutError は LLMError のサブクラスとして raise されること"""
        mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=LLMTimeoutError("timed out"),
        )
        with pytest.raises(LLMError):
            extract(prompt_input, model=_MODEL, base_url=_BASE_URL, timeout_seconds=_TIMEOUT)

    def test_still_retries_on_connect_error(self, prompt_input, mocker):
        """ConnectError（Ollama 未起動等）は従来通りリトライすること"""
        mock_call = mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=httpx.ConnectError("接続失敗"),
        )
        with pytest.raises(LLMError):
            extract(prompt_input, model=_MODEL, base_url=_BASE_URL, timeout_seconds=_TIMEOUT, max_retries=2)
        assert mock_call.call_count == 2

    def test_still_retries_on_general_error(self, prompt_input, mocker):
        """一般的な例外は従来通りリトライすること"""
        mock_call = mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=Exception("一時エラー"),
        )
        with pytest.raises(LLMError):
            extract(prompt_input, model=_MODEL, base_url=_BASE_URL, timeout_seconds=_TIMEOUT, max_retries=2)
        assert mock_call.call_count == 2


# ── logger 引数によるログ出力 ──────────────────────────────────────

class TestExtractLogging:

    def test_success_logs_extra_fields(self, prompt_input, mocker):
        """成功時に INFO ログが model/timeout_seconds/input_chars/output_chars/elapsed_ms/attempt を含むこと"""
        mocker.patch("vmg.analysis.extractor._call_api", return_value=_SAMPLE_JSON)
        logger = MagicMock()

        extract(prompt_input, model=_MODEL, base_url=_BASE_URL, timeout_seconds=_TIMEOUT, logger=logger)

        logger.info.assert_called_once()
        extra = logger.info.call_args.kwargs["extra"]
        assert extra["model"] == _MODEL
        assert extra["timeout_seconds"] == _TIMEOUT
        assert extra["input_chars"] == len(prompt_input.prompt)
        assert extra["output_chars"] == len(_SAMPLE_JSON)
        assert "elapsed_ms" in extra
        assert extra["attempt"] == 1

    def test_timeout_logs_error_type(self, prompt_input, mocker):
        """timeout時に ERROR ログが error_type='timeout' と elapsed_ms を含むこと"""
        mocker.patch("vmg.analysis.extractor._call_api", side_effect=LLMTimeoutError("timed out"))
        logger = MagicMock()

        with pytest.raises(LLMTimeoutError):
            extract(prompt_input, model=_MODEL, base_url=_BASE_URL, timeout_seconds=_TIMEOUT, logger=logger)

        logger.error.assert_called_once()
        extra = logger.error.call_args.kwargs["extra"]
        assert extra["error_type"] == "timeout"
        assert "elapsed_ms" in extra

    def test_retry_logs_warning_with_attempt(self, prompt_input, mocker):
        """1回失敗→成功時に warning が attempt=1 で出ること"""
        mocker.patch(
            "vmg.analysis.extractor._call_api",
            side_effect=[Exception("一時エラー"), _SAMPLE_JSON],
        )
        logger = MagicMock()

        extract(prompt_input, model=_MODEL, base_url=_BASE_URL, timeout_seconds=_TIMEOUT, logger=logger, max_retries=3)

        assert logger.warning.call_count >= 1
        extra = logger.warning.call_args_list[0].kwargs["extra"]
        assert extra["attempt"] == 1
        assert "elapsed_ms" in extra
        assert "timeout_seconds" in extra

    def test_no_logger_does_not_crash(self, prompt_input, mocker):
        """logger=None（デフォルト）でもクラッシュしないこと"""
        mocker.patch("vmg.analysis.extractor._call_api", return_value=_SAMPLE_JSON)

        result = extract(prompt_input, model=_MODEL, base_url=_BASE_URL, timeout_seconds=_TIMEOUT)

        assert result == _SAMPLE_JSON


# ── モジュール import の安全性（httpx は遅延importで保護） ─────────

class TestModuleImportSafety:
    def test_llm_error_importable(self):
        assert LLMError is not None

    def test_extract_callable(self):
        assert callable(extract)

    def test_raw_analysis_json_type_defined(self):
        assert RawAnalysisJSON is not None
