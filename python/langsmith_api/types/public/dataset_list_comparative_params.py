# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict

from ..datasets.sort_by_comparative_experiment_column import SortByComparativeExperimentColumn

__all__ = ["DatasetListComparativeParams"]


class DatasetListComparativeParams(TypedDict, total=False):
    limit: int

    name: Optional[str]

    name_contains: Optional[str]

    offset: int

    sort_by: SortByComparativeExperimentColumn
    """Enum for available comparative experiment columns to sort by."""

    sort_by_desc: bool
