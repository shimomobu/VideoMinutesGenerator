"""TASK-07-03: CLI エントリポイントの単体テスト"""
from __future__ import annotations

import pytest
from click.testing import CliRunner

from vmg.cli import main
from vmg.pipeline import PipelineResult


_FULL_ARGS = [
    "--input", "meeting.mp4",
    "--title", "週次定例",
    "--datetime", "2026-04-23T10:00:00",
    "--participants", "田中",
    "--participants", "佐藤",
]


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def mock_config(mocker):
    from unittest.mock import MagicMock
    cfg = MagicMock()
    cfg.whisper_model = "base"
    cfg.llm_model = "gemma4"
    cfg.ollama_base_url = "http://localhost:11434/v1"
    return mocker.patch("vmg.cli.load_config", return_value=cfg)


@pytest.fixture()
def mock_pipeline(mocker):
    return mocker.patch(
        "vmg.cli.run_pipeline",
        return_value=PipelineResult(
            job_id="job_test_001",
            markdown_path="data/output/job_test_001/minutes.md",
            json_path="data/output/job_test_001/minutes.json",
            manifest_path="data/output/job_test_001/manifest.json",
        ),
    )


@pytest.fixture()
def mock_providers(mocker):
    mocker.patch("vmg.cli.WhisperLocalProvider")
    mocker.patch("vmg.cli.StandardFormatter")


class TestCliHelp:

    def test_help_exit_zero(self, runner):
        """--help はエラーなく終了すること"""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0

    def test_help_contains_input_option(self, runner):
        """--help に --input オプションが含まれること"""
        result = runner.invoke(main, ["--help"])
        assert "--input" in result.output

    def test_help_contains_title_option(self, runner):
        """--help に --title オプションが含まれること"""
        result = runner.invoke(main, ["--help"])
        assert "--title" in result.output

    def test_help_contains_datetime_option(self, runner):
        """--help に --datetime オプションが含まれること"""
        result = runner.invoke(main, ["--help"])
        assert "--datetime" in result.output

    def test_help_contains_participants_option(self, runner):
        """--help に --participants オプションが含まれること"""
        result = runner.invoke(main, ["--help"])
        assert "--participants" in result.output

    def test_help_contains_force_option(self, runner):
        """--help に --force オプションが含まれること"""
        result = runner.invoke(main, ["--help"])
        assert "--force" in result.output


class TestCliMissingArgs:

    def test_missing_all_args_nonzero_exit(self, runner):
        """全引数なしはエラー終了すること"""
        result = runner.invoke(main, [])
        assert result.exit_code != 0

    def test_missing_input_nonzero_exit(self, runner):
        """--input 欠落時はエラー終了すること"""
        result = runner.invoke(main, [
            "--title", "週次定例",
            "--datetime", "2026-04-23T10:00:00",
            "--participants", "田中",
        ])
        assert result.exit_code != 0

    def test_missing_title_nonzero_exit(self, runner):
        """--title 欠落時はエラー終了すること"""
        result = runner.invoke(main, [
            "--input", "meeting.mp4",
            "--datetime", "2026-04-23T10:00:00",
            "--participants", "田中",
        ])
        assert result.exit_code != 0

    def test_missing_datetime_nonzero_exit(self, runner):
        """--datetime 欠落時はエラー終了すること"""
        result = runner.invoke(main, [
            "--input", "meeting.mp4",
            "--title", "週次定例",
            "--participants", "田中",
        ])
        assert result.exit_code != 0

    def test_missing_participants_nonzero_exit(self, runner):
        """--participants 欠落時はエラー終了すること"""
        result = runner.invoke(main, [
            "--input", "meeting.mp4",
            "--title", "週次定例",
            "--datetime", "2026-04-23T10:00:00",
        ])
        assert result.exit_code != 0


class TestCliNormalRun:

    def test_normal_run_exit_zero(self, runner, mock_config, mock_pipeline, mock_providers):
        """全引数指定時はエラーなく終了すること"""
        result = runner.invoke(main, _FULL_ARGS)
        assert result.exit_code == 0

    def test_normal_run_calls_pipeline_once(self, runner, mock_config, mock_pipeline, mock_providers):
        """run_pipeline が1回呼ばれること"""
        runner.invoke(main, _FULL_ARGS)
        mock_pipeline.assert_called_once()

    def test_normal_run_shows_job_id(self, runner, mock_config, mock_pipeline, mock_providers):
        """完了後に job_id が出力されること"""
        result = runner.invoke(main, _FULL_ARGS)
        assert "job_test_001" in result.output

    def test_force_flag_passed_to_pipeline(self, runner, mock_config, mock_pipeline, mock_providers):
        """--force を渡すと run_pipeline に force=True が渡ること"""
        runner.invoke(main, _FULL_ARGS + ["--force"])
        assert mock_pipeline.call_args.kwargs["force"] is True

    def test_no_force_flag_defaults_false(self, runner, mock_config, mock_pipeline, mock_providers):
        """--force なしは run_pipeline に force=False が渡ること"""
        runner.invoke(main, _FULL_ARGS)
        assert mock_pipeline.call_args.kwargs["force"] is False

    def test_timeout_seconds_passed_to_pipeline(self, runner, mock_config, mock_pipeline, mock_providers):
        """config の llm_timeout_seconds が run_pipeline に timeout_seconds として渡ること"""
        mock_config.return_value.llm_timeout_seconds = 300
        runner.invoke(main, _FULL_ARGS)
        assert mock_pipeline.call_args.kwargs["timeout_seconds"] == 300

    def test_participants_passed_as_list(self, runner, mock_config, mock_pipeline, mock_providers):
        """--participants は list[str] として run_pipeline に渡ること"""
        runner.invoke(main, _FULL_ARGS)
        participants = mock_pipeline.call_args.kwargs["participants"]
        assert isinstance(participants, list)
        assert "田中" in participants
        assert "佐藤" in participants


class TestCliJobId:

    def test_job_id_passed_to_pipeline_when_specified(self, runner, mock_config, mock_pipeline, mock_providers):
        """--job-id を指定すると run_pipeline に job_id が渡ること"""
        runner.invoke(main, _FULL_ARGS + ["--job-id", "job_fixed_001"])
        assert mock_pipeline.call_args.kwargs["job_id"] == "job_fixed_001"

    def test_job_id_is_none_when_not_specified(self, runner, mock_config, mock_pipeline, mock_providers):
        """--job-id を指定しない場合、run_pipeline に job_id=None が渡ること"""
        runner.invoke(main, _FULL_ARGS)
        assert mock_pipeline.call_args.kwargs["job_id"] is None
