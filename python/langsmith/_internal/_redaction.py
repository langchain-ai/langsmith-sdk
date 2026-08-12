"""Mask credentials in provider request params on the way into a trace.

The wrappers copy the caller's request kwargs into ``run.inputs``. Several
providers accept credentials inside those kwargs -- remote MCP server tokens,
per-request auth headers -- so anything that is a credential by construction is
masked here before it is traced.

Every helper returns new containers. The caller's own objects are still sent to
the provider API and must keep their real values.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any, Optional

from langsmith.anonymizer import SECRET_PLACEHOLDER

__all__ = ["mask", "redact_outside", "redact_keys"]

# Request params are shallow; a cyclic or pathological payload must not turn
# tracing into a hang.
_MAX_DEPTH = 12


def _as_mapping(value: Any) -> Optional[Mapping]:
    """Return ``value`` as a mapping, converting Pydantic models best-effort.

    Some provider configs reach tracing as model instances whose credential
    fields are only visible after a dump.
    """
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
    """Mask ``value``, keeping key names so a trace still shows what was set."""
    mapping = _as_mapping(value)
    if mapping is not None:
        return {key: SECRET_PLACEHOLDER for key in mapping}
    return SECRET_PLACEHOLDER


def redact_outside(entry: Any, safe_keys: Collection[str]) -> Any:
    """Copy ``entry`` with every value outside ``safe_keys`` masked.

    Keys keep their names, so a trace still shows the field was set, and a
    credential field the provider adds later is masked by default rather than
    exported.
    """
    mapping = _as_mapping(entry)
    if mapping is None:
        return entry
    return {
        key: value if key in safe_keys else SECRET_PLACEHOLDER
        for key, value in mapping.items()
    }


def redact_keys(value: Any, secret_keys: Collection[str], _depth: int = 0) -> Any:
    """Recursively mask the value of any mapping key named in ``secret_keys``.

    Use where a provider hides credentials across several unrelated subtrees and
    a per-site allowlist would need a new patch every release. Scope it to the
    config-shaped part of a payload; walking user message content would mask
    legitimate tool arguments and schema properties.
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
