# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from datetime import datetime

from .._models import BaseModel

__all__ = ["DatasetVersion"]


class DatasetVersion(BaseModel):
    """Dataset version schema."""

    as_of: datetime

    tags: Optional[List[str]] = None
