"""共通型定義 — パイプライン全体で使用するPydanticモデル"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class MeetingInfo(BaseModel):
    title: str
    datetime: str
    participants: list[str]
    source_file: str
    duration_seconds: int


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str
    speaker: Optional[str] = None


class Transcript(BaseModel):
    language: str
    segments: list[TranscriptSegment]
    full_text: str


class Topic(BaseModel):
    title: str
    summary: str
    key_points: list[str]


class Todo(BaseModel):
    task: str
    owner_candidate: Optional[str] = None
    due_date_candidate: Optional[str] = None
    notes: Optional[str] = None


class AnalysisResult(BaseModel):
    summary: str
    agenda: list[str]
    topics: list[Topic]
    decisions: list[str]
    pending_items: list[str]
    todos: list[Todo]


class OutputManifest(BaseModel):
    job_id: str
    generated_at: str
    files: list[str]
    source_transcript: str


class MinutesOutput(BaseModel):
    meeting_info: MeetingInfo
    analysis: AnalysisResult
    transcript: Transcript
    manifest: OutputManifest
