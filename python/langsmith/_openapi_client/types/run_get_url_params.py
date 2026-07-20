# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

__all__ = ["RunGetURLParams"]


class RunGetURLParams(TypedDict, total=False):
    project_id: Required[str]
    """Project (session) UUID"""

    trace_id: Required[str]
    """Trace UUID"""

    start_time: str
    """Run start time in RFC3339 format; omit if unknown"""
