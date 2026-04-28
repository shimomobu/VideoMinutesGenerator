"""analysis.extractor — Ollama（ローカルLLM）を呼び出して RawAnalysisJSON を取得する"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from vmg.analysis.input_builder import PromptInput

if TYPE_CHECKING:
    from vmg.common.logger import StructuredLogger

# 未検証 JSON 文字列の型エイリアス
RawAnalysisJSON = str


class LLMError(Exception):
    pass


class LLMTimeoutError(LLMError):
    """Ollama 呼び出しがタイムアウトした場合の例外。リトライ対象外。"""
    pass


_SYSTEM_PROMPT = (
    "あなたは会議の文字起こしを分析するアシスタントです。"
    "以下の文字起こしを分析し、次のJSONスキーマで出力してください:\n"
    '{"summary": "string", "agenda": ["string"], '
    '"topics": [{"title": "string", "summary": "string", "key_points": ["string"]}], '
    '"decisions": ["string"], "pending_items": ["string"], '
    '"todos": [{"task": "string", "owner_candidate": null, "due_date_candidate": null, "notes": null}]}'
)


def extract(
    prompt_input: PromptInput,
    model: str,
    base_url: str,
    max_retries: int = 3,
    timeout_seconds: int = 900,
    logger: "StructuredLogger | None" = None,
) -> RawAnalysisJSON:
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        t0 = time.time()
        try:
            result = _call_api(prompt_input.prompt, model, base_url, timeout_seconds=timeout_seconds)
            elapsed_ms = int((time.time() - t0) * 1000)
            if logger is not None:
                logger.info(
                    stage="analysis.extractor",
                    message="LLM呼び出し成功",
                    extra={
                        "model": model,
                        "timeout_seconds": timeout_seconds,
                        "input_chars": len(prompt_input.prompt),
                        "output_chars": len(result),
                        "elapsed_ms": elapsed_ms,
                        "attempt": attempt,
                    },
                )
            return result
        except LLMTimeoutError:
            elapsed_ms = int((time.time() - t0) * 1000)
            if logger is not None:
                logger.error(
                    stage="analysis.extractor",
                    message="LLM呼び出しタイムアウト",
                    extra={
                        "error_type": "timeout",
                        "elapsed_ms": elapsed_ms,
                        "model": model,
                        "timeout_seconds": timeout_seconds,
                        "input_chars": len(prompt_input.prompt),
                        "attempt": attempt,
                    },
                )
            raise
        except Exception as e:
            elapsed_ms = int((time.time() - t0) * 1000)
            if logger is not None:
                logger.warning(
                    stage="analysis.extractor",
                    message=f"LLM呼び出し失敗（リトライ {attempt}/{max_retries}）",
                    extra={
                        "error_type": type(e).__name__,
                        "elapsed_ms": elapsed_ms,
                        "model": model,
                        "timeout_seconds": timeout_seconds,
                        "input_chars": len(prompt_input.prompt),
                        "attempt": attempt,
                    },
                )
            last_error = e
    raise LLMError(
        f"Ollama 呼び出しが {max_retries} 回失敗しました: {last_error}"
    ) from last_error


def _call_api(prompt: str, model: str, base_url: str, timeout_seconds: int = 900) -> str:
    import httpx

    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }
    try:
        response = httpx.post(url, json=payload, timeout=float(timeout_seconds))
        response.raise_for_status()
    except httpx.TimeoutException as e:
        raise LLMTimeoutError(
            f"Ollama 呼び出しがタイムアウトしました: {timeout_seconds}秒 "
            f"(base_url={base_url}, model={model})"
        ) from e
    except httpx.ConnectError as e:
        raise LLMError(
            f"Ollama に接続できませんでした。"
            f"Ollama が起動しているか確認してください。"
            f"(base_url={base_url}, model={model}, 原因: {e})"
        ) from e
    except httpx.HTTPStatusError as e:
        raise LLMError(
            f"Ollama からエラーレスポンスが返りました: HTTP {e.response.status_code} "
            f"(base_url={base_url}, model={model})"
        ) from e
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    return _strip_code_block(content)


def _strip_code_block(text: str) -> str:
    """```json ... ``` または ``` ... ``` の外枠だけを除去する"""
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1 and stripped.endswith("```"):
            return stripped[first_newline + 1 : -3].strip()
    return stripped
