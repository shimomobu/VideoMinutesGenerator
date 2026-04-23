"""analysis.extractor — Claude API を呼び出して RawAnalysisJSON を取得する"""
from __future__ import annotations

from vmg.analysis.input_builder import PromptInput

# 未検証 JSON 文字列の型エイリアス
RawAnalysisJSON = str


class LLMError(Exception):
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
    api_key: str,
    max_retries: int = 3,
) -> RawAnalysisJSON:
    last_error: Exception | None = None
    for _ in range(max_retries):
        try:
            return _call_api(prompt_input.prompt, model, api_key)
        except Exception as e:
            last_error = e
    raise LLMError(
        f"Claude API 呼び出しが {max_retries} 回失敗しました: {last_error}"
    ) from last_error


def _call_api(prompt: str, model: str, api_key: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text
