# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, Optional
from datetime import datetime

from ..._models import BaseModel

__all__ = ["InfoListResponse", "BatchIngestConfig", "CustomerInfo"]


class BatchIngestConfig(BaseModel):
    """Batch ingest config."""

    scale_down_nempty_trigger: Optional[int] = None

    scale_up_nthreads_limit: Optional[int] = None

    scale_up_qsize_trigger: Optional[int] = None

    size_limit: Optional[int] = None

    size_limit_bytes: Optional[int] = None

    use_multipart_endpoint: Optional[bool] = None


class CustomerInfo(BaseModel):
    """Customer info."""

    customer_id: str

    customer_name: str


class InfoListResponse(BaseModel):
    """The LangSmith server info."""

    version: str

    batch_ingest_config: Optional[BatchIngestConfig] = None
    """Batch ingest config."""

    customer_info: Optional[CustomerInfo] = None
    """Customer info."""

    git_sha: Optional[str] = None

    instance_flags: Optional[Dict[str, object]] = None

    license_expiration_time: Optional[datetime] = None
