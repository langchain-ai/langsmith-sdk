# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional

from .._models import BaseModel
from .bulk_delete_evaluator_failed_item import BulkDeleteEvaluatorFailedItem

__all__ = ["BulkDeleteEvaluatorsResponse"]


class BulkDeleteEvaluatorsResponse(BaseModel):
    failed: Optional[List[BulkDeleteEvaluatorFailedItem]] = None

    succeeded: Optional[List[str]] = None
