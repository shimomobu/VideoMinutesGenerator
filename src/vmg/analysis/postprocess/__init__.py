"""analysis.postprocess — ValidatedAnalysisJSON を後処理して AnalysisResult を返す"""
from __future__ import annotations

from pathlib import Path

from vmg.analysis.validator import ValidatedAnalysisJSON
from vmg.common.models import AnalysisResult, Todo


def postprocess(
    validated: ValidatedAnalysisJSON,
    job_id: str,
    work_dir: str | Path = "data/work",
) -> AnalysisResult:
    result = _deduplicate(validated)
    save_analysis(result, job_id=job_id, work_dir=work_dir)
    return result


def save_analysis(
    result: AnalysisResult,
    job_id: str,
    work_dir: str | Path = "data/work",
) -> Path:
    output_dir = Path(work_dir) / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "analysis.json"
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return path


def _deduplicate(validated: ValidatedAnalysisJSON) -> AnalysisResult:
    unique_decisions = list(dict.fromkeys(validated.decisions))

    seen_tasks: set[str] = set()
    unique_todos: list[Todo] = []
    for todo in validated.todos:
        if todo.task not in seen_tasks:
            seen_tasks.add(todo.task)
            unique_todos.append(todo)

    return AnalysisResult(
        summary=validated.summary,
        agenda=validated.agenda,
        topics=validated.topics,
        decisions=unique_decisions,
        pending_items=validated.pending_items,
        todos=unique_todos,
    )
