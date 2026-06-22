# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, Optional
from datetime import datetime

from ..._models import BaseModel

__all__ = ["ComparativeCreateResponse"]


class ComparativeCreateResponse(BaseModel):
    """ComparativeExperiment schema."""

    id: str

    created_at: datetime

    modified_at: datetime

    reference_dataset_id: str

    tenant_id: str

    description: Optional[str] = None

    extra: Optional[Dict[str, object]] = None

    name: Optional[str] = None
