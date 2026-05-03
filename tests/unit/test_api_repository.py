"""JobRepository（SQLite）の単体テスト"""
from __future__ import annotations

import pytest

from api.models import JobStatus
from api.repository import JobRepository


@pytest.fixture()
def repo(tmp_path):
    return JobRepository(tmp_path / "jobs.db")


# ── insert / get ──────────────────────────────────────────────

def test_insert_creates_pending_job(repo):
    repo.insert("job_001")
    row = repo.get("job_001")
    assert row is not None
    assert row["job_id"] == "job_001"
    assert row["status"] == JobStatus.pending.value


def test_get_returns_none_for_unknown_job(repo):
    assert repo.get("nonexistent") is None


def test_insert_sets_created_at(repo):
    repo.insert("job_001")
    row = repo.get("job_001")
    assert row["created_at"] is not None
    assert len(row["created_at"]) > 0


def test_insert_initial_fields_are_null(repo):
    repo.insert("job_001")
    row = repo.get("job_001")
    assert row["started_at"] is None
    assert row["finished_at"] is None
    assert row["error"] is None
    assert row["markdown_path"] is None
    assert row["json_path"] is None
    assert row["manifest_path"] is None


# ── set_running ───────────────────────────────────────────────

def test_set_running_updates_status(repo):
    repo.insert("job_001")
    repo.set_running("job_001")
    row = repo.get("job_001")
    assert row["status"] == JobStatus.running.value


def test_set_running_sets_started_at(repo):
    repo.insert("job_001")
    repo.set_running("job_001")
    row = repo.get("job_001")
    assert row["started_at"] is not None


# ── set_completed ─────────────────────────────────────────────

def test_set_completed_updates_status(repo):
    repo.insert("job_001")
    repo.set_running("job_001")
    repo.set_completed("job_001", "/out/minutes.md", "/out/minutes.json", "/out/manifest.json")
    row = repo.get("job_001")
    assert row["status"] == JobStatus.completed.value


def test_set_completed_saves_result_paths(repo):
    repo.insert("job_001")
    repo.set_completed("job_001", "/out/minutes.md", "/out/minutes.json", "/out/manifest.json")
    row = repo.get("job_001")
    assert row["markdown_path"] == "/out/minutes.md"
    assert row["json_path"] == "/out/minutes.json"
    assert row["manifest_path"] == "/out/manifest.json"


def test_set_completed_sets_finished_at(repo):
    repo.insert("job_001")
    repo.set_completed("job_001", "/md", "/json", "/manifest")
    row = repo.get("job_001")
    assert row["finished_at"] is not None


# ── set_failed ────────────────────────────────────────────────

def test_set_failed_updates_status(repo):
    repo.insert("job_001")
    repo.set_failed("job_001", "パイプラインエラー")
    row = repo.get("job_001")
    assert row["status"] == JobStatus.failed.value


def test_set_failed_saves_error_message(repo):
    repo.insert("job_001")
    repo.set_failed("job_001", "パイプラインエラー")
    row = repo.get("job_001")
    assert row["error"] == "パイプラインエラー"


def test_set_failed_sets_finished_at(repo):
    repo.insert("job_001")
    repo.set_failed("job_001", "エラー")
    row = repo.get("job_001")
    assert row["finished_at"] is not None


# ── 永続化テスト（再初期化後も取得できる） ────────────────────

def test_persists_across_repo_reinit(tmp_path):
    """同じ DB パスで JobRepository を再生成しても状態が残ること"""
    db_path = tmp_path / "jobs.db"

    repo1 = JobRepository(db_path)
    repo1.insert("job_persist")
    repo1.set_completed("job_persist", "/md", "/json", "/manifest")

    repo2 = JobRepository(db_path)
    row = repo2.get("job_persist")
    assert row is not None
    assert row["status"] == JobStatus.completed.value
    assert row["markdown_path"] == "/md"


# ── clear_all（テスト用） ─────────────────────────────────────

def test_clear_all_removes_all_rows(repo):
    repo.insert("job_001")
    repo.insert("job_002")
    repo.clear_all()
    assert repo.get("job_001") is None
    assert repo.get("job_002") is None
