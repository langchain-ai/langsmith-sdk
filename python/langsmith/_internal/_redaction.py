"""Mask credentials in provider request params on the way into a trace.

Helpers return new containers: the caller's objects also go to the provider API
and must keep their real values.
"""

from __future__ import annotations

import logging
from collections.abc import Collection, Mapping
from typing import Any, Optional

from langsmith.anonymizer import SECRET_PLACEHOLDER

__all__ = ["as_mapping", "mask", "redact_outside"]

logger = logging.getLogger(__name__)


def as_mapping(value: Any) -> Optional[Mapping]:
    """Return ``value`` as a mapping; Pydantic configs need a dump to see into."""
    if isinstance(value, Mapping):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            dumped = dump()
        except Exception as e:
            logger.warning(
                "Could not read %s to redact it: %s", type(value).__name__, e
            )
            return None
        return dumped if isinstance(dumped, Mapping) else None
    return None


def mask(value: Any) -> Any:
    """Mask ``value``, keeping key names so a trace shows what was set."""
    mapping = as_mapping(value)
    if mapping is not None:
        return {key: SECRET_PLACEHOLDER for key in mapping}
    return SECRET_PLACEHOLDER


def redact_outside(entry: Any, safe_keys: Collection[str]) -> Any:
    """Copy ``entry``, masking values outside ``safe_keys``; unknown keys fail shut."""
    mapping = as_mapping(entry)
    if mapping is None:
        return entry
    return {
        key: value if key in safe_keys else SECRET_PLACEHOLDER
        for key, value in mapping.items()
    }
