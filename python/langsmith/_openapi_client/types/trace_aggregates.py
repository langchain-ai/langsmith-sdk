# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional
from datetime import datetime

from .._models import BaseModel

__all__ = ["TraceAggregates"]


class TraceAggregates(BaseModel):
    first_token_time: Optional[datetime] = None
    """
    `first_token_time` is when the first output token was produced anywhere in the
    trace (RFC3339), when recorded.
    """

    total_cost: Optional[float] = None
    """`total_cost` is total estimated USD cost across every run in the trace."""

    total_tokens: Optional[int] = None
    """
    `total_tokens` is prompt plus completion tokens summed across every run in the
    trace.
    """
