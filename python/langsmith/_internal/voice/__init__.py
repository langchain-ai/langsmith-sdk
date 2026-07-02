"""Private shared machinery for the voice tracing integrations.

Two independent bases live here, sharing only this namespace (not a common
class):

* ``base_span_processor`` — Track A: :class:`BaseLangSmithSpanProcessor`, an
  OpenTelemetry ``SpanProcessor`` shared by the framework integrations that emit
  their own OTel spans (Pipecat, LiveKit).
* ``session`` — Track B: :class:`EventSession`, a LangSmith ``RunTree`` builder
  shared by the integrations that observe a remote event stream and construct
  the trace themselves (OpenAI Realtime, OpenAI Agents realtime, ADK Live).

Nothing in this package is part of the public API; import from the per-framework
packages instead.
"""

from __future__ import annotations

import contextvars
from typing import Optional

# Per-conversation LangSmith thread id, read by the voice integrations via
# ``thread_id_from_context``. A ``ContextVar`` — not a module global or a
# closure — so that concurrent conversations running as separate asyncio tasks
# each see their own value rather than clobbering a single shared one.
_VOICE_THREAD_ID: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "langsmith_voice_thread_id", default=None
)


def set_thread_id(thread_id: Optional[str]) -> None:
    """Set the LangSmith thread id for the current (async) context.

    Call this once per conversation, inside that conversation's asyncio task, to
    group its spans into a LangSmith thread. The voice processors capture it as
    the conversation's spans start and apply it across the whole trace, so no
    wiring is needed beyond this call — and it holds even for spans finished on a
    background task. Because it is stored in a :class:`~contextvars.ContextVar`,
    concurrent conversations each see their own value; a shared closure would not.
    """
    _VOICE_THREAD_ID.set(thread_id)


def thread_id_from_context() -> Optional[str]:
    """Return the thread id set by :func:`set_thread_id` for this context."""
    return _VOICE_THREAD_ID.get()
