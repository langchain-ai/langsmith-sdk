"""LangSmith tracing for Deepgram's Voice Agent API.

Install with ``pip install langsmith[deepgram-voice]``.
"""

from langsmith._internal._beta_decorator import warn_beta
from langsmith.integrations.deepgram_voice._connection import (
    DEFAULT_SAMPLE_RATE,
    wrap_deepgram_voice,
)

wrap_deepgram_voice = warn_beta(wrap_deepgram_voice)

__all__ = ["DEFAULT_SAMPLE_RATE", "wrap_deepgram_voice"]
