# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional

from .._models import BaseModel
from .sandbox_response import SandboxResponse

__all__ = ["SandboxListResponse"]


class SandboxListResponse(BaseModel):
    offset: Optional[int] = None

    sandboxes: Optional[List[SandboxResponse]] = None
