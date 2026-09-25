"""LangSmith tracing for Deepgram's Voice Agent API."""

from langsmith.integrations.deepgram_voice._connection import (
    DEFAULT_SAMPLE_RATE,
    wrap_deepgram_voice,
)

__all__ = ["DEFAULT_SAMPLE_RATE", "wrap_deepgram_voice"]
