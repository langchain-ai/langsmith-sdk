# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Literal, Required, TypedDict

__all__ = ["RunStatsGroupByParam"]


class RunStatsGroupByParam(TypedDict, total=False):
    """Group by param for run stats."""

    attribute: Required[Literal["name", "run_type", "tag", "metadata"]]

    max_groups: int

    path: Optional[str]
