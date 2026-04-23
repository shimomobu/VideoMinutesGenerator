"""analysis.validator — RawAnalysisJSON のスキーマバリデーション"""
from __future__ import annotations

import json

from vmg.analysis.extractor import LLMError, RawAnalysisJSON
from vmg.common.models import AnalysisResult

ValidatedAnalysisJSON = AnalysisResult


def validate(raw: RawAnalysisJSON) -> ValidatedAnalysisJSON:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as e:
        raise LLMError(f"JSON パース失敗: {e}") from e

    try:
        return AnalysisResult.model_validate(data)
    except Exception as e:
        raise LLMError(f"スキーマバリデーション失敗: {e}") from e
