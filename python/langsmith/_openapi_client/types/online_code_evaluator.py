# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["OnlineCodeEvaluator"]


class OnlineCodeEvaluator(BaseModel):
    code: Optional[str] = None

    dependencies: Optional[str] = None

    evaluator_build_error: Optional[str] = None

    evaluator_build_status: Optional[Literal["ENQUEUED", "BUILDING", "READY", "FAILED"]] = None

    evaluator_id: Optional[str] = None

    language: Optional[str] = None
    """Default: "python" """

    workspace_secrets_keys: Optional[List[str]] = None
