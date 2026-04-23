"""TASK-02-01/02-02: vmg.preprocess の音声抽出・バリデーション 単体テスト"""
import struct
import wave
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vmg.ingest import IngestResult
from vmg.preprocess import ProcessingError, PreprocessResult, extract_audio, validate_audio


# ── フィクスチャ ──────────────────────────────────────────────────

@pytest.fixture
def ingest_result(tmp_path):
    f = tmp_path / "meeting.mp4"
    f.write_bytes(b"")
    return IngestResult(
        file_path=str(f),
        file_format="mp4",
        file_size_bytes=0,
    )


def _make_ok_run():
    mock = MagicMock()
    mock.returncode = 0
    mock.stderr = b""
    return mock


# ── 正常系: FFmpeg コマンド構造の確認 ────────────────────────────

class TestFfmpegCommand:
    def test_ffmpeg_is_called(self, ingest_result, tmp_path, mocker):
        run = mocker.patch("subprocess.run", return_value=_make_ok_run())
        extract_audio(ingest_result, "job-001", work_dir=tmp_path / "work")
        run.assert_called_once()

    def test_command_starts_with_ffmpeg(self, ingest_result, tmp_path, mocker):
        run = mocker.patch("subprocess.run", return_value=_make_ok_run())
        extract_audio(ingest_result, "job-001", work_dir=tmp_path / "work")
        cmd = run.call_args[0][0]
        assert cmd[0] == "ffmpeg"

    def test_command_contains_input_path(self, ingest_result, tmp_path, mocker):
        run = mocker.patch("subprocess.run", return_value=_make_ok_run())
        extract_audio(ingest_result, "job-001", work_dir=tmp_path / "work")
        cmd = run.call_args[0][0]
        assert ingest_result.file_path in cmd

    def test_command_sets_16khz_sample_rate(self, ingest_result, tmp_path, mocker):
        run = mocker.patch("subprocess.run", return_value=_make_ok_run())
        extract_audio(ingest_result, "job-001", work_dir=tmp_path / "work")
        cmd = run.call_args[0][0]
        assert "-ar" in cmd
        ar_idx = cmd.index("-ar")
        assert cmd[ar_idx + 1] == "16000"

    def test_command_sets_mono_channel(self, ingest_result, tmp_path, mocker):
        run = mocker.patch("subprocess.run", return_value=_make_ok_run())
        extract_audio(ingest_result, "job-001", work_dir=tmp_path / "work")
        cmd = run.call_args[0][0]
        assert "-ac" in cmd
        ac_idx = cmd.index("-ac")
        assert cmd[ac_idx + 1] == "1"

    def test_command_output_is_audio_wav(self, ingest_result, tmp_path, mocker):
        run = mocker.patch("subprocess.run", return_value=_make_ok_run())
        extract_audio(ingest_result, "job-001", work_dir=tmp_path / "work")
        cmd = run.call_args[0][0]
        assert cmd[-1].endswith("audio.wav")

    def test_command_contains_overwrite_flag(self, ingest_result, tmp_path, mocker):
        run = mocker.patch("subprocess.run", return_value=_make_ok_run())
        extract_audio(ingest_result, "job-001", work_dir=tmp_path / "work")
        cmd = run.call_args[0][0]
        assert "-y" in cmd

    def test_output_path_is_under_job_dir(self, ingest_result, tmp_path, mocker):
        work = tmp_path / "work"
        run = mocker.patch("subprocess.run", return_value=_make_ok_run())
        extract_audio(ingest_result, "job-001", work_dir=work)
        cmd = run.call_args[0][0]
        expected = str(work / "job-001" / "audio.wav")
        assert cmd[-1] == expected


# ── 正常系: 各入力形式 ────────────────────────────────────────────

class TestInputFormats:
    @pytest.mark.parametrize("ext", ["mp4", "mov", "mkv"])
    def test_accepts_video_format(self, ext, tmp_path, mocker):
        f = tmp_path / f"meeting.{ext}"
        f.write_bytes(b"")
        ingest = IngestResult(file_path=str(f), file_format=ext, file_size_bytes=0)
        mocker.patch("subprocess.run", return_value=_make_ok_run())
        result = extract_audio(ingest, "job-001", work_dir=tmp_path / "work")
        assert isinstance(result, PreprocessResult)


# ── 正常系: 戻り値の確認 ─────────────────────────────────────────

class TestReturnValue:
    def test_returns_preprocess_result(self, ingest_result, tmp_path, mocker):
        mocker.patch("subprocess.run", return_value=_make_ok_run())
        result = extract_audio(ingest_result, "job-001", work_dir=tmp_path / "work")
        assert isinstance(result, PreprocessResult)

    def test_audio_path_is_str(self, ingest_result, tmp_path, mocker):
        mocker.patch("subprocess.run", return_value=_make_ok_run())
        result = extract_audio(ingest_result, "job-001", work_dir=tmp_path / "work")
        assert isinstance(result.audio_path, str)

    def test_audio_path_ends_with_wav(self, ingest_result, tmp_path, mocker):
        mocker.patch("subprocess.run", return_value=_make_ok_run())
        result = extract_audio(ingest_result, "job-001", work_dir=tmp_path / "work")
        assert result.audio_path.endswith("audio.wav")

    def test_audio_path_contains_job_id(self, ingest_result, tmp_path, mocker):
        mocker.patch("subprocess.run", return_value=_make_ok_run())
        result = extract_audio(ingest_result, "job-001", work_dir=tmp_path / "work")
        assert "job-001" in result.audio_path

    def test_job_id_in_result(self, ingest_result, tmp_path, mocker):
        mocker.patch("subprocess.run", return_value=_make_ok_run())
        result = extract_audio(ingest_result, "job-001", work_dir=tmp_path / "work")
        assert result.job_id == "job-001"


# ── 正常系: 出力ディレクトリ作成 ─────────────────────────────────

class TestOutputDirectory:
    def test_job_dir_is_created(self, ingest_result, tmp_path, mocker):
        work = tmp_path / "work"
        mocker.patch("subprocess.run", return_value=_make_ok_run())
        extract_audio(ingest_result, "job-001", work_dir=work)
        assert (work / "job-001").is_dir()

    def test_nested_work_dir_created(self, ingest_result, tmp_path, mocker):
        work = tmp_path / "nested" / "work"
        mocker.patch("subprocess.run", return_value=_make_ok_run())
        extract_audio(ingest_result, "job-001", work_dir=work)
        assert (work / "job-001").is_dir()


# ── 異常系: FFmpeg 失敗 ───────────────────────────────────────────

class TestFfmpegFailure:
    def test_nonzero_returncode_raises_processing_error(self, ingest_result, tmp_path, mocker):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = b"error: invalid codec"
        mocker.patch("subprocess.run", return_value=mock_result)
        with pytest.raises(ProcessingError):
            extract_audio(ingest_result, "job-001", work_dir=tmp_path / "work")

    def test_ffmpeg_not_installed_raises_processing_error(self, ingest_result, tmp_path, mocker):
        mocker.patch("subprocess.run", side_effect=FileNotFoundError)
        with pytest.raises(ProcessingError):
            extract_audio(ingest_result, "job-001", work_dir=tmp_path / "work")

    def test_processing_error_message_on_failure(self, ingest_result, tmp_path, mocker):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = b"codec error"
        mocker.patch("subprocess.run", return_value=mock_result)
        with pytest.raises(ProcessingError, match="FFmpeg"):
            extract_audio(ingest_result, "job-001", work_dir=tmp_path / "work")

    def test_processing_error_message_on_not_installed(self, ingest_result, tmp_path, mocker):
        mocker.patch("subprocess.run", side_effect=FileNotFoundError)
        with pytest.raises(ProcessingError, match="ffmpeg"):
            extract_audio(ingest_result, "job-001", work_dir=tmp_path / "work")


# ── TASK-02-02: validate_audio ヘルパー ──────────────────────────

def _make_wav(path: Path, duration_secs: float = 10.0, sample_rate: int = 16000, silent: bool = False) -> None:
    n_frames = int(duration_secs * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        if silent or n_frames == 0:
            wf.writeframes(b"\x00" * n_frames * 2)
        else:
            wf.writeframes(struct.pack(f"<{n_frames}h", *([1000] * n_frames)))


# ── 正常系: 通常音声 ──────────────────────────────────────────────

class TestValidateAudioNormal:
    def test_returns_preprocess_result(self, tmp_path):
        wav = tmp_path / "audio.wav"
        _make_wav(wav, duration_secs=10.0)
        result = validate_audio(str(wav), "job-001")
        assert isinstance(result, PreprocessResult)

    def test_duration_seconds_correct(self, tmp_path):
        wav = tmp_path / "audio.wav"
        _make_wav(wav, duration_secs=10.0, sample_rate=16000)
        result = validate_audio(str(wav), "job-001")
        assert abs(result.duration_seconds - 10.0) < 0.1

    def test_sample_rate_correct(self, tmp_path):
        wav = tmp_path / "audio.wav"
        _make_wav(wav, duration_secs=5.0, sample_rate=16000)
        result = validate_audio(str(wav), "job-001")
        assert result.sample_rate == 16000

    def test_audio_path_in_result(self, tmp_path):
        wav = tmp_path / "audio.wav"
        _make_wav(wav)
        result = validate_audio(str(wav), "job-001")
        assert result.audio_path == str(wav)

    def test_job_id_in_result(self, tmp_path):
        wav = tmp_path / "audio.wav"
        _make_wav(wav)
        result = validate_audio(str(wav), "job-xyz")
        assert result.job_id == "job-xyz"

    def test_normal_audio_no_short_warning(self, tmp_path):
        wav = tmp_path / "audio.wav"
        _make_wav(wav, duration_secs=10.0)
        mock_logger = MagicMock()
        validate_audio(str(wav), "job-001", logger=mock_logger)
        for call in mock_logger.warning.call_args_list:
            msg = call[1].get("message", "") or (call[0][1] if len(call[0]) > 1 else "")
            assert "短" not in msg

    def test_accepts_pathlib_path(self, tmp_path):
        wav = tmp_path / "audio.wav"
        _make_wav(wav)
        result = validate_audio(wav, "job-001")
        assert isinstance(result, PreprocessResult)


# ── 正常系: 短い音声の警告 ────────────────────────────────────────

class TestValidateAudioShortWarning:
    def test_short_audio_does_not_raise(self, tmp_path):
        wav = tmp_path / "audio.wav"
        _make_wav(wav, duration_secs=3.0)
        validate_audio(str(wav), "job-001")  # 例外が出ないこと

    def test_short_audio_warns_when_logger_provided(self, tmp_path):
        wav = tmp_path / "audio.wav"
        _make_wav(wav, duration_secs=3.0)
        mock_logger = MagicMock()
        validate_audio(str(wav), "job-001", logger=mock_logger)
        mock_logger.warning.assert_called()

    def test_short_audio_without_logger_does_not_crash(self, tmp_path):
        wav = tmp_path / "audio.wav"
        _make_wav(wav, duration_secs=2.0)
        validate_audio(str(wav), "job-001", logger=None)  # クラッシュしないこと

    def test_exactly_five_seconds_does_not_warn(self, tmp_path):
        wav = tmp_path / "audio.wav"
        _make_wav(wav, duration_secs=5.0)
        mock_logger = MagicMock()
        validate_audio(str(wav), "job-001", logger=mock_logger)
        for call in mock_logger.warning.call_args_list:
            msg = call[1].get("message", "") or (call[0][1] if len(call[0]) > 1 else "")
            assert "短" not in msg


# ── 正常系: 無音ファイルの警告 ───────────────────────────────────

class TestValidateAudioSilentWarning:
    def test_silent_audio_does_not_raise(self, tmp_path):
        wav = tmp_path / "audio.wav"
        _make_wav(wav, duration_secs=10.0, silent=True)
        validate_audio(str(wav), "job-001")  # 例外が出ないこと

    def test_silent_audio_warns_when_logger_provided(self, tmp_path):
        wav = tmp_path / "audio.wav"
        _make_wav(wav, duration_secs=10.0, silent=True)
        mock_logger = MagicMock()
        validate_audio(str(wav), "job-001", logger=mock_logger)
        mock_logger.warning.assert_called()

    def test_silent_audio_without_logger_does_not_crash(self, tmp_path):
        wav = tmp_path / "audio.wav"
        _make_wav(wav, duration_secs=10.0, silent=True)
        validate_audio(str(wav), "job-001", logger=None)

    def test_non_silent_audio_not_warned(self, tmp_path):
        wav = tmp_path / "audio.wav"
        _make_wav(wav, duration_secs=10.0, silent=False)
        mock_logger = MagicMock()
        validate_audio(str(wav), "job-001", logger=mock_logger)
        mock_logger.warning.assert_not_called()


# ── 異常系: 破損・存在しないファイル ─────────────────────────────

class TestValidateAudioErrors:
    def test_corrupted_wav_raises_processing_error(self, tmp_path):
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"NOT_A_WAV_FILE_GARBAGE_CONTENT_HERE_XYZ")
        with pytest.raises(ProcessingError):
            validate_audio(str(wav), "job-001")

    def test_nonexistent_file_raises_processing_error(self, tmp_path):
        with pytest.raises(ProcessingError):
            validate_audio(str(tmp_path / "missing.wav"), "job-001")
