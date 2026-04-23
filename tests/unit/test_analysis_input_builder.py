"""TASK-04-01: vmg.analysis.input_builder 単体テスト"""
import re

import pytest

from vmg.analysis.input_builder import PromptInput, build_prompt
from vmg.common.models import Transcript, TranscriptSegment


# ── フィクスチャ ──────────────────────────────────────────────────

@pytest.fixture
def short_transcript():
    return Transcript(
        language="ja",
        segments=[
            TranscriptSegment(start=0.0, end=5.0, text="こんにちは", speaker=None),
            TranscriptSegment(start=5.0, end=10.0, text="ありがとう", speaker=None),
        ],
        full_text="こんにちはありがとう",
    )


@pytest.fixture
def long_transcript():
    """max_chars=50 でチャンク分割が発生する transcript（セグメント10件）"""
    segments = [
        TranscriptSegment(
            start=float(i * 5),
            end=float((i + 1) * 5),
            text=f"テキスト{i:02d}",
            speaker=None,
        )
        for i in range(10)
    ]
    return Transcript(language="ja", segments=segments, full_text="")


@pytest.fixture
def empty_transcript():
    return Transcript(language="ja", segments=[], full_text="")


@pytest.fixture
def speaker_transcript():
    return Transcript(
        language="ja",
        segments=[
            TranscriptSegment(start=0.0, end=5.0, text="こんにちは", speaker="Speaker_A"),
            TranscriptSegment(start=5.0, end=10.0, text="ありがとう", speaker=None),
        ],
        full_text="",
    )


# ── PromptInput モデル ────────────────────────────────────────────

class TestPromptInputModel:
    def test_has_prompt_field(self):
        pi = PromptInput(prompt="hello", segment_start=0, segment_end=1)
        assert pi.prompt == "hello"

    def test_has_segment_start_field(self):
        pi = PromptInput(prompt="", segment_start=2, segment_end=5)
        assert pi.segment_start == 2

    def test_has_segment_end_field(self):
        pi = PromptInput(prompt="", segment_start=0, segment_end=5)
        assert pi.segment_end == 5

    def test_prompt_is_str(self):
        pi = PromptInput(prompt="test", segment_start=0, segment_end=0)
        assert isinstance(pi.prompt, str)

    def test_segment_start_is_int(self):
        pi = PromptInput(prompt="", segment_start=3, segment_end=5)
        assert isinstance(pi.segment_start, int)

    def test_segment_end_is_int(self):
        pi = PromptInput(prompt="", segment_start=0, segment_end=7)
        assert isinstance(pi.segment_end, int)


# ── 正常系: 空 transcript ─────────────────────────────────────────

class TestBuildPromptEmpty:
    def test_empty_transcript_returns_list(self, empty_transcript):
        result = build_prompt(empty_transcript)
        assert isinstance(result, list)

    def test_empty_transcript_does_not_crash(self, empty_transcript):
        build_prompt(empty_transcript)

    def test_empty_transcript_returns_empty_list(self, empty_transcript):
        result = build_prompt(empty_transcript)
        assert result == []


# ── 正常系: 短い transcript（分割なし） ───────────────────────────

class TestBuildPromptShort:
    def test_returns_list(self, short_transcript):
        result = build_prompt(short_transcript)
        assert isinstance(result, list)

    def test_single_chunk_for_short_transcript(self, short_transcript):
        result = build_prompt(short_transcript)
        assert len(result) == 1

    def test_chunk_is_prompt_input(self, short_transcript):
        result = build_prompt(short_transcript)
        assert isinstance(result[0], PromptInput)

    def test_prompt_contains_first_segment_text(self, short_transcript):
        result = build_prompt(short_transcript)
        assert "こんにちは" in result[0].prompt

    def test_prompt_contains_second_segment_text(self, short_transcript):
        result = build_prompt(short_transcript)
        assert "ありがとう" in result[0].prompt

    def test_segment_start_is_zero(self, short_transcript):
        result = build_prompt(short_transcript)
        assert result[0].segment_start == 0

    def test_segment_end_is_last_index(self, short_transcript):
        result = build_prompt(short_transcript)
        assert result[0].segment_end == len(short_transcript.segments) - 1

    def test_single_segment_transcript(self):
        t = Transcript(
            language="ja",
            segments=[TranscriptSegment(start=0.0, end=5.0, text="ひとつだけ", speaker=None)],
            full_text="",
        )
        result = build_prompt(t)
        assert len(result) == 1
        assert result[0].segment_start == 0
        assert result[0].segment_end == 0


# ── 正常系: 長い transcript（チャンク分割） ───────────────────────

class TestBuildPromptLong:
    def test_produces_multiple_chunks(self, long_transcript):
        result = build_prompt(long_transcript, max_chars=50)
        assert len(result) > 1

    def test_first_chunk_starts_at_zero(self, long_transcript):
        result = build_prompt(long_transcript, max_chars=50)
        assert result[0].segment_start == 0

    def test_last_chunk_ends_at_last_segment(self, long_transcript):
        result = build_prompt(long_transcript, max_chars=50)
        assert result[-1].segment_end == len(long_transcript.segments) - 1

    def test_chunks_are_sequential(self, long_transcript):
        result = build_prompt(long_transcript, max_chars=50)
        for i in range(len(result) - 1):
            assert result[i].segment_end + 1 == result[i + 1].segment_start

    def test_all_segments_covered(self, long_transcript):
        result = build_prompt(long_transcript, max_chars=50)
        covered = set()
        for chunk in result:
            for i in range(chunk.segment_start, chunk.segment_end + 1):
                covered.add(i)
        assert covered == set(range(len(long_transcript.segments)))

    def test_each_chunk_prompt_is_not_empty(self, long_transcript):
        result = build_prompt(long_transcript, max_chars=50)
        for chunk in result:
            assert chunk.prompt.strip() != ""


# ── 正常系: プロンプトの整形 ─────────────────────────────────────

class TestPromptFormat:
    def test_timestamp_present_in_prompt(self, short_transcript):
        result = build_prompt(short_transcript)
        assert "[00:00:00]" in result[0].prompt

    def test_timestamp_format_hhmmss(self, short_transcript):
        result = build_prompt(short_transcript)
        assert re.search(r'\[\d{2}:\d{2}:\d{2}\]', result[0].prompt)

    def test_large_timestamp_formatted(self):
        t = Transcript(
            language="ja",
            segments=[TranscriptSegment(start=3661.0, end=3665.0, text="test", speaker=None)],
            full_text="",
        )
        result = build_prompt(t)
        assert "[01:01:01]" in result[0].prompt

    def test_speaker_included_when_not_none(self, speaker_transcript):
        result = build_prompt(speaker_transcript)
        assert "Speaker_A" in result[0].prompt

    def test_speaker_colon_format(self, speaker_transcript):
        result = build_prompt(speaker_transcript)
        assert "Speaker_A:" in result[0].prompt

    def test_speaker_omitted_when_none(self, short_transcript):
        result = build_prompt(short_transcript)
        assert "Speaker" not in result[0].prompt

    def test_second_segment_has_timestamp(self, short_transcript):
        result = build_prompt(short_transcript)
        assert "[00:00:05]" in result[0].prompt

    def test_segments_separated_by_newline(self, short_transcript):
        result = build_prompt(short_transcript)
        assert "\n" in result[0].prompt
