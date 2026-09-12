# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["OnlineCodeEvaluator"]


class OnlineCodeEvaluator(BaseModel):
    advanced_features_enabled: Optional[bool] = None

    code: Optional[str] = None

    dependencies: Optional[str] = None

    evaluator_build_error: Optional[str] = None

    evaluator_build_status: Optional[Literal["ENQUEUED", "BUILDING", "READY", "FAILED"]] = None

    evaluator_id: Optional[str] = None

    language: Optional[str] = None
    """Default: "python" """
