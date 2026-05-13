# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional

from ..._models import BaseModel

__all__ = ["BulkDeleteResponse"]


class BulkDeleteResponse(BaseModel):
    count: Optional[int] = None

    example_ids: Optional[List[str]] = None
