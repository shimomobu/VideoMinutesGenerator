"""CLI エントリポイント — video-minutes / python -m vmg"""
from __future__ import annotations

import click

from vmg.asr import WhisperLocalProvider
from vmg.common.config import load_config
from vmg.formatter import StandardFormatter
from vmg.pipeline import PipelineError, run_pipeline


@click.command()
@click.option("--input", "input_path", required=True, type=click.Path(), help="入力動画ファイルパス（mp4/mov/mkv）")
@click.option("--title", required=True, help="会議タイトル")
@click.option("--datetime", "datetime_str", required=True, help="会議日時（ISO8601形式、例: 2026-04-23T10:00:00）")
@click.option("--participants", multiple=True, help="参加者名（複数指定可、例: --participants 田中 --participants 佐藤）")
@click.option("--job-id", "job_id", default=None, help="ジョブID（省略時は自動生成）")
@click.option("--force", is_flag=True, default=False, help="中間ファイルを無視して全ステージを強制再実行")
def main(
    input_path: str,
    title: str,
    datetime_str: str,
    participants: tuple,
    job_id: str | None,
    force: bool,
) -> None:
    """会議動画から議事録を自動生成します。"""
    if not participants:
        raise click.UsageError("--participants は必須です。少なくとも1名指定してください。")

    try:
        config = load_config()
    except Exception as e:
        raise click.ClickException(f"設定読み込みエラー: {e}") from e

    asr_provider = WhisperLocalProvider(model_name=config.whisper_model)
    formatter_provider = StandardFormatter()

    try:
        result = run_pipeline(
            video_path=input_path,
            title=title,
            datetime_str=datetime_str,
            participants=list(participants),
            asr_provider=asr_provider,
            formatter_provider=formatter_provider,
            model=config.llm_model,
            base_url=config.ollama_base_url,
            force=force,
            job_id=job_id,
            timeout_seconds=config.llm_timeout_seconds,
            max_retries=config.llm_max_retries,
        )
    except PipelineError as e:
        raise click.ClickException(f"パイプラインエラー [{e.stage}]: {e.cause}") from e

    click.echo(f"完了: {result.job_id}")
    click.echo(f"  Markdown : {result.markdown_path}")
    click.echo(f"  JSON     : {result.json_path}")
    click.echo(f"  Manifest : {result.manifest_path}")
