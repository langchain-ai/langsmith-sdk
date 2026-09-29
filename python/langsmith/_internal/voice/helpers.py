"""Shared helpers for the voice integration adapters.

* ``dump_event`` — best-effort conversion of an event object to a plain dict
  (Pydantic ``model_dump`` → ``dict`` → ``repr`` fallback).
* ``scrub`` — replace raw audio ``bytes`` with a ``<N bytes>`` placeholder and
  truncate long strings, recursing through dicts and sequences, so a span never
  carries megabytes of audio or un-serializable junk.
* ``observe_safely`` — run an adapter's per-event ``observe`` so a tracing error
  never escapes into the caller's live loop.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

__all__ = ["dump_event", "scrub", "observe_safely"]

# Longest string kept on a span before truncating. Transcripts are short; this
# only ever trims an unexpectedly large blob.
MAX_STR = 2000


def observe_safely(observe: Callable[[Any], None], event: Any) -> None:
    """Run an adapter's ``observe`` over one event, swallowing any error.

    Tracing must never break the live voice loop, so a failure building the
    trace is logged and dropped and the caller still gets its event.
    """
    try:
        observe(event)
    except Exception:
        logger.warning(
            "voice tracing: failed to observe an event; skipping it", exc_info=True
        )


def scrub(obj: Any) -> Any:
    """Make an event payload safe and compact for a span.

    Replaces raw ``bytes`` (audio / base64 blobs) with a ``<N bytes>``
    placeholder and truncates very long strings, recursing through dicts and
    sequences, so a span never ships megabytes of payload or breaks JSON
    serialization.
    """
    if isinstance(obj, bytes):
        return f"<{len(obj)} bytes>"
    if isinstance(obj, str):
        if len(obj) > MAX_STR:
            return obj[:MAX_STR] + f"... <+{len(obj) - MAX_STR} chars>"
        return obj
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [scrub(v) for v in obj]
    return obj


def dump_event(event: Any) -> dict[str, Any]:
    """Best-effort conversion of an event object to a plain dict."""
    if hasattr(event, "model_dump"):
        try:
            return event.model_dump()
        except Exception:
            pass
    if isinstance(event, dict):
        return event
    return {"repr": repr(event)}
