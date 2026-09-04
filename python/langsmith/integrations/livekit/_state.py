"""Mutable lifecycle state for the LiveKit span processor."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Optional

from langsmith._internal.voice.base_span_processor import TranslatedSpan


@dataclass
class _PendingAudio:
    name: str
    data: bytes
    mime_type: str


@dataclass
class _PendingThreadState:
    """Lifecycle data delivered before a thread is associated with a trace."""

    recording_mode: Optional[str] = None
    pending_audio: Optional[_PendingAudio] = None
    recording_started_at: Optional[float] = None
    audio_status: Optional[str] = None
    recording_received: bool = False


@dataclass
class _ConversationState:
    trace_id: int
    recording_mode: str = "session_report"
    thread_id: Optional[str] = None
    root: Optional[TranslatedSpan] = None
    session_ended: bool = False
    transcript: list[tuple[Any, dict]] = field(default_factory=list)
    report_transcript: Optional[list[dict]] = None
    pending_audio: Optional[_PendingAudio] = None
    recording_started_at: Optional[float] = None
    audio_status: Optional[str] = None
    report_received: bool = False
    recording_received: bool = False
    report_hook_session_id: Optional[int] = None
    release_timer: Optional[threading.Timer] = None
    spans_waiting_for_transcript: list[TranslatedSpan] = field(default_factory=list)
    transcripts_waiting_for_span: list[str] = field(default_factory=list)
