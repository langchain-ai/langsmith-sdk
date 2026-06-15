# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional

from .._models import BaseModel

__all__ = ["OnlineCodeEvaluator"]


class OnlineCodeEvaluator(BaseModel):
    code: Optional[str] = None

    evaluator_id: Optional[str] = None

    language: Optional[str] = None
    """Default: "python" """
