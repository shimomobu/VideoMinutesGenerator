"""TASK-00-04: vmg.common.logger の単体テスト"""
import json
from datetime import datetime
from pathlib import Path

import pytest

from vmg.common.logger import StructuredLogger


# ── ヘルパー ──────────────────────────────────────────────────────

def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ── ログエントリの構造確認 ────────────────────────────────────────

class TestLogEntryStructure:
    def test_all_required_fields_present(self, tmp_path):
        logger = StructuredLogger(job_id="job-001", log_dir=tmp_path / "logs")
        logger.info(stage="ingest", message="ファイル受け付け完了")
        entries = read_jsonl(tmp_path / "logs" / "job-001.jsonl")
        assert len(entries) == 1
        entry = entries[0]
        assert "timestamp" in entry
        assert "job_id" in entry
        assert "stage" in entry
        assert "level" in entry
        assert "message" in entry
        assert "duration_ms" in entry
        assert "extra" in entry

    def test_job_id_matches(self, tmp_path):
        logger = StructuredLogger(job_id="job-abc", log_dir=tmp_path / "logs")
        logger.info(stage="ingest", message="test")
        entry = read_jsonl(tmp_path / "logs" / "job-abc.jsonl")[0]
        assert entry["job_id"] == "job-abc"

    def test_stage_field(self, tmp_path):
        logger = StructuredLogger(job_id="job-001", log_dir=tmp_path / "logs")
        logger.info(stage="preprocess", message="test")
        entry = read_jsonl(tmp_path / "logs" / "job-001.jsonl")[0]
        assert entry["stage"] == "preprocess"

    def test_level_info(self, tmp_path):
        logger = StructuredLogger(job_id="job-001", log_dir=tmp_path / "logs")
        logger.info(stage="asr", message="test")
        entry = read_jsonl(tmp_path / "logs" / "job-001.jsonl")[0]
        assert entry["level"] == "INFO"

    def test_level_warning(self, tmp_path):
        logger = StructuredLogger(job_id="job-001", log_dir=tmp_path / "logs")
        logger.warning(stage="asr", message="短い音声です")
        entry = read_jsonl(tmp_path / "logs" / "job-001.jsonl")[0]
        assert entry["level"] == "WARNING"

    def test_level_error(self, tmp_path):
        logger = StructuredLogger(job_id="job-001", log_dir=tmp_path / "logs")
        logger.error(stage="export", message="書き込み失敗")
        entry = read_jsonl(tmp_path / "logs" / "job-001.jsonl")[0]
        assert entry["level"] == "ERROR"

    def test_message_field(self, tmp_path):
        logger = StructuredLogger(job_id="job-001", log_dir=tmp_path / "logs")
        logger.info(stage="ingest", message="処理完了")
        entry = read_jsonl(tmp_path / "logs" / "job-001.jsonl")[0]
        assert entry["message"] == "処理完了"

    def test_timestamp_is_iso8601_string(self, tmp_path):
        logger = StructuredLogger(job_id="job-001", log_dir=tmp_path / "logs")
        logger.info(stage="ingest", message="test")
        entry = read_jsonl(tmp_path / "logs" / "job-001.jsonl")[0]
        ts = entry["timestamp"]
        assert isinstance(ts, str)
        datetime.fromisoformat(ts)  # ISO 8601 パースできること

    def test_duration_ms_none_by_default(self, tmp_path):
        logger = StructuredLogger(job_id="job-001", log_dir=tmp_path / "logs")
        logger.info(stage="ingest", message="test")
        entry = read_jsonl(tmp_path / "logs" / "job-001.jsonl")[0]
        assert entry["duration_ms"] is None

    def test_duration_ms_set_when_provided(self, tmp_path):
        logger = StructuredLogger(job_id="job-001", log_dir=tmp_path / "logs")
        logger.info(stage="asr", message="文字起こし完了", duration_ms=3500)
        entry = read_jsonl(tmp_path / "logs" / "job-001.jsonl")[0]
        assert entry["duration_ms"] == 3500

    def test_extra_empty_dict_by_default(self, tmp_path):
        logger = StructuredLogger(job_id="job-001", log_dir=tmp_path / "logs")
        logger.info(stage="ingest", message="test")
        entry = read_jsonl(tmp_path / "logs" / "job-001.jsonl")[0]
        assert entry["extra"] == {}

    def test_extra_dict_preserved(self, tmp_path):
        logger = StructuredLogger(job_id="job-001", log_dir=tmp_path / "logs")
        logger.info(stage="ingest", message="test", extra={"file_size_mb": 120})
        entry = read_jsonl(tmp_path / "logs" / "job-001.jsonl")[0]
        assert entry["extra"] == {"file_size_mb": 120}


# ── ステージ名フォーマット ────────────────────────────────────────

class TestStageName:
    def test_dotted_stage_name(self, tmp_path):
        logger = StructuredLogger(job_id="job-001", log_dir=tmp_path / "logs")
        logger.info(stage="analysis.extractor", message="LLM呼び出し完了")
        entry = read_jsonl(tmp_path / "logs" / "job-001.jsonl")[0]
        assert entry["stage"] == "analysis.extractor"

    def test_analysis_submodule_stages(self, tmp_path):
        logger = StructuredLogger(job_id="job-001", log_dir=tmp_path / "logs")
        for sub in ["analysis.input_builder", "analysis.extractor", "analysis.validator", "analysis.postprocess"]:
            logger.info(stage=sub, message="test")
        entries = read_jsonl(tmp_path / "logs" / "job-001.jsonl")
        stages = [e["stage"] for e in entries]
        assert "analysis.input_builder" in stages
        assert "analysis.extractor" in stages
        assert "analysis.validator" in stages
        assert "analysis.postprocess" in stages


# ── ファイル出力確認 ──────────────────────────────────────────────

class TestFileOutput:
    def test_log_file_created(self, tmp_path):
        logger = StructuredLogger(job_id="job-001", log_dir=tmp_path / "logs")
        logger.info(stage="ingest", message="test")
        assert (tmp_path / "logs" / "job-001.jsonl").exists()

    def test_log_dir_created_if_not_exists(self, tmp_path):
        log_dir = tmp_path / "new_logs" / "nested"
        logger = StructuredLogger(job_id="job-001", log_dir=log_dir)
        logger.info(stage="ingest", message="test")
        assert (log_dir / "job-001.jsonl").exists()

    def test_each_line_is_valid_json(self, tmp_path):
        logger = StructuredLogger(job_id="job-001", log_dir=tmp_path / "logs")
        logger.info(stage="ingest", message="test1")
        logger.warning(stage="asr", message="test2")
        lines = (tmp_path / "logs" / "job-001.jsonl").read_text().splitlines()
        for line in lines:
            json.loads(line)  # パース失敗で例外が上がることを確認

    def test_job_id_determines_filename(self, tmp_path):
        logger = StructuredLogger(job_id="job-xyz-999", log_dir=tmp_path / "logs")
        logger.info(stage="ingest", message="test")
        assert (tmp_path / "logs" / "job-xyz-999.jsonl").exists()


# ── 複数ステージの追記確認 ────────────────────────────────────────

class TestAppend:
    def test_multiple_calls_append_to_same_file(self, tmp_path):
        logger = StructuredLogger(job_id="job-001", log_dir=tmp_path / "logs")
        logger.info(stage="ingest", message="ステージ1")
        logger.info(stage="preprocess", message="ステージ2")
        logger.info(stage="asr", message="ステージ3")
        entries = read_jsonl(tmp_path / "logs" / "job-001.jsonl")
        assert len(entries) == 3

    def test_multiple_stages_in_same_file(self, tmp_path):
        logger = StructuredLogger(job_id="job-001", log_dir=tmp_path / "logs")
        stages = ["ingest", "preprocess", "asr", "analysis.extractor", "formatter", "export"]
        for s in stages:
            logger.info(stage=s, message=f"{s} 完了")
        entries = read_jsonl(tmp_path / "logs" / "job-001.jsonl")
        assert [e["stage"] for e in entries] == stages

    def test_second_logger_instance_appends(self, tmp_path):
        log_dir = tmp_path / "logs"
        logger1 = StructuredLogger(job_id="job-001", log_dir=log_dir)
        logger1.info(stage="ingest", message="first")
        logger2 = StructuredLogger(job_id="job-001", log_dir=log_dir)
        logger2.info(stage="preprocess", message="second")
        entries = read_jsonl(log_dir / "job-001.jsonl")
        assert len(entries) == 2

    def test_different_job_ids_separate_files(self, tmp_path):
        log_dir = tmp_path / "logs"
        StructuredLogger(job_id="job-A", log_dir=log_dir).info(stage="ingest", message="A")
        StructuredLogger(job_id="job-B", log_dir=log_dir).info(stage="ingest", message="B")
        assert (log_dir / "job-A.jsonl").exists()
        assert (log_dir / "job-B.jsonl").exists()
        assert len(read_jsonl(log_dir / "job-A.jsonl")) == 1
        assert len(read_jsonl(log_dir / "job-B.jsonl")) == 1
