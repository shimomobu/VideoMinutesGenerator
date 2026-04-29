"""TASK-01-01/01-02: vmg.ingest の動画ファイルバリデーション・ジョブID発行 単体テスト"""
import json
import pytest
from datetime import datetime
from pathlib import Path

from vmg.ingest import IngestResult, JobMeta, ValidationError, create_job, validate_input_file, validate_video_file


# ── 正常系（対応形式） ────────────────────────────────────────────

class TestValidFormats:
    def test_mp4_accepted(self, tmp_path):
        f = tmp_path / "meeting.mp4"
        f.write_bytes(b"")
        result = validate_video_file(f)
        assert isinstance(result, IngestResult)

    def test_mov_accepted(self, tmp_path):
        f = tmp_path / "meeting.mov"
        f.write_bytes(b"")
        result = validate_video_file(f)
        assert isinstance(result, IngestResult)

    def test_mkv_accepted(self, tmp_path):
        f = tmp_path / "meeting.mkv"
        f.write_bytes(b"")
        result = validate_video_file(f)
        assert isinstance(result, IngestResult)

    def test_result_file_format_mp4(self, tmp_path):
        f = tmp_path / "meeting.mp4"
        f.write_bytes(b"")
        result = validate_video_file(f)
        assert result.file_format == "mp4"

    def test_result_file_format_mov(self, tmp_path):
        f = tmp_path / "meeting.mov"
        f.write_bytes(b"")
        result = validate_video_file(f)
        assert result.file_format == "mov"

    def test_result_file_format_mkv(self, tmp_path):
        f = tmp_path / "meeting.mkv"
        f.write_bytes(b"")
        result = validate_video_file(f)
        assert result.file_format == "mkv"

    def test_result_file_path_is_str(self, tmp_path):
        f = tmp_path / "meeting.mp4"
        f.write_bytes(b"")
        result = validate_video_file(f)
        assert isinstance(result.file_path, str)

    def test_result_file_path_contains_filename(self, tmp_path):
        f = tmp_path / "meeting.mp4"
        f.write_bytes(b"")
        result = validate_video_file(f)
        assert "meeting.mp4" in result.file_path

    def test_result_file_size_zero_bytes(self, tmp_path):
        f = tmp_path / "meeting.mp4"
        f.write_bytes(b"")
        result = validate_video_file(f)
        assert result.file_size_bytes == 0

    def test_result_file_size_nonzero(self, tmp_path):
        f = tmp_path / "meeting.mp4"
        f.write_bytes(b"\x00" * 1024)
        result = validate_video_file(f)
        assert result.file_size_bytes == 1024

    def test_accepts_string_path(self, tmp_path):
        f = tmp_path / "meeting.mp4"
        f.write_bytes(b"")
        result = validate_video_file(str(f))
        assert isinstance(result, IngestResult)

    def test_accepts_pathlib_path(self, tmp_path):
        f = tmp_path / "meeting.mp4"
        f.write_bytes(b"")
        result = validate_video_file(f)
        assert isinstance(result, IngestResult)


# ── 異常系: 存在しないパス ────────────────────────────────────────

class TestNonexistentFile:
    def test_nonexistent_path_raises_validation_error(self, tmp_path):
        with pytest.raises(ValidationError):
            validate_video_file(tmp_path / "nonexistent.mp4")

    def test_error_message_contains_path(self, tmp_path):
        missing = tmp_path / "missing.mp4"
        with pytest.raises(ValidationError, match="missing.mp4"):
            validate_video_file(missing)


# ── 異常系: 非対応拡張子 ──────────────────────────────────────────

class TestUnsupportedExtension:
    def test_avi_rejected(self, tmp_path):
        f = tmp_path / "meeting.avi"
        f.write_bytes(b"")
        with pytest.raises(ValidationError):
            validate_video_file(f)

    def test_wmv_rejected(self, tmp_path):
        f = tmp_path / "meeting.wmv"
        f.write_bytes(b"")
        with pytest.raises(ValidationError):
            validate_video_file(f)

    def test_txt_rejected(self, tmp_path):
        f = tmp_path / "notes.txt"
        f.write_bytes(b"")
        with pytest.raises(ValidationError):
            validate_video_file(f)

    def test_error_message_mentions_extension(self, tmp_path):
        f = tmp_path / "meeting.avi"
        f.write_bytes(b"")
        with pytest.raises(ValidationError, match="avi"):
            validate_video_file(f)


# ── 異常系: 拡張子なし ────────────────────────────────────────────

class TestNoExtension:
    def test_no_extension_raises_validation_error(self, tmp_path):
        f = tmp_path / "meeting"
        f.write_bytes(b"")
        with pytest.raises(ValidationError):
            validate_video_file(f)

    def test_dot_only_extension_raises_validation_error(self, tmp_path):
        f = tmp_path / "meeting."
        f.write_bytes(b"")
        with pytest.raises(ValidationError):
            validate_video_file(f)


# ── TASK-01-02: create_job ────────────────────────────────────────

@pytest.fixture
def ingest_result(tmp_path):
    f = tmp_path / "meeting.mp4"
    f.write_bytes(b"")
    return validate_video_file(f)


class TestCreateJobReturnsJobMeta:
    def test_returns_job_meta_instance(self, ingest_result, tmp_path):
        result = create_job(ingest_result, work_dir=tmp_path / "work")
        assert isinstance(result, JobMeta)

    def test_job_meta_has_job_id(self, ingest_result, tmp_path):
        result = create_job(ingest_result, work_dir=tmp_path / "work")
        assert result.job_id

    def test_job_meta_has_executed_at(self, ingest_result, tmp_path):
        result = create_job(ingest_result, work_dir=tmp_path / "work")
        assert result.executed_at

    def test_job_meta_input_file_path_matches(self, ingest_result, tmp_path):
        result = create_job(ingest_result, work_dir=tmp_path / "work")
        assert result.input_file_path == ingest_result.file_path


class TestJobIdUniqueness:
    def test_same_file_produces_different_job_ids(self, ingest_result, tmp_path):
        work = tmp_path / "work"
        meta1 = create_job(ingest_result, work_dir=work)
        meta2 = create_job(ingest_result, work_dir=work)
        assert meta1.job_id != meta2.job_id

    def test_job_id_starts_with_job_prefix(self, ingest_result, tmp_path):
        result = create_job(ingest_result, work_dir=tmp_path / "work")
        assert result.job_id.startswith("job_")

    def test_job_id_is_string(self, ingest_result, tmp_path):
        result = create_job(ingest_result, work_dir=tmp_path / "work")
        assert isinstance(result.job_id, str)


class TestJobDirectory:
    def test_job_dir_is_created(self, ingest_result, tmp_path):
        work = tmp_path / "work"
        meta = create_job(ingest_result, work_dir=work)
        assert (work / meta.job_id).is_dir()

    def test_work_dir_created_if_not_exists(self, ingest_result, tmp_path):
        work = tmp_path / "nested" / "work"
        meta = create_job(ingest_result, work_dir=work)
        assert (work / meta.job_id).is_dir()

    def test_different_jobs_have_separate_dirs(self, ingest_result, tmp_path):
        work = tmp_path / "work"
        meta1 = create_job(ingest_result, work_dir=work)
        meta2 = create_job(ingest_result, work_dir=work)
        assert (work / meta1.job_id).is_dir()
        assert (work / meta2.job_id).is_dir()
        assert meta1.job_id != meta2.job_id


class TestJobMetaJson:
    def test_job_meta_json_file_created(self, ingest_result, tmp_path):
        work = tmp_path / "work"
        meta = create_job(ingest_result, work_dir=work)
        assert (work / meta.job_id / "job_meta.json").is_file()

    def test_job_meta_json_contains_job_id(self, ingest_result, tmp_path):
        work = tmp_path / "work"
        meta = create_job(ingest_result, work_dir=work)
        data = json.loads((work / meta.job_id / "job_meta.json").read_text())
        assert data["job_id"] == meta.job_id

    def test_job_meta_json_contains_executed_at(self, ingest_result, tmp_path):
        work = tmp_path / "work"
        meta = create_job(ingest_result, work_dir=work)
        data = json.loads((work / meta.job_id / "job_meta.json").read_text())
        assert "executed_at" in data

    def test_job_meta_executed_at_is_iso8601(self, ingest_result, tmp_path):
        work = tmp_path / "work"
        meta = create_job(ingest_result, work_dir=work)
        data = json.loads((work / meta.job_id / "job_meta.json").read_text())
        datetime.fromisoformat(data["executed_at"])  # ISO 8601 パースできること

    def test_job_meta_json_contains_input_file_path(self, ingest_result, tmp_path):
        work = tmp_path / "work"
        meta = create_job(ingest_result, work_dir=work)
        data = json.loads((work / meta.job_id / "job_meta.json").read_text())
        assert data["input_file_path"] == ingest_result.file_path

    def test_job_meta_json_is_valid_json(self, ingest_result, tmp_path):
        work = tmp_path / "work"
        meta = create_job(ingest_result, work_dir=work)
        raw = (work / meta.job_id / "job_meta.json").read_text()
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)

    def test_job_meta_deserializes_to_model(self, ingest_result, tmp_path):
        work = tmp_path / "work"
        meta = create_job(ingest_result, work_dir=work)
        raw = (work / meta.job_id / "job_meta.json").read_text()
        restored = JobMeta.model_validate_json(raw)
        assert restored.job_id == meta.job_id


class TestForcedJobId:
    def test_forced_job_id_is_used(self, ingest_result, tmp_path):
        """forced_job_id を指定した場合、そのIDが job_id として使用されること"""
        meta = create_job(ingest_result, work_dir=tmp_path / "work", forced_job_id="job_fixed_001")
        assert meta.job_id == "job_fixed_001"

    def test_forced_job_id_creates_correct_dir(self, ingest_result, tmp_path):
        """forced_job_id を指定した場合、対応するディレクトリが作成されること"""
        work = tmp_path / "work"
        create_job(ingest_result, work_dir=work, forced_job_id="job_fixed_001")
        assert (work / "job_fixed_001").is_dir()

    def test_none_forced_job_id_generates_new_id(self, ingest_result, tmp_path):
        """forced_job_id=None の場合は新しい job_id が自動生成されること"""
        meta = create_job(ingest_result, work_dir=tmp_path / "work", forced_job_id=None)
        assert meta.job_id.startswith("job_")


class TestValidateInputFileAudio:
    """音声ファイル形式（wav/mp3/m4a）の受け入れテスト"""

    def test_wav_accepted(self, tmp_path):
        f = tmp_path / "recording.wav"
        f.write_bytes(b"")
        result = validate_input_file(f)
        assert result.file_format == "wav"

    def test_mp3_accepted(self, tmp_path):
        f = tmp_path / "recording.mp3"
        f.write_bytes(b"")
        result = validate_input_file(f)
        assert result.file_format == "mp3"

    def test_m4a_accepted(self, tmp_path):
        f = tmp_path / "recording.m4a"
        f.write_bytes(b"")
        result = validate_input_file(f)
        assert result.file_format == "m4a"

    def test_wav_format_preserved_in_result(self, tmp_path):
        f = tmp_path / "recording.wav"
        f.write_bytes(b"")
        result = validate_input_file(f)
        assert isinstance(result, IngestResult)
        assert result.file_path == str(f)

    def test_mp3_format_preserved_in_result(self, tmp_path):
        f = tmp_path / "recording.mp3"
        f.write_bytes(b"")
        result = validate_input_file(f)
        assert isinstance(result, IngestResult)
        assert result.file_path == str(f)

    def test_validate_video_file_alias_still_works(self, tmp_path):
        """validate_video_file は validate_input_file の互換エイリアスであること"""
        f = tmp_path / "meeting.mp4"
        f.write_bytes(b"")
        result = validate_video_file(f)
        assert result.file_format == "mp4"
