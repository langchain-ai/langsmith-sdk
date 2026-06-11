# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional

from .._models import BaseModel
from .online_evaluator_spend_group import OnlineEvaluatorSpendGroup

__all__ = ["GetOnlineEvaluatorSpendResponse"]


class GetOnlineEvaluatorSpendResponse(BaseModel):
    groups: Optional[List[OnlineEvaluatorSpendGroup]] = None

    period_end: Optional[str] = None

    period_start: Optional[str] = None
