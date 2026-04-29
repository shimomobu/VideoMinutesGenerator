"""同音異義語誤変換補正 TranscriptCorrector の単体テスト"""
from __future__ import annotations

import pytest

from vmg.asr.corrector import TranscriptCorrector
from vmg.common.models import Transcript, TranscriptSegment


def _seg(text: str, start: float = 0.0, end: float = 5.0) -> TranscriptSegment:
    return TranscriptSegment(start=start, end=end, text=text)


def _transcript(full_text: str, *seg_texts: str) -> Transcript:
    texts = seg_texts if seg_texts else (full_text,)
    return Transcript(
        language="ja",
        segments=[_seg(t) for t in texts],
        full_text=full_text,
    )


# ── 基本補正 ──────────────────────────────────────────────────────

class TestTranscriptCorrectorBasic:

    def test_single_rule_replaces_match(self):
        """#1: 辞書に1件マッチする誤変換が正しく置換される"""
        corrector = TranscriptCorrector(rules=[{"wrong": "使用書", "correct": "仕様書"}])
        result = corrector.correct(_transcript("使用書を確認する"))
        assert result.full_text == "仕様書を確認する"
        assert result.segments[0].text == "仕様書を確認する"

    def test_multiple_rules_all_applied(self):
        """#2: 複数ルールが同一テキストに存在するとき、すべて適用される"""
        corrector = TranscriptCorrector(rules=[
            {"wrong": "使用書", "correct": "仕様書"},
            {"wrong": "バック修正", "correct": "バグ修正"},
        ])
        result = corrector.correct(_transcript("使用書のバック修正を行う"))
        assert result.full_text == "仕様書のバグ修正を行う"

    def test_no_match_leaves_text_unchanged(self):
        """#3: 辞書にない文字列は変更されない"""
        corrector = TranscriptCorrector(rules=[{"wrong": "使用書", "correct": "仕様書"}])
        original = "本日の会議を開始します"
        result = corrector.correct(_transcript(original))
        assert result.full_text == original

    def test_multiple_occurrences_all_replaced(self):
        """#4: 同一誤変換が複数箇所に出現する場合、全箇所置換される"""
        corrector = TranscriptCorrector(rules=[{"wrong": "使用書", "correct": "仕様書"}])
        result = corrector.correct(_transcript("使用書と使用書を比較する"))
        assert result.full_text == "仕様書と仕様書を比較する"

    def test_empty_rules_returns_original(self):
        """#5: ルールが0件の辞書のとき、入力をそのまま返す"""
        corrector = TranscriptCorrector(rules=[])
        original = _transcript("使用書の確認")
        result = corrector.correct(original)
        assert result.full_text == original.full_text

    def test_disabled_skips_correction(self):
        """#6: enabled=False のとき補正をスキップし入力をそのまま返す"""
        corrector = TranscriptCorrector(
            rules=[{"wrong": "使用書", "correct": "仕様書"}],
            enabled=False,
        )
        result = corrector.correct(_transcript("使用書を確認する"))
        assert result.full_text == "使用書を確認する"


# ── full_text / segments 両方に適用 ──────────────────────────────

class TestTranscriptCorrectorScope:

    def test_both_full_text_and_segments_corrected(self):
        """#7: full_text と segments[].text の両方が補正される"""
        corrector = TranscriptCorrector(rules=[{"wrong": "使用書", "correct": "仕様書"}])
        t = Transcript(
            language="ja",
            segments=[_seg("使用書を確認する")],
            full_text="使用書を確認する",
        )
        result = corrector.correct(t)
        assert result.full_text == "仕様書を確認する"
        assert result.segments[0].text == "仕様書を確認する"

    def test_all_segments_corrected(self):
        """#8: セグメントが複数ある場合、全セグメントに適用される"""
        corrector = TranscriptCorrector(rules=[{"wrong": "使用書", "correct": "仕様書"}])
        t = _transcript(
            "使用書を確認する。使用書を更新する。",
            "使用書を確認する。",
            "使用書を更新する。",
        )
        result = corrector.correct(t)
        assert result.segments[0].text == "仕様書を確認する。"
        assert result.segments[1].text == "仕様書を更新する。"

    def test_no_false_positive_on_substring(self):
        """#9: 誤変換語が正しい語の部分文字列になるケース — 誤検知しない

        「使用書」→「仕様書」に直すが、「使用する」「使用方法」は置換しない。
        """
        corrector = TranscriptCorrector(rules=[{"wrong": "使用書", "correct": "仕様書"}])
        text = "使用書の使用方法を使用する場合の注意"
        result = corrector.correct(_transcript(text))
        assert result.full_text == "仕様書の使用方法を使用する場合の注意"


# ── フィールド保持 ────────────────────────────────────────────────

class TestTranscriptCorrectorFieldPreservation:

    def test_speaker_field_preserved(self):
        """speaker フィールドが補正後も保持される"""
        corrector = TranscriptCorrector(rules=[{"wrong": "使用書", "correct": "仕様書"}])
        t = Transcript(
            language="ja",
            segments=[TranscriptSegment(start=0.0, end=5.0, text="使用書を確認", speaker="田中")],
            full_text="使用書を確認",
        )
        result = corrector.correct(t)
        assert result.segments[0].speaker == "田中"
        assert result.segments[0].text == "仕様書を確認"

    def test_language_field_preserved(self):
        """language フィールドが補正後も保持される"""
        corrector = TranscriptCorrector(rules=[{"wrong": "使用書", "correct": "仕様書"}])
        result = corrector.correct(_transcript("使用書"))
        assert result.language == "ja"
