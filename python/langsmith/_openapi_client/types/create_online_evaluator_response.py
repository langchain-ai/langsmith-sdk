# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional

from .._models import BaseModel
from .online_evaluator import OnlineEvaluator

__all__ = ["CreateOnlineEvaluatorResponse"]


class CreateOnlineEvaluatorResponse(BaseModel):
    evaluator: Optional[OnlineEvaluator] = None
