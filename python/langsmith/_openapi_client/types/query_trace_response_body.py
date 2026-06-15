# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional

from .._models import BaseModel
from .query_run_response import QueryRunResponse

__all__ = ["QueryTraceResponseBody"]


class QueryTraceResponseBody(BaseModel):
    items: Optional[List[QueryRunResponse]] = None
    """
    `items` lists runs in the trace for the requested time window, in `start_time`
    order.
    """
