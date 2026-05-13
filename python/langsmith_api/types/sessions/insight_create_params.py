# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Iterable, Optional
from datetime import datetime
from typing_extensions import Literal, Annotated, TypedDict

from ..._utils import PropertyInfo

__all__ = ["InsightCreateParams"]


class InsightCreateParams(TypedDict, total=False):
    attribute_schemas: Optional[Dict[str, object]]

    cluster_model: Optional[str]

    config_id: Optional[str]

    end_time: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    filter: Optional[str]

    hierarchy: Optional[Iterable[int]]

    is_scheduled: bool

    last_n_hours: Optional[int]

    model: Literal["openai", "anthropic"]

    name: Optional[str]

    partitions: Optional[Dict[str, str]]

    sample: Optional[float]

    start_time: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    summary_model: Optional[str]

    summary_prompt: Optional[str]

    user_context: Optional[Dict[str, str]]

    validate_model_secrets: bool
