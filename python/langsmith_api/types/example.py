# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, Optional
from datetime import datetime

from .._models import BaseModel

__all__ = ["Example"]


class Example(BaseModel):
    """Example schema."""

    id: str

    dataset_id: str

    inputs: Dict[str, object]

    name: str

    attachment_urls: Optional[Dict[str, object]] = None

    created_at: Optional[datetime] = None

    metadata: Optional[Dict[str, object]] = None

    modified_at: Optional[datetime] = None

    outputs: Optional[Dict[str, object]] = None

    source_run_id: Optional[str] = None
