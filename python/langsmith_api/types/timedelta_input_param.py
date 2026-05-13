# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import TypedDict

__all__ = ["TimedeltaInputParam"]


class TimedeltaInputParam(TypedDict, total=False):
    """Timedelta input."""

    days: int

    hours: int

    minutes: int
