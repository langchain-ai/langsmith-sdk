"""LangSmith integration for the OpenAI Realtime API.

There are two ways to build an OpenAI Realtime voice agent, each with its own
wrapper here:

* :func:`wrap_realtime` — for a raw ``client.realtime.connect()`` WebSocket loop.
* :func:`wrap_realtime_session` — for an ``agents.realtime`` session built with
  the OpenAI Agents SDK.

Both build a single LangSmith trace from the provider's event stream and return
a transparent proxy, so the caller's loop is unchanged.
"""

from __future__ import annotations

from .._voice import warn_in_development
from ._connection import wrap_realtime
from ._session import wrap_realtime_session

warn_in_development("openai_realtime")

__all__ = ["wrap_realtime", "wrap_realtime_session"]
