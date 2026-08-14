# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional

from .._models import BaseModel

__all__ = ["OnlineEvaluatorSpendDay"]


class OnlineEvaluatorSpendDay(BaseModel):
    date: Optional[str] = None

    spend_usd: Optional[float] = None

    trace_count: Optional[int] = None
