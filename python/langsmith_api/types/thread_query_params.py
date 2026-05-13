# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union
from datetime import datetime
from typing_extensions import Annotated, TypedDict

from .._utils import PropertyInfo

__all__ = ["ThreadQueryParams"]


class ThreadQueryParams(TypedDict, total=False):
    cursor: str
    """`cursor` is the opaque string from a previous response's `next_cursor`.

    Omit on the first request; pass the returned cursor to fetch the next page.
    """

    filter: str
    """
    `filter` narrows which threads are returned, using a LangSmith filter expression
    evaluated against each thread's root run. For example: has(tags, "production")
    or eq(status, "error"). See
    https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
    for syntax.
    """

    max_start_time: Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]
    """
    `max_start_time` is the inclusive upper bound on thread activity (RFC3339
    date-time).
    """

    min_start_time: Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]
    """
    `min_start_time` is the inclusive lower bound on thread activity (RFC3339
    date-time).
    """

    page_size: int
    """`page_size` is the maximum number of threads to return in this response.

    Defaults to 20 when omitted; must be between 1 and 100 inclusive when set. The
    response may contain fewer threads than `page_size` even when `has_more` is
    true.
    """

    project_id: str
    """`project_id` is the tracing project UUID."""
