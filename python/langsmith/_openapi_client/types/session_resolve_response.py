# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["SessionResolveResponse"]


class SessionResolveResponse(BaseModel):
    session_id: str
    """`session_id` is the tracing project (session) the address names."""
