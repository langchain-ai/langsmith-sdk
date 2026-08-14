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

from langsmith._internal._beta_decorator import warn_beta
from langsmith.integrations.openai_realtime._connection import wrap_realtime
from langsmith.integrations.openai_realtime._session import wrap_realtime_session

# In beta: warn once on first use (matches the SDK's warn_beta convention).
wrap_realtime = warn_beta(wrap_realtime)
wrap_realtime_session = warn_beta(wrap_realtime_session)

__all__ = ["wrap_realtime", "wrap_realtime_session"]
