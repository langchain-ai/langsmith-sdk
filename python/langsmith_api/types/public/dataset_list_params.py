# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import TypedDict

from ..sort_by_dataset_column import SortByDatasetColumn

__all__ = ["DatasetListParams"]


class DatasetListParams(TypedDict, total=False):
    limit: int

    offset: int

    sort_by: SortByDatasetColumn
    """Enum for available dataset columns to sort by."""

    sort_by_desc: bool
