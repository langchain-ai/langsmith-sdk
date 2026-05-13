# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from datetime import datetime

from ..._models import BaseModel

__all__ = ["FeedbackIngestTokenSchema"]


class FeedbackIngestTokenSchema(BaseModel):
    """Feedback ingest token schema."""

    id: str

    expires_at: datetime

    feedback_key: str

    url: str
