# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional

from ..._models import BaseModel

__all__ = ["InsightCreateResponse"]


class InsightCreateResponse(BaseModel):
    """Response to creating a run clustering job."""

    id: str

    name: str

    status: str

    error: Optional[str] = None
