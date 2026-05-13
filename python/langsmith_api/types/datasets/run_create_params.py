# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional
from typing_extensions import Literal, Required, TypedDict

from ..._types import SequenceNotStr
from .sort_params_for_runs_comparison_view_param import SortParamsForRunsComparisonViewParam

__all__ = ["RunCreateParams"]


class RunCreateParams(TypedDict, total=False):
    session_ids: Required[SequenceNotStr[str]]

    format: Optional[Literal["csv"]]
    """Response format, e.g., 'csv'"""

    comparative_experiment_id: Optional[str]

    example_ids: Optional[SequenceNotStr[str]]

    filters: Optional[Dict[str, SequenceNotStr[str]]]

    include_annotator_detail: bool

    limit: Optional[int]

    offset: int

    preview: bool

    sort_params: Optional[SortParamsForRunsComparisonViewParam]
