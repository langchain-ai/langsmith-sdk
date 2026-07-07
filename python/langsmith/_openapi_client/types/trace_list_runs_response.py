# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional

from .run import Run
from .._models import BaseModel

__all__ = ["TraceListRunsResponse"]


class TraceListRunsResponse(BaseModel):
    items: Optional[List[Run]] = None
    """
    `items` lists runs in the trace for the requested time window, in `start_time`
    order.
    """
