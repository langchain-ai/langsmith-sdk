# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional

from .._models import BaseModel

__all__ = ["BulkDeleteEvaluatorFailedItem"]


class BulkDeleteEvaluatorFailedItem(BaseModel):
    id: Optional[str] = None

    error: Optional[str] = None
