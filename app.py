"""デモ用 Streamlit UI — 動画をアップロードして議事録を生成する"""
from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from vmg.asr import WhisperLocalProvider
from vmg.common.config import load_config
from vmg.formatter import StandardFormatter
from vmg.pipeline import PipelineError, run_pipeline

st.set_page_config(page_title="Video Minutes Generator", layout="centered")
st.title("Video Minutes Generator")
st.caption("会議動画をアップロードして議事録を自動生成します。処理には数分かかります。")

# ── 入力フォーム ──────────────────────────────────────────────────

uploaded_file = st.file_uploader(
    "動画・音声ファイルをアップロード",
    type=["mp4", "mov", "mkv", "wav", "mp3", "m4a"],
    help="対応形式: mp4 / mov / mkv / wav / mp3 / m4a",
)

title = st.text_input("会議タイトル", placeholder="週次定例会議")
datetime_str = st.text_input(
    "日時（ISO 8601 形式）",
    placeholder="2026-04-29T10:00:00",
    help="例: 2026-04-29T10:00:00",
)
participants_str = st.text_input(
    "参加者（カンマ区切り）",
    placeholder="田中, 佐藤",
)

run_btn = st.button("議事録を生成する", type="primary", disabled=not uploaded_file)

# ── 実行 ─────────────────────────────────────────────────────────

if run_btn:
    if not title:
        st.error("会議タイトルを入力してください。")
        st.stop()
    if not datetime_str:
        st.error("日時を入力してください（例: 2026-04-29T10:00:00）。")
        st.stop()

    participants = [p.strip() for p in participants_str.split(",") if p.strip()]

    suffix = Path(uploaded_file.name).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = Path(tmp.name)

    try:
        config = load_config()
        asr_provider = WhisperLocalProvider(
            model_name=config.whisper_model,
            initial_prompt=config.whisper_initial_prompt,
        )
        formatter_provider = StandardFormatter()

        with st.spinner("処理中… ASR と LLM の分析に数分かかります"):
            result = run_pipeline(
                input_path=tmp_path,
                title=title,
                datetime_str=datetime_str,
                participants=participants,
                asr_provider=asr_provider,
                formatter_provider=formatter_provider,
                model=config.llm_model,
                base_url=config.ollama_base_url,
                timeout_seconds=config.llm_timeout_seconds,
                max_retries=config.llm_max_retries,
                correction_rules=config.correction_rules,
                correction_enabled=config.correction_enabled,
            )
    except PipelineError as e:
        st.error(f"エラー [{e.stage}]: {e.cause}")
        st.stop()
    finally:
        tmp_path.unlink(missing_ok=True)

    st.success(f"完了: {result.job_id}")

    st.subheader("出力ファイル")
    st.code(result.json_path, language=None)

    st.subheader("議事録（minutes.md）")
    md_text = Path(result.markdown_path).read_text(encoding="utf-8")
    st.markdown(md_text)
