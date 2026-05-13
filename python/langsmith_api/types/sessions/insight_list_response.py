# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, Optional
from datetime import datetime

from ..._models import BaseModel

__all__ = ["InsightListResponse"]


class InsightListResponse(BaseModel):
    """Session cluster job"""

    id: str

    created_at: datetime

    name: str

    status: str

    config_id: Optional[str] = None

    end_time: Optional[datetime] = None

    error: Optional[str] = None

    metadata: Optional[Dict[str, object]] = None

    shape: Optional[Dict[str, int]] = None

    start_time: Optional[datetime] = None
