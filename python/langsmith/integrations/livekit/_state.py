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
class _ConversationState:
    trace_id: int
    thread_id: Optional[str] = None
    root: Optional[TranslatedSpan] = None
    session_ended: bool = False
    transcript: list[tuple[Any, dict]] = field(default_factory=list)
    report_transcript: Optional[list[dict]] = None
    pending_audio: Optional[_PendingAudio] = None
    recording_started_at: Optional[float] = None
    audio_status: Optional[str] = None
    delivery_complete: bool = False
    delivery_in_progress: bool = False
    release_timer: Optional[threading.Timer] = None
    deferred_user_speaking: list[TranslatedSpan] = field(default_factory=list)
    pending_user_transcripts: list[str] = field(default_factory=list)
