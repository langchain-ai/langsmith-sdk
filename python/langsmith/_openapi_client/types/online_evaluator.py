# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional

from .._models import BaseModel
from .online_llm_evaluator import OnlineLlmEvaluator
from .online_code_evaluator import OnlineCodeEvaluator
from .online_evaluator_type import OnlineEvaluatorType
from .online_evaluator_run_rule import OnlineEvaluatorRunRule

__all__ = ["OnlineEvaluator"]


class OnlineEvaluator(BaseModel):
    id: Optional[str] = None

    code_evaluator: Optional[OnlineCodeEvaluator] = None

    created_at: Optional[str] = None

    created_by: Optional[str] = None

    feedback_keys: Optional[List[str]] = None

    is_managed: Optional[bool] = None
    """
    IsManaged marks a LangChain-managed evaluator (currently the managed Perceived
    Error judge). NULL in the DB is read as false via COALESCE.
    """

    llm_evaluator: Optional[OnlineLlmEvaluator] = None
    """Embedded child evaluator (populated based on type)"""

    name: Optional[str] = None

    run_rules: Optional[List[OnlineEvaluatorRunRule]] = None

    tenant_id: Optional[str] = None

    type: Optional[OnlineEvaluatorType] = None

    updated_at: Optional[str] = None
