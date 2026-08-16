"""LangSmith integration for the Gemini Live API.

Use :func:`wrap_gemini_live` with the ``AsyncSession`` yielded by
``google.genai.Client().aio.live.connect(...)``. The wrapper observes the
session's WebSocket event stream without changing the application's receive,
audio, or tool-handling loop.

The implementation intentionally imports no ``google-genai`` types at runtime,
so importing this module does not require the optional provider dependency.
"""

from __future__ import annotations

from langsmith._internal._beta_decorator import warn_beta
from langsmith.integrations.gemini_live._session import wrap_gemini_live

wrap_gemini_live = warn_beta(wrap_gemini_live)

__all__ = ["wrap_gemini_live"]
