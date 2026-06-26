"""Private shared machinery for the voice tracing integrations.

Two independent bases live here, sharing only this namespace (not a common
class):

* ``base`` — Track A: :class:`BaseLangSmithSpanProcessor`, an OpenTelemetry
  ``SpanProcessor`` shared by the framework integrations that emit their own
  OTel spans (Pipecat, LiveKit).
* ``session`` — Track B: :class:`EventSession`, a LangSmith ``RunTree`` builder
  shared by the integrations that observe a remote event stream and construct
  the trace themselves (OpenAI Realtime, OpenAI Agents realtime, ADK Live).

Nothing in this package is part of the public API; import from the per-framework
packages instead.
"""

from __future__ import annotations

import warnings


class LangSmithVoiceBetaWarning(UserWarning):
    """Warns that a LangSmith voice tracing integration is in development.

    Filter it with ``warnings.filterwarnings("ignore",
    category=LangSmithVoiceBetaWarning)``.
    """


def warn_in_development(integration: str) -> None:
    """Emit a :class:`LangSmithVoiceBetaWarning` for a voice integration.

    Called when one of the voice integration packages is imported, to signal
    that these integrations are in development and their APIs may change.
    """
    warnings.warn(
        f"langsmith.integrations.{integration} is in development; its API may "
        "change in a future release.",
        category=LangSmithVoiceBetaWarning,
        stacklevel=3,
    )

