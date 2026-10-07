# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["ProjectResolveResponse"]


class ProjectResolveResponse(BaseModel):
    session_id: str
    """`session_id` is the tracing project (session) the address names."""
