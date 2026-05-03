"""API レイヤーの単体テスト — POST /jobs / GET /jobs/{id} / GET /jobs/{id}/result"""
from __future__ import annotations

import json
import threading
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi", reason="fastapi が未インストールのためスキップ")

from fastapi.testclient import TestClient

from api.app import create_app
from api import service as api_service
from api.models import JobStatus
from vmg.pipeline import PipelineResult


# ── フィクスチャ ───────────────────────────────────────────────

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    """各テストに専用の SQLite DB を割り当てる"""
    api_service.init_repo(tmp_path / "test_jobs.db")
    yield


@pytest.fixture()
def client():
    return TestClient(create_app())


def _fake_file(content: bytes = b"fake video") -> BytesIO:
    return BytesIO(content)


# ── POST /jobs ────────────────────────────────────────────────

def test_post_jobs_returns_202_with_job_id(client):
    with patch("api.service.submit_job"):
        resp = client.post(
            "/jobs",
            data={"title": "週次定例", "datetime": "2026-05-01T10:00:00", "participants": "田中,佐藤"},
            files={"file": ("meeting.mp4", _fake_file(), "video/mp4")},
        )
    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body
    assert isinstance(body["job_id"], str)
    assert len(body["job_id"]) > 0


def test_post_jobs_job_id_starts_with_api(client):
    with patch("api.service.submit_job"):
        resp = client.post(
            "/jobs",
            data={"title": "週次定例", "datetime": "2026-05-01T10:00:00", "participants": "田中"},
            files={"file": ("meeting.mp4", _fake_file(), "video/mp4")},
        )
    assert resp.json()["job_id"].startswith("api_")


def test_post_jobs_rejects_unsupported_file_type(client):
    resp = client.post(
        "/jobs",
        data={"title": "テスト", "datetime": "2026-05-01T10:00:00", "participants": "田中"},
        files={"file": ("doc.txt", _fake_file(), "text/plain")},
    )
    assert resp.status_code == 400


def test_post_jobs_accepts_audio_file(client):
    with patch("api.service.submit_job"):
        resp = client.post(
            "/jobs",
            data={"title": "週次定例", "datetime": "2026-05-01T10:00:00", "participants": "田中"},
            files={"file": ("audio.wav", _fake_file(), "audio/wav")},
        )
    assert resp.status_code == 202


# ── GET /jobs/{job_id} ────────────────────────────────────────

def test_get_job_status_returns_pending_after_submit(client):
    with patch("api.service.submit_job"):
        post_resp = client.post(
            "/jobs",
            data={"title": "週次定例", "datetime": "2026-05-01T10:00:00", "participants": "田中"},
            files={"file": ("meeting.mp4", _fake_file(), "video/mp4")},
        )
    job_id = post_resp.json()["job_id"]

    resp = client.get(f"/jobs/{job_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == job_id
    assert body["status"] == "pending"


def test_get_job_status_not_found(client):
    resp = client.get("/jobs/nonexistent_job_id")
    assert resp.status_code == 404


def test_get_job_status_error_field_when_failed(client):
    with patch("api.service.submit_job"):
        post_resp = client.post(
            "/jobs",
            data={"title": "週次定例", "datetime": "2026-05-01T10:00:00", "participants": "田中"},
            files={"file": ("meeting.mp4", _fake_file(), "video/mp4")},
        )
    job_id = post_resp.json()["job_id"]

    api_service._repo.set_failed(job_id, "テストエラー")

    resp = client.get(f"/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"
    assert resp.json()["error"] == "テストエラー"


# ── GET /jobs/{job_id}/result ─────────────────────────────────

def test_get_job_result_not_found(client):
    resp = client.get("/jobs/nonexistent_job_id/result")
    assert resp.status_code == 404


def test_get_job_result_returns_409_when_pending(client):
    with patch("api.service.submit_job"):
        post_resp = client.post(
            "/jobs",
            data={"title": "週次定例", "datetime": "2026-05-01T10:00:00", "participants": "田中"},
            files={"file": ("meeting.mp4", _fake_file(), "video/mp4")},
        )
    job_id = post_resp.json()["job_id"]

    resp = client.get(f"/jobs/{job_id}/result")
    assert resp.status_code == 409


def test_get_job_result_returns_409_when_running(client):
    with patch("api.service.submit_job"):
        post_resp = client.post(
            "/jobs",
            data={"title": "週次定例", "datetime": "2026-05-01T10:00:00", "participants": "田中"},
            files={"file": ("meeting.mp4", _fake_file(), "video/mp4")},
        )
    job_id = post_resp.json()["job_id"]

    api_service._repo.set_running(job_id)

    resp = client.get(f"/jobs/{job_id}/result")
    assert resp.status_code == 409


def test_get_job_result_json_when_completed(client, tmp_path):
    json_content = {"meeting_info": {"title": "週次定例"}, "summary": "テスト要約"}
    json_path = tmp_path / "minutes.json"
    json_path.write_text(json.dumps(json_content), encoding="utf-8")
    md_path = tmp_path / "minutes.md"
    md_path.write_text("# 議事録\n\nテスト", encoding="utf-8")

    with patch("api.service.submit_job"):
        post_resp = client.post(
            "/jobs",
            data={"title": "週次定例", "datetime": "2026-05-01T10:00:00", "participants": "田中"},
            files={"file": ("meeting.mp4", _fake_file(), "video/mp4")},
        )
    job_id = post_resp.json()["job_id"]

    api_service._repo.set_completed(
        job_id,
        str(md_path),
        str(json_path),
        str(tmp_path / "manifest.json"),
    )

    resp = client.get(f"/jobs/{job_id}/result")
    assert resp.status_code == 200
    assert resp.json()["meeting_info"]["title"] == "週次定例"


def test_get_job_result_returns_400_for_invalid_format(client, tmp_path):
    json_path = tmp_path / "minutes.json"
    json_path.write_text("{}", encoding="utf-8")
    md_path = tmp_path / "minutes.md"
    md_path.write_text("# テスト", encoding="utf-8")

    with patch("api.service.submit_job"):
        post_resp = client.post(
            "/jobs",
            data={"title": "週次定例", "datetime": "2026-05-01T10:00:00", "participants": "田中"},
            files={"file": ("meeting.mp4", _fake_file(), "video/mp4")},
        )
    job_id = post_resp.json()["job_id"]

    api_service._repo.set_completed(
        job_id,
        str(md_path),
        str(json_path),
        str(tmp_path / "manifest.json"),
    )

    resp = client.get(f"/jobs/{job_id}/result?format=xml")
    assert resp.status_code == 400


def test_get_job_result_markdown_when_format_md(client, tmp_path):
    md_path = tmp_path / "minutes.md"
    md_path.write_text("# 議事録\n\nテスト", encoding="utf-8")
    json_path = tmp_path / "minutes.json"
    json_path.write_text("{}", encoding="utf-8")

    with patch("api.service.submit_job"):
        post_resp = client.post(
            "/jobs",
            data={"title": "週次定例", "datetime": "2026-05-01T10:00:00", "participants": "田中"},
            files={"file": ("meeting.mp4", _fake_file(), "video/mp4")},
        )
    job_id = post_resp.json()["job_id"]

    api_service._repo.set_completed(
        job_id,
        str(md_path),
        str(json_path),
        str(tmp_path / "manifest.json"),
    )

    resp = client.get(f"/jobs/{job_id}/result?format=md")
    assert resp.status_code == 200
    assert "議事録" in resp.text


# ── 状態遷移テスト ────────────────────────────────────────────

def test_job_state_transitions():
    """pending → running → completed の状態遷移を直接検証"""
    job_id = "test_state_transitions"

    record = api_service.create_job(job_id)
    assert record.status == JobStatus.pending

    api_service._repo.set_running(job_id)
    assert api_service.get_job(job_id).status == JobStatus.running

    api_service._repo.set_completed(job_id, "/md", "/json", "/manifest")
    assert api_service.get_job(job_id).status == JobStatus.completed


def test_submit_job_executes_in_background(tmp_path):
    """submit_job がバックグラウンドスレッドで run_pipeline を呼び出すことを確認"""
    completed = threading.Event()
    captured: dict = {}

    def mock_run_pipeline(**kwargs):
        captured["job_id"] = kwargs.get("job_id")
        return PipelineResult(
            job_id=kwargs.get("job_id", ""),
            markdown_path=str(tmp_path / "minutes.md"),
            json_path=str(tmp_path / "minutes.json"),
            manifest_path=str(tmp_path / "manifest.json"),
        )

    job_id = "bg_test_job"
    api_service.create_job(job_id)

    upload_path = tmp_path / "original.mp4"
    upload_path.write_bytes(b"fake video")

    with patch("api.service.run_pipeline", side_effect=mock_run_pipeline), \
         patch("api.service.load_config") as mock_cfg, \
         patch("api.service.WhisperLocalProvider"), \
         patch("api.service.StandardFormatter"):
        mock_cfg.return_value.whisper_model = "base"
        mock_cfg.return_value.whisper_initial_prompt = None
        mock_cfg.return_value.llm_model = "gemma4"
        mock_cfg.return_value.ollama_base_url = "http://localhost:11434"
        mock_cfg.return_value.llm_timeout_seconds = 30
        mock_cfg.return_value.llm_max_retries = 1
        mock_cfg.return_value.correction_rules = []
        mock_cfg.return_value.correction_enabled = False
        mock_cfg.return_value.paths.work_dir = "data/work"
        mock_cfg.return_value.paths.output_dir = "data/output"
        mock_cfg.return_value.paths.log_dir = "logs"

        api_service.submit_job(
            job_id=job_id,
            upload_path=upload_path,
            title="テスト",
            datetime_str="2026-05-01T10:00:00",
            participants=["田中"],
            on_complete=lambda: completed.set(),
        )

        completed.wait(timeout=5)
    record = api_service.get_job(job_id)
    assert record.status == JobStatus.completed
    assert captured["job_id"] == job_id


# ── アップロードファイル保存テスト ─────────────────────────────

def test_post_jobs_saves_file_to_upload_dir(client, tmp_path):
    """アップロードファイルがチャンク保存されること"""
    with patch("api.routes._UPLOAD_DIR", tmp_path / "upload"), \
         patch("api.service.submit_job"):
        resp = client.post(
            "/jobs",
            data={"title": "週次定例", "datetime": "2026-05-01T10:00:00", "participants": "田中"},
            files={"file": ("meeting.mp4", _fake_file(b"video data"), "video/mp4")},
        )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]
    upload_file = tmp_path / "upload" / job_id / "original.mp4"
    assert upload_file.exists()
    assert upload_file.read_bytes() == b"video data"


def test_post_jobs_413_when_file_exceeds_limit(client, tmp_path):
    """ファイルサイズが上限を超えた場合に 413 が返ること"""
    with patch("api.routes._UPLOAD_DIR", tmp_path / "upload"), \
         patch("api.routes._MAX_UPLOAD_BYTES", 5):
        resp = client.post(
            "/jobs",
            data={"title": "週次定例", "datetime": "2026-05-01T10:00:00", "participants": "田中"},
            files={"file": ("meeting.mp4", _fake_file(b"this is more than 5 bytes"), "video/mp4")},
        )
    assert resp.status_code == 413


def test_post_jobs_413_cleans_up_partial_file(client, tmp_path):
    """413 時にアップロードディレクトリが削除されること"""
    upload_dir = tmp_path / "upload"
    with patch("api.routes._UPLOAD_DIR", upload_dir), \
         patch("api.routes._MAX_UPLOAD_BYTES", 5):
        client.post(
            "/jobs",
            data={"title": "週次定例", "datetime": "2026-05-01T10:00:00", "participants": "田中"},
            files={"file": ("meeting.mp4", _fake_file(b"this is more than 5 bytes"), "video/mp4")},
        )
    if upload_dir.exists():
        for job_dir in upload_dir.iterdir():
            assert not list(job_dir.iterdir()), f"{job_dir} にファイルが残っています"


def test_get_job_result_returns_404_when_result_file_missing(client, tmp_path):
    """result ファイルが存在しない場合に 404 が返ること（500 ではない）"""
    md_path = tmp_path / "minutes.md"
    json_path = tmp_path / "minutes.json"
    # ファイルを作らない（存在しない状態）

    mock_result = PipelineResult(
        job_id="test_job",
        markdown_path=str(md_path),
        json_path=str(json_path),
        manifest_path=str(tmp_path / "manifest.json"),
    )

    with patch("api.service.submit_job"):
        post_resp = client.post(
            "/jobs",
            data={"title": "週次定例", "datetime": "2026-05-01T10:00:00", "participants": "田中"},
            files={"file": ("meeting.mp4", _fake_file(), "video/mp4")},
        )
    job_id = post_resp.json()["job_id"]

    api_service._repo.set_completed(
        job_id,
        str(md_path),
        str(json_path),
        str(tmp_path / "manifest.json"),
    )

    resp = client.get(f"/jobs/{job_id}/result")
    assert resp.status_code == 404


def test_post_jobs_cleans_up_dir_on_write_exception(client, tmp_path):
    """upload 書き込み中に例外が起きた場合、upload ディレクトリが残らないこと"""
    upload_dir = tmp_path / "upload"

    with patch("api.routes._UPLOAD_DIR", upload_dir), \
         patch("builtins.open", side_effect=OSError("ディスクフル")):
        resp = client.post(
            "/jobs",
            data={"title": "週次定例", "datetime": "2026-05-01T10:00:00", "participants": "田中"},
            files={"file": ("meeting.mp4", _fake_file(), "video/mp4")},
        )

    assert resp.status_code in (500, 400, 503)
    if upload_dir.exists():
        remaining = list(upload_dir.rglob("*"))
        assert remaining == [], f"ディレクトリが残っています: {remaining}"


def test_submit_job_stores_absolute_paths_in_db(tmp_path):
    """SQLite に保存される result_path が絶対パスであること"""
    completed = threading.Event()

    md_path = tmp_path / "minutes.md"
    json_path = tmp_path / "minutes.json"
    manifest_path = tmp_path / "manifest.json"

    def mock_run_pipeline(**kwargs):
        # 意図的に相対パスを返す — service.py が絶対パスに変換すべき
        return PipelineResult(
            job_id="abs_test_job",
            markdown_path="data/output/abs_test_job/minutes.md",
            json_path="data/output/abs_test_job/minutes.json",
            manifest_path="data/output/abs_test_job/manifest.json",
        )

    job_id = "abs_test_job"
    api_service.create_job(job_id)
    upload_path = tmp_path / "original.mp4"
    upload_path.write_bytes(b"fake")

    with patch("api.service.run_pipeline", side_effect=mock_run_pipeline), \
         patch("api.service.load_config") as mock_cfg, \
         patch("api.service.WhisperLocalProvider"), \
         patch("api.service.StandardFormatter"):
        mock_cfg.return_value.whisper_model = "base"
        mock_cfg.return_value.whisper_initial_prompt = None
        mock_cfg.return_value.llm_model = "gemma4"
        mock_cfg.return_value.ollama_base_url = "http://localhost:11434"
        mock_cfg.return_value.llm_timeout_seconds = 30
        mock_cfg.return_value.llm_max_retries = 1
        mock_cfg.return_value.correction_rules = []
        mock_cfg.return_value.correction_enabled = False
        mock_cfg.return_value.paths.work_dir = str(tmp_path / "work")
        mock_cfg.return_value.paths.output_dir = str(tmp_path / "output")
        mock_cfg.return_value.paths.log_dir = str(tmp_path / "logs")

        api_service.submit_job(
            job_id=job_id,
            upload_path=upload_path,
            title="テスト",
            datetime_str="2026-05-01T10:00:00",
            participants=["田中"],
            on_complete=lambda: completed.set(),
        )
        completed.wait(timeout=5)

    row = api_service._repo.get(job_id)
    assert row["markdown_path"] is not None
    assert Path(row["markdown_path"]).is_absolute(), f"絶対パスではありません: {row['markdown_path']}"
    assert Path(row["json_path"]).is_absolute(), f"絶対パスではありません: {row['json_path']}"
    assert Path(row["manifest_path"]).is_absolute(), f"絶対パスではありません: {row['manifest_path']}"


def test_submit_job_passes_config_dirs_to_pipeline(tmp_path):
    """submit_job が config の paths を run_pipeline に渡すことを確認"""
    completed = threading.Event()
    captured: dict = {}

    def mock_run_pipeline(**kwargs):
        captured["work_dir"] = kwargs.get("work_dir")
        captured["output_dir"] = kwargs.get("output_dir")
        captured["log_dir"] = kwargs.get("log_dir")
        return PipelineResult(
            job_id="dir_test_job",
            markdown_path=str(tmp_path / "minutes.md"),
            json_path=str(tmp_path / "minutes.json"),
            manifest_path=str(tmp_path / "manifest.json"),
        )

    job_id = "dir_test_job"
    api_service.create_job(job_id)
    upload_path = tmp_path / "original.mp4"
    upload_path.write_bytes(b"fake")

    with patch("api.service.run_pipeline", side_effect=mock_run_pipeline), \
         patch("api.service.load_config") as mock_cfg, \
         patch("api.service.WhisperLocalProvider"), \
         patch("api.service.StandardFormatter"):
        mock_cfg.return_value.whisper_model = "base"
        mock_cfg.return_value.whisper_initial_prompt = None
        mock_cfg.return_value.llm_model = "gemma4"
        mock_cfg.return_value.ollama_base_url = "http://localhost:11434"
        mock_cfg.return_value.llm_timeout_seconds = 30
        mock_cfg.return_value.llm_max_retries = 1
        mock_cfg.return_value.correction_rules = []
        mock_cfg.return_value.correction_enabled = False
        mock_cfg.return_value.paths.work_dir = "custom/work"
        mock_cfg.return_value.paths.output_dir = "custom/output"
        mock_cfg.return_value.paths.log_dir = "custom/logs"

        api_service.submit_job(
            job_id=job_id,
            upload_path=upload_path,
            title="テスト",
            datetime_str="2026-05-01T10:00:00",
            participants=["田中"],
            on_complete=lambda: completed.set(),
        )
        completed.wait(timeout=5)

    assert captured["work_dir"] == "custom/work"
    assert captured["output_dir"] == "custom/output"
    assert captured["log_dir"] == "custom/logs"
