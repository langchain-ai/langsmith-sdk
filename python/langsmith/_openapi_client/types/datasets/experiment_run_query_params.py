# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, List
from typing_extensions import TypedDict

from ..._types import SequenceNotStr
from ..run_select_field import RunSelectField

__all__ = ["ExperimentRunQueryParams", "Sort"]


class ExperimentRunQueryParams(TypedDict, total=False):
    comparative_experiment_id: str
    """`comparative_experiment_id` scopes pairwise-annotation feedback (optional)."""

    cursor: str
    """`cursor` is the opaque string from a previous response's `next_cursor`.

    Absent for the first page.
    """

    example_ids: SequenceNotStr[str]
    """
    `example_ids` optionally restricts the page to these dataset example UUIDs (max
    1000).
    """

    experiment_ids: SequenceNotStr[str]
    """`experiment_ids` lists the experiment (tracing session) UUIDs to query.

    Required, non-empty.
    """

    filters: Dict[str, SequenceNotStr[str]]
    """
    `filters` maps a project (session) UUID string to a list of filter expressions
    (optional).
    """

    page_size: int
    """`page_size` is the maximum number of examples to return.

    Defaults to 20, max 100.
    """

    selects: List[RunSelectField]
    """`selects` lists which run properties to include.

    Omitted => only `id`. Tokens mirror /v2/runs/query.
    """

    sort: Sort
    """`sort` controls feedback-score sorting (single project only)."""


class Sort(TypedDict, total=False):
    """`sort` controls feedback-score sorting (single project only)."""

    by: str
    """`by` is the feedback selector, e.g.

    `feedback.correctness` (the `feedback.` prefix is optional).
    """

    order: str
    """`order` is `ASC` or `DESC` (defaults to `DESC`)."""
