# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, Optional
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["OnlineCodeEvaluator", "ManagedCodeEvaluatorSettings"]


class ManagedCodeEvaluatorSettings(BaseModel):
    is_enabled: Optional[bool] = None

    key_name: Optional[str] = None


class OnlineCodeEvaluator(BaseModel):
    advanced_features_enabled: Optional[bool] = None

    code: Optional[str] = None

    dependencies: Optional[str] = None

    evaluator_build_error: Optional[str] = None

    evaluator_build_status: Optional[Literal["ENQUEUED", "BUILDING", "READY", "FAILED"]] = None

    evaluator_id: Optional[str] = None

    language: Optional[str] = None
    """Default: "python" """

    managed_code_evaluator_key: Optional[str] = None

    managed_code_evaluator_settings: Optional[Dict[str, ManagedCodeEvaluatorSettings]] = None
