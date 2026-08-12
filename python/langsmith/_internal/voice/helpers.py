"""Shared helpers for the voice integration adapters.

* ``dump_event`` — best-effort conversion of an event object to a plain dict
  (Pydantic ``model_dump`` → ``dict`` → ``repr`` fallback).
* ``scrub`` — recurse through dicts and sequences replacing raw audio ``bytes``
  with a ``<N bytes>`` placeholder, masking credential keys and truncating long
  strings, so a span carries no audio, live credential, or un-serializable junk.
* ``observe_safely`` — run an adapter's per-event ``observe`` so a tracing error
  never escapes into the caller's live loop.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from langsmith._internal._redaction import mask

logger = logging.getLogger(__name__)

__all__ = ["dump_event", "scrub", "observe_safely"]

# Longest string kept on a span before truncating. Transcripts are short; this
# only ever trims an unexpectedly large blob.
MAX_STR = 2000

# Credential keys wherever they appear in a provider event. Adapters pass
# arbitrary payloads, so this is a denylist; exact match keeps `max_tokens` safe.
SECRET_KEYS: frozenset[str] = frozenset(
    {
        "authorization",
        "api_key",
        "apiKey",
        "headers",
        "env",
        "access_token",
        "accessToken",
        "refresh_token",
        "refreshToken",
        "client_secret",
        "clientSecret",
        "password",
        "secret",
    }
)


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

    Replaces raw ``bytes`` with a ``<N bytes>`` placeholder, masks values under
    :data:`SECRET_KEYS`, and truncates long strings.
    """
    if isinstance(obj, bytes):
        return f"<{len(obj)} bytes>"
    if isinstance(obj, str):
        if len(obj) > MAX_STR:
            return obj[:MAX_STR] + f"... <+{len(obj) - MAX_STR} chars>"
        return obj
    if isinstance(obj, dict):
        return {k: mask(v) if k in SECRET_KEYS else scrub(v) for k, v in obj.items()}
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
