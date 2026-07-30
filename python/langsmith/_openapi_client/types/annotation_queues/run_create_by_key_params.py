# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Iterable, Optional
from datetime import datetime
from typing_extensions import Required, Annotated, TypedDict

from ..._utils import PropertyInfo

__all__ = ["RunCreateByKeyParams", "Body"]


class RunCreateByKeyParams(TypedDict, total=False):
    body: Required[Iterable[Body]]

    extend_trace_retention: bool


class Body(TypedDict, total=False):
    """Add run to AQ by SmithDB key. is_root derived server-side (LSAQ-141)."""

    run_id: Required[str]

    session_id: Required[str]

    start_time: Required[Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]]

    source_proposed_example_id: Optional[str]
