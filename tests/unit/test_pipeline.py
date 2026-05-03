"""TASK-07-01/07-02: pipeline.run_pipeline の単体テスト（全ステージをモック化）"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vmg.analysis.input_builder import PromptInput
from vmg.common.models import AnalysisResult, Todo, Topic, Transcript, TranscriptSegment
from vmg.ingest import IngestResult, JobMeta
from vmg.pipeline import PipelineError, PipelineResult, run_pipeline
from vmg.preprocess import PreprocessResult, ProcessingError


# ---- フィクスチャ ----

@pytest.fixture()
def mock_asr_provider():
    from unittest.mock import MagicMock
    provider = MagicMock()
    provider.transcribe.return_value = Transcript(
        language="ja",
        segments=[TranscriptSegment(start=0.0, end=5.0, text="会議を始めます。")],
        full_text="会議を始めます。",
    )
    return provider


@pytest.fixture()
def mock_formatter_provider():
    from unittest.mock import MagicMock
    provider = MagicMock()
    provider.format.return_value = "# 議事録\n\n## 1. 会議情報\n"
    return provider


@pytest.fixture()
def sample_analysis():
    return AnalysisResult(
        summary="要約テスト",
        agenda=["議題1"],
        topics=[Topic(title="A", summary="B", key_points=[])],
        decisions=["決定1"],
        pending_items=[],
        todos=[Todo(task="タスク1")],
    )


@pytest.fixture()
def sample_transcript():
    return Transcript(
        language="ja",
        segments=[TranscriptSegment(start=0.0, end=5.0, text="テスト発言")],
        full_text="テスト発言",
    )


# ---- ヘルパー ----

_JOB_ID = "job_test_001"
_RAW_ANALYSIS = (
    '{"summary":"要約","agenda":["A"],"topics":[],"decisions":[],"pending_items":[],"todos":[]}'
)


def _patch_all(mocker, tmp_path, analysis) -> dict:
    """全ステージを正常系でモック化し、mock オブジェクトの dict を返す"""
    mocks = {}
    mocks["validate_input_file"] = mocker.patch(
        "vmg.pipeline.validate_input_file",
        return_value=IngestResult(
            file_path=str(tmp_path / "meeting.mp4"),
            file_format="mp4",
            file_size_bytes=1024,
        ),
    )
    mocker.patch(
        "vmg.pipeline.create_job",
        return_value=JobMeta(
            job_id=_JOB_ID,
            executed_at="2026-04-23T10:00:00+00:00",
            input_file_path=str(tmp_path / "meeting.mp4"),
        ),
    )
    mocker.patch(
        "vmg.pipeline.extract_audio",
        return_value=PreprocessResult(
            audio_path=str(tmp_path / _JOB_ID / "audio.wav"),
            job_id=_JOB_ID,
            duration_seconds=3600.0,
            sample_rate=16000,
        ),
    )
    mocker.patch(
        "vmg.pipeline.validate_audio",
        return_value=PreprocessResult(
            audio_path=str(tmp_path / _JOB_ID / "audio.wav"),
            job_id=_JOB_ID,
            duration_seconds=3600.0,
            sample_rate=16000,
        ),
    )
    mocker.patch(
        "vmg.pipeline.save_transcript",
        return_value=tmp_path / _JOB_ID / "transcript.json",
    )
    mocker.patch(
        "vmg.pipeline.build_prompt",
        return_value=[PromptInput(prompt="会議テキスト", segment_start=0, segment_end=0)],
    )
    mocker.patch("vmg.pipeline.extract", return_value=_RAW_ANALYSIS)
    mocker.patch("vmg.pipeline.validate_analysis", return_value=analysis)
    mocker.patch("vmg.pipeline.run_postprocess", return_value=analysis)
    mocker.patch(
        "vmg.pipeline.write_markdown",
        return_value=tmp_path / _JOB_ID / "minutes.md",
    )
    mocker.patch(
        "vmg.pipeline.write_json",
        return_value=tmp_path / _JOB_ID / "minutes.json",
    )
    mocker.patch(
        "vmg.pipeline.write_manifest",
        return_value=tmp_path / _JOB_ID / "manifest.json",
    )


def _run_pipeline(tmp_path, asr, formatter, *, force: bool = False, job_id: str | None = None):
    return run_pipeline(
        input_path=tmp_path / "meeting.mp4",
        title="テスト会議",
        datetime_str="2026-04-23T10:00:00",
        participants=["田中", "佐藤"],
        asr_provider=asr,
        formatter_provider=formatter,
        model="gemma4",
        base_url="http://localhost:11434",
        work_dir=tmp_path / "work",
        output_dir=tmp_path / "output",
        log_dir=tmp_path / "logs",
        force=force,
        job_id=job_id,
        timeout_seconds=900,
    )


# ---- TASK-07-02 用ヘルパー（中間ファイル作成） ----

def _job_dir(tmp_path) -> Path:
    d = tmp_path / "work" / _JOB_ID
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_audio_wav(tmp_path) -> Path:
    p = _job_dir(tmp_path) / "audio.wav"
    p.write_bytes(b"RIFF dummy wav")
    return p


def _write_transcript_json(tmp_path, transcript: Transcript) -> Path:
    p = _job_dir(tmp_path) / "transcript.json"
    p.write_text(transcript.model_dump_json(indent=2), encoding="utf-8")
    return p


def _write_analysis_json(tmp_path, analysis: AnalysisResult) -> Path:
    p = _job_dir(tmp_path) / "analysis.json"
    p.write_text(analysis.model_dump_json(indent=2), encoding="utf-8")
    return p


class TestPipelineRun:

    def test_returns_pipeline_result(self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis):
        """正常系: PipelineResult が返ること"""
        _patch_all(mocker, tmp_path, sample_analysis)
        result = _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider)
        assert isinstance(result, PipelineResult)

    def test_pipeline_result_contains_job_id(self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis):
        """正常系: PipelineResult に job_id が含まれること"""
        _patch_all(mocker, tmp_path, sample_analysis)
        result = _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider)
        assert result.job_id == _JOB_ID

    def test_output_paths_in_result(self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis):
        """正常系: markdown_path / json_path / manifest_path が含まれること"""
        _patch_all(mocker, tmp_path, sample_analysis)
        result = _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider)
        assert "minutes.md" in result.markdown_path
        assert "minutes.json" in result.json_path
        assert "manifest.json" in result.manifest_path

    def test_stops_on_ingest_failure(self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis):
        """ingest 失敗時に PipelineError が発生すること"""
        _patch_all(mocker, tmp_path, sample_analysis)
        mocker.patch(
            "vmg.pipeline.validate_input_file",
            side_effect=Exception("ファイルが存在しない"),
        )
        with pytest.raises(PipelineError):
            _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider)

    def test_stops_on_preprocess_failure(self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis):
        """preprocess 失敗時に PipelineError が発生すること"""
        _patch_all(mocker, tmp_path, sample_analysis)
        mocker.patch(
            "vmg.pipeline.extract_audio",
            side_effect=ProcessingError("FFmpeg 失敗"),
        )
        with pytest.raises(PipelineError):
            _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider)

    def test_stops_on_asr_failure(self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis):
        """asr 失敗時に PipelineError が発生すること"""
        _patch_all(mocker, tmp_path, sample_analysis)
        mock_asr_provider.transcribe.side_effect = Exception("Whisper 失敗")
        with pytest.raises(PipelineError):
            _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider)

    def test_stops_on_analysis_failure(self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis):
        """analysis 失敗時に PipelineError が発生すること"""
        _patch_all(mocker, tmp_path, sample_analysis)
        mocker.patch(
            "vmg.pipeline.extract",
            side_effect=Exception("Claude API 失敗"),
        )
        with pytest.raises(PipelineError):
            _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider)

    def test_stops_on_formatter_failure(self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis):
        """formatter 失敗時に PipelineError が発生すること"""
        _patch_all(mocker, tmp_path, sample_analysis)
        mock_formatter_provider.format.side_effect = Exception("テンプレートエラー")
        with pytest.raises(PipelineError):
            _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider)

    def test_stops_on_export_failure(self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis):
        """export 失敗時に PipelineError が発生すること"""
        _patch_all(mocker, tmp_path, sample_analysis)
        mocker.patch(
            "vmg.pipeline.write_markdown",
            side_effect=Exception("書き込み失敗"),
        )
        with pytest.raises(PipelineError):
            _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider)

    def test_pipeline_error_contains_stage_name(self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis):
        """PipelineError.stage に失敗ステージ名が設定されること"""
        _patch_all(mocker, tmp_path, sample_analysis)
        mocker.patch(
            "vmg.pipeline.extract_audio",
            side_effect=ProcessingError("FFmpeg 失敗"),
        )
        with pytest.raises(PipelineError) as exc_info:
            _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider)
        assert exc_info.value.stage == "preprocess"

    def test_pipeline_error_contains_original_cause(self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis):
        """PipelineError.cause に元例外が保持されること"""
        _patch_all(mocker, tmp_path, sample_analysis)
        mocker.patch(
            "vmg.pipeline.extract_audio",
            side_effect=ProcessingError("FFmpeg 失敗"),
        )
        with pytest.raises(PipelineError) as exc_info:
            _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider)
        assert isinstance(exc_info.value.cause, ProcessingError)

    def test_failure_stage_logged(self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis):
        """失敗ステージの ERROR エントリがログファイルに記録されること"""
        _patch_all(mocker, tmp_path, sample_analysis)
        mocker.patch(
            "vmg.pipeline.extract_audio",
            side_effect=ProcessingError("FFmpeg 失敗"),
        )
        with pytest.raises(PipelineError):
            _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider)

        log_file = tmp_path / "logs" / f"{_JOB_ID}.jsonl"
        entries = [
            json.loads(line)
            for line in log_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        error_entries = [e for e in entries if e["level"] == "ERROR"]
        assert any(e["stage"] == "preprocess" for e in error_entries)

    def test_empty_transcript_does_not_crash(self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis):
        """空の transcript（チャンクなし）でもクラッシュしないこと"""
        _patch_all(mocker, tmp_path, sample_analysis)
        mocker.patch("vmg.pipeline.build_prompt", return_value=[])
        result = _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider)
        assert isinstance(result, PipelineResult)


class TestPipelineSkip:
    """TASK-07-02: ステージスキップ機構のテスト"""

    def test_skips_preprocess_when_audio_wav_exists(
        self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis
    ):
        """audio.wav が存在する場合、extract_audio がスキップされること"""
        _write_audio_wav(tmp_path)
        _patch_all(mocker, tmp_path, sample_analysis)
        extract_mock = mocker.patch("vmg.pipeline.extract_audio")

        _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider)

        extract_mock.assert_not_called()

    def test_skips_asr_when_transcript_json_exists(
        self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider,
        sample_analysis, sample_transcript
    ):
        """transcript.json が存在する場合、asr_provider.transcribe がスキップされること"""
        _write_transcript_json(tmp_path, sample_transcript)
        _patch_all(mocker, tmp_path, sample_analysis)

        _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider)

        mock_asr_provider.transcribe.assert_not_called()

    def test_skips_analysis_when_analysis_json_exists(
        self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider,
        sample_analysis, sample_transcript
    ):
        """analysis.json が存在する場合、analysis.extractor がスキップされること"""
        _write_analysis_json(tmp_path, sample_analysis)
        _patch_all(mocker, tmp_path, sample_analysis)
        extract_mock = mocker.patch("vmg.pipeline.extract")

        _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider)

        extract_mock.assert_not_called()

    def test_force_reruns_preprocess_even_when_audio_exists(
        self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis
    ):
        """force=True のとき audio.wav が存在しても extract_audio が呼ばれること"""
        _write_audio_wav(tmp_path)
        _patch_all(mocker, tmp_path, sample_analysis)
        extract_mock = mocker.patch(
            "vmg.pipeline.extract_audio",
            return_value=PreprocessResult(
                audio_path=str(tmp_path / _JOB_ID / "audio.wav"),
                job_id=_JOB_ID,
                duration_seconds=3600.0,
                sample_rate=16000,
            ),
        )

        _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider, force=True)

        extract_mock.assert_called_once()

    def test_force_reruns_asr_even_when_transcript_exists(
        self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider,
        sample_analysis, sample_transcript
    ):
        """force=True のとき transcript.json が存在しても asr_provider.transcribe が呼ばれること"""
        _write_transcript_json(tmp_path, sample_transcript)
        _patch_all(mocker, tmp_path, sample_analysis)

        _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider, force=True)

        mock_asr_provider.transcribe.assert_called_once()

    def test_force_reruns_analysis_even_when_analysis_exists(
        self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider,
        sample_analysis
    ):
        """force=True のとき analysis.json が存在しても analysis.extractor が呼ばれること"""
        _write_analysis_json(tmp_path, sample_analysis)
        _patch_all(mocker, tmp_path, sample_analysis)
        extract_mock = mocker.patch("vmg.pipeline.extract", return_value=_RAW_ANALYSIS)

        _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider, force=True)

        extract_mock.assert_called_once()

    def test_corrupted_transcript_json_triggers_rerun(
        self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis
    ):
        """transcript.json が破損している場合、asr_provider.transcribe が再実行されること"""
        _job_dir(tmp_path)
        (tmp_path / "work" / _JOB_ID / "transcript.json").write_text(
            "INVALID JSON!!!!", encoding="utf-8"
        )
        _patch_all(mocker, tmp_path, sample_analysis)

        _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider)

        mock_asr_provider.transcribe.assert_called_once()

    def test_corrupted_analysis_json_triggers_rerun(
        self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis
    ):
        """analysis.json が破損している場合、analysis.extractor が再実行されること"""
        _job_dir(tmp_path)
        (tmp_path / "work" / _JOB_ID / "analysis.json").write_text(
            "INVALID JSON!!!!", encoding="utf-8"
        )
        _patch_all(mocker, tmp_path, sample_analysis)
        extract_mock = mocker.patch("vmg.pipeline.extract", return_value=_RAW_ANALYSIS)

        _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider)

        extract_mock.assert_called_once()


class TestPipelineJobId:
    """job_id 指定による再実行性のテスト"""

    def _make_create_job_mock(self, mocker, tmp_path, job_id: str):
        """create_job を指定した job_id を返すモックに差し替える"""
        from vmg.ingest import JobMeta
        return mocker.patch(
            "vmg.pipeline.create_job",
            return_value=JobMeta(
                job_id=job_id,
                executed_at="2026-04-24T10:00:00+00:00",
                input_file_path=str(tmp_path / "meeting.mp4"),
            ),
        )

    def test_specified_job_id_passed_to_create_job(
        self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis
    ):
        """job_id を指定した場合、create_job に forced_job_id として渡されること"""
        _patch_all(mocker, tmp_path, sample_analysis)
        create_job_mock = self._make_create_job_mock(mocker, tmp_path, _JOB_ID)

        _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider, job_id="job_fixed_abc")

        create_job_mock.assert_called_once()
        assert create_job_mock.call_args.kwargs.get("forced_job_id") == "job_fixed_abc"

    def test_unspecified_job_id_passes_none_to_create_job(
        self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis
    ):
        """job_id を指定しない場合、create_job に forced_job_id=None が渡されること"""
        _patch_all(mocker, tmp_path, sample_analysis)
        create_job_mock = self._make_create_job_mock(mocker, tmp_path, _JOB_ID)

        _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider)

        create_job_mock.assert_called_once()
        assert create_job_mock.call_args.kwargs.get("forced_job_id") is None


class TestPipelineMaxRetries:

    def test_max_retries_passed_to_extract(
        self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis
    ):
        """run_pipeline に max_retries=5 を渡すと extract に max_retries=5 が渡ること"""
        _patch_all(mocker, tmp_path, sample_analysis)
        extract_mock = mocker.patch("vmg.pipeline.extract", return_value=_RAW_ANALYSIS)

        run_pipeline(
            input_path=tmp_path / "meeting.mp4",
            title="テスト会議",
            datetime_str="2026-04-23T10:00:00",
            participants=["田中"],
            asr_provider=mock_asr_provider,
            formatter_provider=mock_formatter_provider,
            work_dir=tmp_path / "work",
            output_dir=tmp_path / "output",
            log_dir=tmp_path / "logs",
            timeout_seconds=900,
            max_retries=5,
        )

        assert extract_mock.call_args.kwargs.get("max_retries") == 5

    def test_default_max_retries_is_three(
        self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis
    ):
        """max_retries 未指定時は extract に max_retries=3 が渡ること"""
        _patch_all(mocker, tmp_path, sample_analysis)
        extract_mock = mocker.patch("vmg.pipeline.extract", return_value=_RAW_ANALYSIS)

        _run_pipeline(tmp_path, mock_asr_provider, mock_formatter_provider)

        assert extract_mock.call_args.kwargs.get("max_retries") == 3

    def test_timeout_seconds_passed_to_extract(
        self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis
    ):
        """run_pipeline に timeout_seconds=300 を渡すと extract に timeout_seconds=300 が渡ること"""
        _patch_all(mocker, tmp_path, sample_analysis)
        extract_mock = mocker.patch("vmg.pipeline.extract", return_value=_RAW_ANALYSIS)

        run_pipeline(
            input_path=tmp_path / "meeting.mp4",
            title="テスト会議",
            datetime_str="2026-04-23T10:00:00",
            participants=["田中"],
            asr_provider=mock_asr_provider,
            formatter_provider=mock_formatter_provider,
            work_dir=tmp_path / "work",
            output_dir=tmp_path / "output",
            log_dir=tmp_path / "logs",
            timeout_seconds=300,
            max_retries=3,
        )

        assert extract_mock.call_args.kwargs.get("timeout_seconds") == 300


class TestPipelineCorrector:
    """pipeline 統合テスト: corrector が ASR 後・analysis 前に適用されること"""

    def test_corrector_applied_before_analysis(
        self, mocker, tmp_path, mock_formatter_provider, sample_analysis
    ):
        """#10: correction_enabled=True のとき補正済み transcript が build_prompt に渡される"""
        from unittest.mock import MagicMock
        mock_asr = MagicMock()
        mock_asr.transcribe.return_value = Transcript(
            language="ja",
            segments=[TranscriptSegment(start=0.0, end=5.0, text="使用書を確認する")],
            full_text="使用書を確認する",
        )
        _patch_all(mocker, tmp_path, sample_analysis)
        build_prompt_mock = mocker.patch(
            "vmg.pipeline.build_prompt",
            return_value=[PromptInput(prompt="会議テキスト", segment_start=0, segment_end=0)],
        )

        run_pipeline(
            input_path=tmp_path / "meeting.mp4",
            title="テスト会議",
            datetime_str="2026-04-23T10:00:00",
            participants=["田中"],
            asr_provider=mock_asr,
            formatter_provider=mock_formatter_provider,
            work_dir=tmp_path / "work",
            output_dir=tmp_path / "output",
            log_dir=tmp_path / "logs",
            timeout_seconds=900,
            correction_rules=[{"wrong": "使用書", "correct": "仕様書"}],
            correction_enabled=True,
        )

        called_transcript = build_prompt_mock.call_args.args[0]
        assert called_transcript.full_text == "仕様書を確認する"
        assert called_transcript.segments[0].text == "仕様書を確認する"

    def test_corrector_disabled_passes_original_transcript(
        self, mocker, tmp_path, mock_formatter_provider, sample_analysis
    ):
        """#11: correction_enabled=False のとき補正なしで pipeline が通る"""
        from unittest.mock import MagicMock
        mock_asr = MagicMock()
        mock_asr.transcribe.return_value = Transcript(
            language="ja",
            segments=[TranscriptSegment(start=0.0, end=5.0, text="使用書を確認する")],
            full_text="使用書を確認する",
        )
        _patch_all(mocker, tmp_path, sample_analysis)
        build_prompt_mock = mocker.patch(
            "vmg.pipeline.build_prompt",
            return_value=[PromptInput(prompt="会議テキスト", segment_start=0, segment_end=0)],
        )

        run_pipeline(
            input_path=tmp_path / "meeting.mp4",
            title="テスト会議",
            datetime_str="2026-04-23T10:00:00",
            participants=["田中"],
            asr_provider=mock_asr,
            formatter_provider=mock_formatter_provider,
            work_dir=tmp_path / "work",
            output_dir=tmp_path / "output",
            log_dir=tmp_path / "logs",
            timeout_seconds=900,
            correction_rules=[{"wrong": "使用書", "correct": "仕様書"}],
            correction_enabled=False,
        )

        called_transcript = build_prompt_mock.call_args.args[0]
        assert called_transcript.full_text == "使用書を確認する"


class TestAudioInput:
    """音声ファイル入力: input_path に wav/mp3/m4a を渡した場合の動作確認"""

    def test_wav_input_calls_validate_input_file(
        self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis
    ):
        """input_path に .wav を指定すると validate_input_file が呼ばれること"""
        _patch_all(mocker, tmp_path, sample_analysis)
        validate_mock = mocker.patch(
            "vmg.pipeline.validate_input_file",
            return_value=IngestResult(
                file_path=str(tmp_path / "recording.wav"),
                file_format="wav",
                file_size_bytes=512,
            ),
        )
        run_pipeline(
            input_path=tmp_path / "recording.wav",
            title="録音テスト",
            datetime_str="2026-05-01T10:00:00",
            participants=["田中"],
            asr_provider=mock_asr_provider,
            formatter_provider=mock_formatter_provider,
            work_dir=tmp_path / "work",
            output_dir=tmp_path / "output",
            log_dir=tmp_path / "logs",
            timeout_seconds=900,
        )
        validate_mock.assert_called_once()

    def test_mp3_input_calls_validate_input_file(
        self, mocker, tmp_path, mock_asr_provider, mock_formatter_provider, sample_analysis
    ):
        """input_path に .mp3 を指定すると validate_input_file が呼ばれること"""
        _patch_all(mocker, tmp_path, sample_analysis)
        validate_mock = mocker.patch(
            "vmg.pipeline.validate_input_file",
            return_value=IngestResult(
                file_path=str(tmp_path / "recording.mp3"),
                file_format="mp3",
                file_size_bytes=512,
            ),
        )
        run_pipeline(
            input_path=tmp_path / "recording.mp3",
            title="録音テスト",
            datetime_str="2026-05-01T10:00:00",
            participants=["田中"],
            asr_provider=mock_asr_provider,
            formatter_provider=mock_formatter_provider,
            work_dir=tmp_path / "work",
            output_dir=tmp_path / "output",
            log_dir=tmp_path / "logs",
            timeout_seconds=900,
        )
        validate_mock.assert_called_once()
