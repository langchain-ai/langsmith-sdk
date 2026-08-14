# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional

from .._models import BaseModel

__all__ = ["SandboxStatusResponse"]


class SandboxStatusResponse(BaseModel):
    status: Optional[str] = None

    status_message: Optional[str] = None
