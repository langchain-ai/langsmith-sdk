# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["OnlineEvaluatorBulkDeleteParams"]


class OnlineEvaluatorBulkDeleteParams(TypedDict, total=False):
    evaluator_ids: Required[SequenceNotStr[str]]
    """Evaluator IDs to delete"""

    delete_run_rules: bool
    """
    When true, delete all run rules for this evaluator before deleting the evaluator
    """
