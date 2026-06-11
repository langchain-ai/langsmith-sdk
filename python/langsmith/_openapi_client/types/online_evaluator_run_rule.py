# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional

from .._models import BaseModel
from .online_spend_limit import OnlineSpendLimit

__all__ = ["OnlineEvaluatorRunRule"]


class OnlineEvaluatorRunRule(BaseModel):
    id: Optional[str] = None

    corrections_dataset_id: Optional[str] = None

    dataset_id: Optional[str] = None

    dataset_name: Optional[str] = None

    group_by: Optional[str] = None

    num_few_shot_examples: Optional[int] = None

    session_id: Optional[str] = None

    session_name: Optional[str] = None

    spend_limit: Optional[OnlineSpendLimit] = None
    """
    SpendLimit is the effective spend-cap limit for this rule (nil when
    unconfigured).
    """

    spend_usd: Optional[float] = None
    """
    Per-rule spend for the current ISO week (omitted when feature is disabled).
    LLM-evaluator rules are initialized to 0; code-evaluator rules remain nil.
    """

    trace_count: Optional[int] = None

    use_corrections_dataset: Optional[bool] = None
