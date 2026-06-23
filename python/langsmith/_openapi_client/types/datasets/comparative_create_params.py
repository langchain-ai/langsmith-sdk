# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Optional
from datetime import datetime
from typing_extensions import Required, Annotated, TypedDict

from ..._types import SequenceNotStr
from ..._utils import PropertyInfo

__all__ = ["ComparativeCreateParams"]


class ComparativeCreateParams(TypedDict, total=False):
    experiment_ids: Required[SequenceNotStr[str]]

    id: str

    created_at: Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]

    description: Optional[str]

    extra: Optional[Dict[str, object]]

    modified_at: Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]

    name: Optional[str]

    reference_dataset_id: Optional[str]
