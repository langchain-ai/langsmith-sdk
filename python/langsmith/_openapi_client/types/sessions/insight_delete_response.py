# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from ..._models import BaseModel

__all__ = ["InsightDeleteResponse"]


class InsightDeleteResponse(BaseModel):
    """Response to delete a session cluster job."""

    id: str

    message: str
