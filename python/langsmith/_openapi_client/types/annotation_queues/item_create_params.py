# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Iterable
from datetime import datetime
from typing_extensions import Literal, Annotated, TypedDict

from ..._utils import PropertyInfo

__all__ = ["ItemCreateParams", "Item"]


class ItemCreateParams(TypedDict, total=False):
    extend_trace_retention: bool
    """Extend trace retention for added run items"""

    items: Iterable[Item]


class Item(TypedDict, total=False):
    item_type: Literal["RUN", "THREAD"]

    project_id: str

    run_id: str
    """RUN fields"""

    session_id: str
    """SessionID is an alias for project_id."""

    source_proposed_example_id: str
    """
    SourceProposedExampleID links the queue item to the suggested example it was
    created from, when applicable.
    """

    start_time: Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]

    thread_id: str
