"""export — ファイル出力モジュール"""
from __future__ import annotations

from pathlib import Path


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
