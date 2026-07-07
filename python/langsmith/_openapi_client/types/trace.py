# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional

from .run import Run
from .._models import BaseModel
from .trace_aggregates import TraceAggregates

__all__ = ["Trace"]


class Trace(BaseModel):
    root_run: Optional[Run] = None
    """`root_run` is the trace's root run.

    Which properties are populated is controlled by `selects` in the request.
    """

    trace_aggregates: Optional[TraceAggregates] = None
    """`trace_aggregates` carries trace-wide aggregate metrics.

    Omitted when no aggregate field was selected, or `null` (then later filled) on
    the streaming wire while the aggregate values are still being computed.
    """
