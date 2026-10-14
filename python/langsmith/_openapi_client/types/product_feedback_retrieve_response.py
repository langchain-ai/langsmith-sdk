# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional
from datetime import datetime
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["ProductFeedbackRetrieveResponse", "Client"]


class Client(BaseModel):
    architecture: Optional[str] = None

    os: Optional[str] = None

    version: Optional[str] = None


class ProductFeedbackRetrieveResponse(BaseModel):
    id: str

    category: Literal["BUG", "FEATURE_REQUEST", "USABILITY", "DOCUMENTATION", "OTHER"]

    created_at: datetime

    message: str

    source: Literal["LANGSMITH_CLI"]

    client: Optional[Client] = None
