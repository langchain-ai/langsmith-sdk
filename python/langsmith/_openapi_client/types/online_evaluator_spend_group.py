# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional

from .._models import BaseModel
from .online_spend_limit import OnlineSpendLimit
from .online_evaluator_spend_day import OnlineEvaluatorSpendDay

__all__ = ["OnlineEvaluatorSpendGroup"]


class OnlineEvaluatorSpendGroup(BaseModel):
    dataset_id: Optional[str] = None

    dataset_name: Optional[str] = None

    days: Optional[List[OnlineEvaluatorSpendDay]] = None

    evaluator_id: Optional[str] = None

    evaluator_name: Optional[str] = None

    prev_total_spend_usd: Optional[float] = None

    prev_total_trace_count: Optional[int] = None

    run_rule_id: Optional[str] = None

    run_rule_name: Optional[str] = None

    session_id: Optional[str] = None

    session_name: Optional[str] = None

    spend_limit: Optional[OnlineSpendLimit] = None

    total_spend_usd: Optional[float] = None

    total_trace_count: Optional[int] = None
