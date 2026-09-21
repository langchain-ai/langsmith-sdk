"""Delegated LangSmith access for sandboxes."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal, TypedDict

AccessDelegationMode = Literal["INHERIT", "EXPLICIT"]


class AccessDelegation(TypedDict, total=False):
    """Grant letting code inside a sandbox call the LangSmith API as the creator.

    ``mode`` is ``"INHERIT"`` for everything the creator can do, or
    ``"EXPLICIT"`` for the subset named in ``permissions``. Permissions are a
    ceiling re-checked on every request rather than a snapshot, so access the
    creator loses is lost here too.
    """

    mode: AccessDelegationMode
    permissions: list[str]


def _validate_access_delegation(value: Any) -> AccessDelegation:
    """Reject grants the server would refuse, without the round trip."""
    if not isinstance(value, dict):
        raise ValueError("access_delegation must be a mapping")

    mode = value.get("mode")
    if mode not in ("INHERIT", "EXPLICIT"):
        raise ValueError('access_delegation["mode"] must be "INHERIT" or "EXPLICIT"')

    permissions = value.get("permissions")
    if permissions is not None and (
        isinstance(permissions, str) or not isinstance(permissions, Sequence)
    ):
        raise ValueError('access_delegation["permissions"] must be a list of strings')

    if mode == "INHERIT":
        if permissions:
            raise ValueError(
                'access_delegation["permissions"] is not allowed with mode "INHERIT"'
            )
        return {"mode": "INHERIT"}

    if not permissions:
        raise ValueError(
            'access_delegation["permissions"] is required with mode "EXPLICIT"'
        )
    return {"mode": "EXPLICIT", "permissions": list(permissions)}


def _access_delegation_from_dict(value: Any) -> AccessDelegation | None:
    if not isinstance(value, dict):
        return None
    mode = value.get("mode")
    if mode not in ("INHERIT", "EXPLICIT"):
        return None
    delegation: AccessDelegation = {"mode": mode}
    permissions = value.get("permissions")
    if permissions:
        delegation["permissions"] = list(permissions)
    return delegation
