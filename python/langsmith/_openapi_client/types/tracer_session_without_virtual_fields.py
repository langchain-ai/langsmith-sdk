# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, Optional
from datetime import datetime
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["TracerSessionWithoutVirtualFields"]


class TracerSessionWithoutVirtualFields(BaseModel):
    """TracerSession schema."""

    id: str

    tenant_id: str

    default_dataset_id: Optional[str] = None

    description: Optional[str] = None

    end_time: Optional[datetime] = None

    extra: Optional[Dict[str, object]] = None

    last_run_start_time_live: Optional[datetime] = None

    name: Optional[str] = None

    reference_dataset_id: Optional[str] = None

    start_time: Optional[datetime] = None

    trace_tier: Optional[Literal["longlived", "shortlived"]] = None
