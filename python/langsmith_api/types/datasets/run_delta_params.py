# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional
from typing_extensions import Required, TypedDict

from ..._types import SequenceNotStr

__all__ = ["RunDeltaParams"]


class RunDeltaParams(TypedDict, total=False):
    baseline_session_id: Required[str]

    comparison_session_ids: Required[SequenceNotStr[str]]

    feedback_key: Required[str]

    comparative_experiment_id: Optional[str]

    filters: Optional[Dict[str, SequenceNotStr[str]]]

    limit: int

    offset: int
