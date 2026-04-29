"""TASK-03-01/03-02: vmg.asr の WhisperLocalProvider と transcript.json 出力 単体テスト"""
import json
import sys
from unittest.mock import MagicMock

import pytest

from vmg.asr import WhisperLocalProvider, load_transcript, save_transcript, seconds_to_hms
from vmg.common.interfaces import ASRProvider
from vmg.common.models import Transcript, TranscriptSegment


# ── ヘルパー ──────────────────────────────────────────────────────

def _make_whisper_result(segments=None, language="ja", text="テスト"):
    if segments is None:
        segments = [
            {"start": 0.0, "end": 5.0, "text": "こんにちは"},
            {"start": 5.0, "end": 10.0, "text": "ありがとう"},
        ]
    return {"segments": segments, "language": language, "text": text}


@pytest.fixture
def mock_whisper(mocker):
    mock_mod = MagicMock()
    mock_model = MagicMock()
    mock_model.transcribe.return_value = _make_whisper_result()
    mock_mod.load_model.return_value = mock_model
    mocker.patch.dict(sys.modules, {"whisper": mock_mod})
    return mock_model


# ── インターフェース確認 ──────────────────────────────────────────

class TestWhisperLocalProviderInterface:
    def test_is_subclass_of_asr_provider(self):
        assert issubclass(WhisperLocalProvider, ASRProvider)

    def test_instantiable_with_default_model(self, mock_whisper):
        provider = WhisperLocalProvider()
        assert isinstance(provider, WhisperLocalProvider)

    def test_has_transcribe_method(self, mock_whisper):
        provider = WhisperLocalProvider()
        assert callable(provider.transcribe)


# ── Lazy load / CPU 固定 ──────────────────────────────────────────

class TestLazyLoad:
    def test_init_does_not_load_whisper_model(self, mocker):
        """__init__ では whisper.load_model を呼ばないこと"""
        mock_mod = MagicMock()
        mocker.patch.dict(sys.modules, {"whisper": mock_mod})
        WhisperLocalProvider(model_name="base")
        mock_mod.load_model.assert_not_called()

    def test_transcribe_loads_model_with_cpu_device(self, tmp_path, mocker):
        """transcribe() 初回実行時に load_model(model_name, device="cpu") が呼ばれること"""
        mock_mod = MagicMock()
        mock_model = MagicMock()
        mock_model.transcribe.return_value = _make_whisper_result()
        mock_mod.load_model.return_value = mock_model
        mocker.patch.dict(sys.modules, {"whisper": mock_mod})
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        provider = WhisperLocalProvider(model_name="small")
        provider.transcribe(str(wav), "ja")
        mock_mod.load_model.assert_called_once_with("small", device="cpu")

    def test_transcribe_does_not_reload_model_on_second_call(self, tmp_path, mocker):
        """transcribe() 2回目では load_model が再呼び出しされないこと"""
        mock_mod = MagicMock()
        mock_model = MagicMock()
        mock_model.transcribe.return_value = _make_whisper_result()
        mock_mod.load_model.return_value = mock_model
        mocker.patch.dict(sys.modules, {"whisper": mock_mod})
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        provider = WhisperLocalProvider(model_name="base")
        provider.transcribe(str(wav), "ja")
        provider.transcribe(str(wav), "ja")
        mock_mod.load_model.assert_called_once_with("base", device="cpu")


# ── モデルロード ──────────────────────────────────────────────────

class TestModelLoad:
    def test_default_model_name_is_base(self, tmp_path, mocker):
        mock_mod = MagicMock()
        mock_model = MagicMock()
        mock_model.transcribe.return_value = _make_whisper_result()
        mock_mod.load_model.return_value = mock_model
        mocker.patch.dict(sys.modules, {"whisper": mock_mod})
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        WhisperLocalProvider().transcribe(str(wav), "ja")
        mock_mod.load_model.assert_called_once_with("base", device="cpu")

    def test_custom_model_name_small(self, tmp_path, mocker):
        mock_mod = MagicMock()
        mock_model = MagicMock()
        mock_model.transcribe.return_value = _make_whisper_result()
        mock_mod.load_model.return_value = mock_model
        mocker.patch.dict(sys.modules, {"whisper": mock_mod})
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        WhisperLocalProvider(model_name="small").transcribe(str(wav), "ja")
        mock_mod.load_model.assert_called_once_with("small", device="cpu")

    def test_custom_model_name_tiny(self, tmp_path, mocker):
        mock_mod = MagicMock()
        mock_model = MagicMock()
        mock_model.transcribe.return_value = _make_whisper_result()
        mock_mod.load_model.return_value = mock_model
        mocker.patch.dict(sys.modules, {"whisper": mock_mod})
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        WhisperLocalProvider(model_name="tiny").transcribe(str(wav), "ja")
        mock_mod.load_model.assert_called_once_with("tiny", device="cpu")

    def test_custom_model_name_large(self, tmp_path, mocker):
        mock_mod = MagicMock()
        mock_model = MagicMock()
        mock_model.transcribe.return_value = _make_whisper_result()
        mock_mod.load_model.return_value = mock_model
        mocker.patch.dict(sys.modules, {"whisper": mock_mod})
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        WhisperLocalProvider(model_name="large").transcribe(str(wav), "ja")
        mock_mod.load_model.assert_called_once_with("large", device="cpu")


# ── transcribe 正常系 ──────────────────────────────────────────────

class TestTranscribeNormal:
    def test_returns_transcript(self, tmp_path, mock_whisper):
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        provider = WhisperLocalProvider()
        result = provider.transcribe(str(wav), "ja")
        assert isinstance(result, Transcript)

    def test_language_matches_whisper_output(self, tmp_path, mock_whisper):
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        provider = WhisperLocalProvider()
        result = provider.transcribe(str(wav), "ja")
        assert result.language == "ja"

    def test_segments_is_list(self, tmp_path, mock_whisper):
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        provider = WhisperLocalProvider()
        result = provider.transcribe(str(wav), "ja")
        assert isinstance(result.segments, list)

    def test_segment_count_matches_whisper(self, tmp_path, mock_whisper):
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        provider = WhisperLocalProvider()
        result = provider.transcribe(str(wav), "ja")
        assert len(result.segments) == 2

    def test_segment_is_transcript_segment_instance(self, tmp_path, mock_whisper):
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        provider = WhisperLocalProvider()
        result = provider.transcribe(str(wav), "ja")
        assert isinstance(result.segments[0], TranscriptSegment)

    def test_segment_start_is_float(self, tmp_path, mock_whisper):
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        provider = WhisperLocalProvider()
        result = provider.transcribe(str(wav), "ja")
        assert isinstance(result.segments[0].start, float)

    def test_segment_end_is_float(self, tmp_path, mock_whisper):
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        provider = WhisperLocalProvider()
        result = provider.transcribe(str(wav), "ja")
        assert isinstance(result.segments[0].end, float)

    def test_segment_start_value(self, tmp_path, mock_whisper):
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        provider = WhisperLocalProvider()
        result = provider.transcribe(str(wav), "ja")
        assert result.segments[0].start == 0.0

    def test_segment_end_value(self, tmp_path, mock_whisper):
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        provider = WhisperLocalProvider()
        result = provider.transcribe(str(wav), "ja")
        assert result.segments[0].end == 5.0

    def test_segment_text_value(self, tmp_path, mock_whisper):
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        provider = WhisperLocalProvider()
        result = provider.transcribe(str(wav), "ja")
        assert result.segments[0].text == "こんにちは"

    def test_all_segments_speaker_is_none(self, tmp_path, mock_whisper):
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        provider = WhisperLocalProvider()
        result = provider.transcribe(str(wav), "ja")
        for seg in result.segments:
            assert seg.speaker is None

    def test_full_text_is_str(self, tmp_path, mock_whisper):
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        provider = WhisperLocalProvider()
        result = provider.transcribe(str(wav), "ja")
        assert isinstance(result.full_text, str)

    def test_full_text_matches_whisper_text(self, tmp_path, mock_whisper):
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        provider = WhisperLocalProvider()
        result = provider.transcribe(str(wav), "ja")
        assert result.full_text == "テスト"

    def test_whisper_transcribe_called_with_audio_path(self, tmp_path, mock_whisper):
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        provider = WhisperLocalProvider()
        provider.transcribe(str(wav), "ja")
        mock_whisper.transcribe.assert_called_once()
        args = mock_whisper.transcribe.call_args[0]
        assert str(wav) == args[0]

    def test_second_segment_values(self, tmp_path, mock_whisper):
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        provider = WhisperLocalProvider()
        result = provider.transcribe(str(wav), "ja")
        seg = result.segments[1]
        assert seg.start == 5.0
        assert seg.end == 10.0
        assert seg.text == "ありがとう"
        assert seg.speaker is None


# ── 空セグメント ──────────────────────────────────────────────────

class TestEmptySegments:
    def test_empty_whisper_output_returns_empty_segments(self, tmp_path, mocker):
        mock_mod = MagicMock()
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {"segments": [], "language": "ja", "text": ""}
        mock_mod.load_model.return_value = mock_model
        mocker.patch.dict(sys.modules, {"whisper": mock_mod})
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        provider = WhisperLocalProvider()
        result = provider.transcribe(str(wav), "ja")
        assert result.segments == []

    def test_empty_whisper_output_full_text_is_empty(self, tmp_path, mocker):
        mock_mod = MagicMock()
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {"segments": [], "language": "ja", "text": ""}
        mock_mod.load_model.return_value = mock_model
        mocker.patch.dict(sys.modules, {"whisper": mock_mod})
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        provider = WhisperLocalProvider()
        result = provider.transcribe(str(wav), "ja")
        assert result.full_text == ""


# ── HH:MM:SS タイムスタンプ変換 ───────────────────────────────────

class TestSecondsToHms:
    def test_zero_seconds(self):
        assert seconds_to_hms(0.0) == "00:00:00"

    def test_one_minute(self):
        assert seconds_to_hms(60.0) == "00:01:00"

    def test_one_hour(self):
        assert seconds_to_hms(3600.0) == "01:00:00"

    def test_mixed_time(self):
        assert seconds_to_hms(3661.0) == "01:01:01"

    def test_fractional_seconds_are_truncated(self):
        assert seconds_to_hms(5.9) == "00:00:05"

    def test_two_hours(self):
        assert seconds_to_hms(7200.0) == "02:00:00"

    def test_format_has_two_colons(self):
        result = seconds_to_hms(3600.0)
        assert result.count(":") == 2

    def test_format_is_zero_padded(self):
        result = seconds_to_hms(61.0)
        parts = result.split(":")
        assert all(len(p) == 2 for p in parts)


# ── TASK-03-02: transcript.json 出力 ─────────────────────────────

@pytest.fixture
def sample_transcript():
    return Transcript(
        language="ja",
        segments=[
            TranscriptSegment(start=0.0, end=5.0, text="こんにちは", speaker=None),
            TranscriptSegment(start=5.0, end=10.0, text="ありがとう", speaker=None),
        ],
        full_text="こんにちはありがとう",
    )


@pytest.fixture
def empty_transcript():
    return Transcript(language="ja", segments=[], full_text="")


# ── 正常系: ファイル出力 ───────────────────────────────────────────

class TestSaveTranscript:
    def test_creates_transcript_json_file(self, tmp_path, sample_transcript):
        save_transcript(sample_transcript, "job-001", work_dir=tmp_path)
        assert (tmp_path / "job-001" / "transcript.json").is_file()

    def test_returns_path_to_json(self, tmp_path, sample_transcript):
        result = save_transcript(sample_transcript, "job-001", work_dir=tmp_path)
        assert str(result).endswith("transcript.json")

    def test_output_path_contains_job_id(self, tmp_path, sample_transcript):
        result = save_transcript(sample_transcript, "job-001", work_dir=tmp_path)
        assert "job-001" in str(result)

    def test_json_contains_language_field(self, tmp_path, sample_transcript):
        save_transcript(sample_transcript, "job-001", work_dir=tmp_path)
        data = json.loads((tmp_path / "job-001" / "transcript.json").read_text())
        assert "language" in data

    def test_json_language_value(self, tmp_path, sample_transcript):
        save_transcript(sample_transcript, "job-001", work_dir=tmp_path)
        data = json.loads((tmp_path / "job-001" / "transcript.json").read_text())
        assert data["language"] == "ja"

    def test_json_contains_segments_field(self, tmp_path, sample_transcript):
        save_transcript(sample_transcript, "job-001", work_dir=tmp_path)
        data = json.loads((tmp_path / "job-001" / "transcript.json").read_text())
        assert "segments" in data

    def test_json_segments_count(self, tmp_path, sample_transcript):
        save_transcript(sample_transcript, "job-001", work_dir=tmp_path)
        data = json.loads((tmp_path / "job-001" / "transcript.json").read_text())
        assert len(data["segments"]) == 2

    def test_json_contains_full_text_field(self, tmp_path, sample_transcript):
        save_transcript(sample_transcript, "job-001", work_dir=tmp_path)
        data = json.loads((tmp_path / "job-001" / "transcript.json").read_text())
        assert "full_text" in data

    def test_json_is_valid(self, tmp_path, sample_transcript):
        save_transcript(sample_transcript, "job-001", work_dir=tmp_path)
        raw = (tmp_path / "job-001" / "transcript.json").read_text()
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)

    def test_creates_job_dir_if_not_exists(self, tmp_path, sample_transcript):
        work = tmp_path / "nested" / "work"
        save_transcript(sample_transcript, "job-001", work_dir=work)
        assert (work / "job-001" / "transcript.json").is_file()

    def test_empty_segments_saved(self, tmp_path, empty_transcript):
        save_transcript(empty_transcript, "job-001", work_dir=tmp_path)
        data = json.loads((tmp_path / "job-001" / "transcript.json").read_text())
        assert data["segments"] == []


# ── 正常系: ファイル読み込み ──────────────────────────────────────

class TestLoadTranscript:
    def test_returns_transcript_instance(self, tmp_path, sample_transcript):
        save_transcript(sample_transcript, "job-001", work_dir=tmp_path)
        result = load_transcript("job-001", work_dir=tmp_path)
        assert isinstance(result, Transcript)

    def test_language_preserved(self, tmp_path, sample_transcript):
        save_transcript(sample_transcript, "job-001", work_dir=tmp_path)
        result = load_transcript("job-001", work_dir=tmp_path)
        assert result.language == "ja"

    def test_segment_count_preserved(self, tmp_path, sample_transcript):
        save_transcript(sample_transcript, "job-001", work_dir=tmp_path)
        result = load_transcript("job-001", work_dir=tmp_path)
        assert len(result.segments) == 2

    def test_segment_fields_preserved(self, tmp_path, sample_transcript):
        save_transcript(sample_transcript, "job-001", work_dir=tmp_path)
        result = load_transcript("job-001", work_dir=tmp_path)
        seg = result.segments[0]
        assert seg.start == 0.0
        assert seg.end == 5.0
        assert seg.text == "こんにちは"
        assert seg.speaker is None

    def test_full_text_preserved(self, tmp_path, sample_transcript):
        save_transcript(sample_transcript, "job-001", work_dir=tmp_path)
        result = load_transcript("job-001", work_dir=tmp_path)
        assert result.full_text == "こんにちはありがとう"

    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(Exception):
            load_transcript("no-such-job", work_dir=tmp_path)

    def test_empty_segments_loaded(self, tmp_path, empty_transcript):
        save_transcript(empty_transcript, "job-001", work_dir=tmp_path)
        result = load_transcript("job-001", work_dir=tmp_path)
        assert result.segments == []


# ── initial_prompt ───────────────────────────────────────────────

class TestInitialPrompt:
    def test_no_initial_prompt_not_passed_to_transcribe(self, tmp_path, mocker):
        """initial_prompt 未設定の場合、transcribe に initial_prompt を渡さないこと"""
        mock_mod = MagicMock()
        mock_model = MagicMock()
        mock_model.transcribe.return_value = _make_whisper_result()
        mock_mod.load_model.return_value = mock_model
        mocker.patch.dict(sys.modules, {"whisper": mock_mod})
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        provider = WhisperLocalProvider()
        provider.transcribe(str(wav), "ja")
        _, kwargs = mock_model.transcribe.call_args
        assert "initial_prompt" not in kwargs

    def test_empty_initial_prompt_not_passed_to_transcribe(self, tmp_path, mocker):
        """initial_prompt が空文字の場合、transcribe に initial_prompt を渡さないこと"""
        mock_mod = MagicMock()
        mock_model = MagicMock()
        mock_model.transcribe.return_value = _make_whisper_result()
        mock_mod.load_model.return_value = mock_model
        mocker.patch.dict(sys.modules, {"whisper": mock_mod})
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        provider = WhisperLocalProvider(initial_prompt="")
        provider.transcribe(str(wav), "ja")
        _, kwargs = mock_model.transcribe.call_args
        assert "initial_prompt" not in kwargs

    def test_initial_prompt_passed_to_transcribe_when_set(self, tmp_path, mocker):
        """initial_prompt が設定されていれば transcribe に渡すこと"""
        mock_mod = MagicMock()
        mock_model = MagicMock()
        mock_model.transcribe.return_value = _make_whisper_result()
        mock_mod.load_model.return_value = mock_model
        mocker.patch.dict(sys.modules, {"whisper": mock_mod})
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"")
        provider = WhisperLocalProvider(initial_prompt="これは会議の録音です")
        provider.transcribe(str(wav), "ja")
        _, kwargs = mock_model.transcribe.call_args
        assert kwargs.get("initial_prompt") == "これは会議の録音です"


# ── シリアライズ → デシリアライズ往復 ───────────────────────────────

class TestTranscriptRoundTrip:
    def test_roundtrip_preserves_language(self, tmp_path, sample_transcript):
        save_transcript(sample_transcript, "job-rt", work_dir=tmp_path)
        loaded = load_transcript("job-rt", work_dir=tmp_path)
        assert loaded.language == sample_transcript.language

    def test_roundtrip_preserves_segment_count(self, tmp_path, sample_transcript):
        save_transcript(sample_transcript, "job-rt", work_dir=tmp_path)
        loaded = load_transcript("job-rt", work_dir=tmp_path)
        assert len(loaded.segments) == len(sample_transcript.segments)

    def test_roundtrip_preserves_segment_start(self, tmp_path, sample_transcript):
        save_transcript(sample_transcript, "job-rt", work_dir=tmp_path)
        loaded = load_transcript("job-rt", work_dir=tmp_path)
        assert loaded.segments[0].start == sample_transcript.segments[0].start

    def test_roundtrip_preserves_segment_end(self, tmp_path, sample_transcript):
        save_transcript(sample_transcript, "job-rt", work_dir=tmp_path)
        loaded = load_transcript("job-rt", work_dir=tmp_path)
        assert loaded.segments[0].end == sample_transcript.segments[0].end

    def test_roundtrip_preserves_segment_text(self, tmp_path, sample_transcript):
        save_transcript(sample_transcript, "job-rt", work_dir=tmp_path)
        loaded = load_transcript("job-rt", work_dir=tmp_path)
        assert loaded.segments[0].text == sample_transcript.segments[0].text

    def test_roundtrip_preserves_speaker_none(self, tmp_path, sample_transcript):
        save_transcript(sample_transcript, "job-rt", work_dir=tmp_path)
        loaded = load_transcript("job-rt", work_dir=tmp_path)
        for seg in loaded.segments:
            assert seg.speaker is None

    def test_roundtrip_preserves_full_text(self, tmp_path, sample_transcript):
        save_transcript(sample_transcript, "job-rt", work_dir=tmp_path)
        loaded = load_transcript("job-rt", work_dir=tmp_path)
        assert loaded.full_text == sample_transcript.full_text

    def test_roundtrip_empty_segments(self, tmp_path, empty_transcript):
        save_transcript(empty_transcript, "job-rt", work_dir=tmp_path)
        loaded = load_transcript("job-rt", work_dir=tmp_path)
        assert loaded.segments == []
        assert loaded.full_text == ""
