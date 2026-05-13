# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List
from typing_extensions import TypeAlias

from .feedback_ingest_token_schema import FeedbackIngestTokenSchema

__all__ = ["TokenListResponse"]

TokenListResponse: TypeAlias = List[FeedbackIngestTokenSchema]
