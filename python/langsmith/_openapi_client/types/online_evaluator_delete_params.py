# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import TypedDict

__all__ = ["OnlineEvaluatorDeleteParams"]


class OnlineEvaluatorDeleteParams(TypedDict, total=False):
    delete_run_rules: bool
    """
    When true, delete all run rules for this evaluator before deleting the evaluator
    """
