"""Experimental feature toggles, read from one env var rather than one per feature.

``LANGSMITH_EXPERIMENTAL_FEATURES`` is a comma-separated list of feature names,
in the style of ``GOEXPERIMENT``: a bare name turns a feature on and a ``no``
prefix turns it off, so a feature that later ships on by default can still be
switched back.

    LANGSMITH_EXPERIMENTAL_FEATURES=sandbox_sse_exec
    LANGSMITH_EXPERIMENTAL_FEATURES=nosandbox_sse_exec,some_other_feature

Names are matched case-insensitively, and ``-`` reads the same as ``_``. An
unrecognized name is ignored with a warning, so a stale setting cannot silently
mean something else after a feature is renamed or retired.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

ENV_VAR = "LANGSMITH_EXPERIMENTAL_FEATURES"

#: Run sandbox commands over the SSE exec endpoints instead of the WebSocket.
SANDBOX_SSE_EXEC = "sandbox_sse_exec"

_DEFAULTS: dict[str, bool] = {
    SANDBOX_SSE_EXEC: False,
}


def _normalize(name: str) -> str:
    return name.strip().lower().replace("-", "_")


def _settings() -> dict[str, bool]:
    settings = dict(_DEFAULTS)
    for token in os.environ.get(ENV_VAR, "").split(","):
        name = _normalize(token)
        if not name:
            continue
        on = True
        if name.startswith("no") and name not in settings:
            name, on = name[2:], False
        if name not in settings:
            logger.warning(
                "Ignoring unknown feature %r in %s; known features: %s",
                token.strip(),
                ENV_VAR,
                ", ".join(sorted(settings)),
            )
            continue
        settings[name] = on
    return settings


def enabled(name: str) -> bool:
    """Whether ``name`` is on, per ``LANGSMITH_FEATURES`` and its default."""
    return _settings()[_normalize(name)]


def setting_hint(name: str, *, on: bool = True) -> str:
    """Render the env var assignment that turns ``name`` on or off."""
    return f"{ENV_VAR}={'' if on else 'no'}{_normalize(name)}"
