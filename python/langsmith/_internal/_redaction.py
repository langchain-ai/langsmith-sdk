"""Mask credentials in provider request params on the way into a trace.

Helpers return new containers: the caller's objects also go to the provider API
and must keep their real values.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any, Optional

from langsmith.anonymizer import SECRET_PLACEHOLDER

__all__ = ["mask", "redact_outside", "redact_keys"]

# Guard against cyclic payloads; request params are shallow.
_MAX_DEPTH = 12


def _as_mapping(value: Any) -> Optional[Mapping]:
    """Return ``value`` as a mapping; Pydantic configs need a dump to see into."""
    if isinstance(value, Mapping):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            dumped = dump()
        except Exception:
            return None
        return dumped if isinstance(dumped, Mapping) else None
    return None


def mask(value: Any) -> Any:
    """Mask ``value``, keeping key names so a trace shows what was set."""
    mapping = _as_mapping(value)
    if mapping is not None:
        return {key: SECRET_PLACEHOLDER for key in mapping}
    return SECRET_PLACEHOLDER


def redact_outside(entry: Any, safe_keys: Collection[str]) -> Any:
    """Copy ``entry``, masking values outside ``safe_keys``; unknown keys fail shut."""
    mapping = _as_mapping(entry)
    if mapping is None:
        return entry
    return {
        key: value if key in safe_keys else SECRET_PLACEHOLDER
        for key, value in mapping.items()
    }


def redact_keys(value: Any, secret_keys: Collection[str], _depth: int = 0) -> Any:
    """Recursively mask values under ``secret_keys``.

    Scope to config-shaped data, never user content, where these key names are
    legitimate.
    """
    if _depth > _MAX_DEPTH:
        return SECRET_PLACEHOLDER
    mapping = _as_mapping(value)
    if mapping is not None:
        return {
            key: mask(item)
            if key in secret_keys
            else redact_keys(item, secret_keys, _depth + 1)
            for key, item in mapping.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_keys(item, secret_keys, _depth + 1) for item in value]
    return value
