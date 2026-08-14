# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["OnlineEvaluatorSpendParams"]


class OnlineEvaluatorSpendParams(TypedDict, total=False):
    period_start: Required[str]
    """Start of the 7-day window (YYYY-MM-DD)."""

    dataset_id: str
    """Filter to a specific dataset (UUID). Mutually exclusive with group_by."""

    evaluator_id: str
    """Filter to a specific evaluator (UUID). Mutually exclusive with group_by."""

    feedback_key: str
    """Filter grouped results by evaluator feedback key. Only valid with group_by."""

    group_by: str
    """Aggregation mode: 'evaluator', 'resource', or 'run_rule'.

    Mutually exclusive with entity filters.
    """

    resource_id: SequenceNotStr[str]
    """
    Filter grouped results to evaluators attached to all supplied project or dataset
    IDs. Only valid with group_by.
    """

    session_id: str
    """Filter to a specific project (UUID). Mutually exclusive with group_by."""

    type: str
    """Filter grouped results by evaluator type: 'llm' or 'code'.

    Only valid with group_by.
    """
