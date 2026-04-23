"""export — ファイル出力モジュール"""
from __future__ import annotations

import json
from pathlib import Path

from vmg.common.models import MinutesOutput


class OutputError(Exception):
    pass


def write_markdown(
    content: str,
    job_id: str,
    output_dir: Path | str = Path("data/output"),
) -> Path:
    """整形済み Markdown を {output_dir}/{job_id}/minutes.md に書き出す。"""
    out_dir = Path(output_dir) / job_id
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "minutes.md"
        out_path.write_text(content, encoding="utf-8")
    except OSError as e:
        raise OutputError(f"minutes.md の書き込みに失敗しました: {e}") from e
    return out_path


def write_manifest(
    job_id: str,
    generated_at: str,
    files: list[str],
    source_transcript: str,
    output_dir: Path | str = Path("data/output"),
) -> Path:
    """manifest.json を {output_dir}/{job_id}/manifest.json に書き出す。"""
    out_dir = Path(output_dir) / job_id
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "manifest.json"
        payload = {
            "job_id": job_id,
            "generated_at": generated_at,
            "files": files,
            "source_transcript": source_transcript,
        }
        out_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as e:
        raise OutputError(f"manifest.json の書き込みに失敗しました: {e}") from e
    return out_path


def write_json(
    minutes: MinutesOutput,
    job_id: str,
    output_dir: Path | str = Path("data/output"),
) -> Path:
    """MinutesOutput を {output_dir}/{job_id}/minutes.json に書き出す。"""
    out_dir = Path(output_dir) / job_id
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "minutes.json"
        out_path.write_text(
            json.dumps(minutes.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as e:
        raise OutputError(f"minutes.json の書き込みに失敗しました: {e}") from e
    return out_path
