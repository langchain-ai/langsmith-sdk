# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Optional
from datetime import datetime
from typing_extensions import Required, Annotated, TypedDict

from ..._types import SequenceNotStr
from ..._utils import PropertyInfo

__all__ = ["ExperimentGroupedParams"]


class ExperimentGroupedParams(TypedDict, total=False):
    metadata_keys: Required[SequenceNotStr[str]]

    dataset_version: Optional[str]

    experiment_limit: int

    filter: Optional[str]

    name_contains: Optional[str]

    stats_start_time: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    tag_value_id: Optional[SequenceNotStr[str]]

    use_approx_stats: bool
