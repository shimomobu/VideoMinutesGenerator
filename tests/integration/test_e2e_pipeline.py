"""TASK-07-04: パイプライン E2E テスト

@pytest.mark.slow でマーク。通常の CI では省略すること:
  pytest tests/unit/ tests/integration/ -m "not slow"   # slow を除外
  pytest tests/ -m slow -v                               # E2E のみ実行

実行前提（いずれか欠落時は自動スキップ）:
  - tests/fixtures/sample_short.mp4 が存在すること（< 1 分の短尺動画）
      FFmpeg が利用可能な場合は自動生成を試みる（3 秒の無音黒画面）
  - Ollama が起動していること（ollama serve）かつ gemma4 モデルが利用可能であること
  - FFmpeg がインストールされていること
  - openai-whisper がインストールされていること

手動実行例:
  ollama serve &
  pytest tests/integration/test_e2e_pipeline.py -m slow -v -s
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pytest

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
_FIXTURE_VIDEO = _FIXTURES_DIR / "sample_short.mp4"
_WHISPER_MODEL = "tiny"


# ---- 前提チェックヘルパー ----

def _ffmpeg_available() -> bool:
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, check=True, timeout=10,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _whisper_importable() -> bool:
    try:
        import whisper  # noqa: F401
        return True
    except ImportError:
        return False


# ---- fixture 動画 ----

@pytest.fixture(scope="module")
def fixture_video() -> Path:
    """短尺テスト動画を返す。未存在時は FFmpeg で 3 秒の無音黒画面動画を生成する。"""
    if _FIXTURE_VIDEO.exists():
        return _FIXTURE_VIDEO

    if not _ffmpeg_available():
        pytest.skip(
            f"fixture 動画が存在しません ({_FIXTURE_VIDEO}) かつ FFmpeg が利用できません。"
            "sample_short.mp4 を手動で配置するか FFmpeg をインストールしてください。"
        )

    _FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-f", "lavfi", "-i", "color=black:size=320x240:rate=1",
            "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
            "-t", "3",
            "-c:v", "libx264", "-c:a", "aac",
            "-shortest", "-y",
            str(_FIXTURE_VIDEO),
        ],
        capture_output=True,
        check=True,
    )
    return _FIXTURE_VIDEO


# ---- E2E コンテキスト（パイプライン実行結果） ----

@dataclass
class E2EContext:
    job_id: str
    markdown_path: Path
    json_path: Path
    manifest_path: Path
    log_dir: Path


_OLLAMA_BASE_URL = "http://localhost:11434/v1"
_OLLAMA_MODEL = "gemma4"


def _ollama_available() -> bool:
    try:
        import httpx
        httpx.get(_OLLAMA_BASE_URL.replace("/v1", ""), timeout=3.0)
        return True
    except Exception:
        return False


@pytest.fixture(scope="class")
def e2e_ctx(fixture_video, tmp_path_factory) -> E2EContext:
    """パイプラインを一度だけ実行し、テストクラス内で共有する。"""
    if not _ollama_available():
        pytest.skip("Ollama が起動していません（ollama serve を実行してください）")
    if not _ffmpeg_available():
        pytest.skip("FFmpeg がインストールされていません")
    if not _whisper_importable():
        pytest.skip("openai-whisper がインストールされていません")

    from vmg.asr import WhisperLocalProvider
    from vmg.formatter import StandardFormatter
    from vmg.pipeline import run_pipeline

    tmp = tmp_path_factory.mktemp("e2e")
    result = run_pipeline(
        video_path=fixture_video,
        title="E2Eテスト会議",
        datetime_str="2026-04-23T10:00:00",
        participants=["テスト参加者"],
        asr_provider=WhisperLocalProvider(model_name=_WHISPER_MODEL),
        formatter_provider=StandardFormatter(),
        model=_OLLAMA_MODEL,
        base_url=_OLLAMA_BASE_URL,
        work_dir=tmp / "work",
        output_dir=tmp / "output",
        log_dir=tmp / "logs",
    )
    return E2EContext(
        job_id=result.job_id,
        markdown_path=Path(result.markdown_path),
        json_path=Path(result.json_path),
        manifest_path=Path(result.manifest_path),
        log_dir=tmp / "logs",
    )


# ---- E2E テストクラス ----

@pytest.mark.slow
class TestE2EPipeline:
    """パイプライン全体の E2E テスト。@pytest.mark.slow でマーク。"""

    # -- 出力ファイルの存在確認 --

    def test_markdown_file_exists(self, e2e_ctx):
        """minutes.md が生成されること"""
        assert e2e_ctx.markdown_path.exists()

    def test_json_file_exists(self, e2e_ctx):
        """minutes.json が生成されること"""
        assert e2e_ctx.json_path.exists()

    def test_manifest_file_exists(self, e2e_ctx):
        """manifest.json が生成されること"""
        assert e2e_ctx.manifest_path.exists()

    # -- Markdown 構造確認 --

    def test_markdown_starts_with_heading(self, e2e_ctx):
        """minutes.md が `# 議事録` で始まること"""
        md = e2e_ctx.markdown_path.read_text(encoding="utf-8")
        assert md.strip().startswith("# 議事録")

    def test_markdown_contains_required_sections(self, e2e_ctx):
        """全8セクションのキーワードが minutes.md に含まれること"""
        md = e2e_ctx.markdown_path.read_text(encoding="utf-8")
        for section in ["会議情報", "要約", "議題", "決定事項", "保留事項", "ToDo", "参考ログ"]:
            assert section in md, f"セクション '{section}' が見つかりません"

    # -- JSON スキーマ確認 --

    def test_json_schema_valid(self, e2e_ctx):
        """minutes.json が MinutesOutput スキーマに準拠すること"""
        from vmg.common.models import MinutesOutput
        obj = MinutesOutput.model_validate_json(
            e2e_ctx.json_path.read_text(encoding="utf-8")
        )
        assert obj.meeting_info.title == "E2Eテスト会議"

    def test_json_todos_have_candidate_fields(self, e2e_ctx):
        """todos に owner_candidate / due_date_candidate フィールドが定義されていること"""
        from vmg.common.models import MinutesOutput
        obj = MinutesOutput.model_validate_json(
            e2e_ctx.json_path.read_text(encoding="utf-8")
        )
        for todo in obj.analysis.todos:
            assert hasattr(todo, "owner_candidate")
            assert hasattr(todo, "due_date_candidate")

    # -- manifest 整合性確認 --

    def test_manifest_job_id_matches(self, e2e_ctx):
        """manifest の job_id がパイプライン結果と一致すること"""
        data = json.loads(e2e_ctx.manifest_path.read_text(encoding="utf-8"))
        assert data["job_id"] == e2e_ctx.job_id

    def test_manifest_generated_at_is_iso8601(self, e2e_ctx):
        """manifest の generated_at が ISO8601 形式であること"""
        data = json.loads(e2e_ctx.manifest_path.read_text(encoding="utf-8"))
        datetime.fromisoformat(data["generated_at"])

    def test_manifest_files_contains_outputs(self, e2e_ctx):
        """manifest の files に minutes.md / minutes.json が含まれること"""
        data = json.loads(e2e_ctx.manifest_path.read_text(encoding="utf-8"))
        assert "minutes.md" in data["files"]
        assert "minutes.json" in data["files"]

    # -- ログ出力確認 --

    def test_log_file_exists(self, e2e_ctx):
        """logs/{job_id}.jsonl が生成されること"""
        log_file = e2e_ctx.log_dir / f"{e2e_ctx.job_id}.jsonl"
        assert log_file.exists()

    def test_log_contains_all_required_stages(self, e2e_ctx):
        """ログに全ステージのエントリが存在すること"""
        log_file = e2e_ctx.log_dir / f"{e2e_ctx.job_id}.jsonl"
        entries = [
            json.loads(line)
            for line in log_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        stages = {e["stage"] for e in entries}
        for expected in [
            "preprocess.validate",
            "asr",
            "analysis.input_builder",
            "formatter",
            "export.markdown",
            "export.json",
            "export.manifest",
        ]:
            assert expected in stages, f"ステージ '{expected}' がログに存在しません"
