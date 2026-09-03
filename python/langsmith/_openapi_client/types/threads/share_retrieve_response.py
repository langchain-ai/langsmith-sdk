# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional

from ..._models import BaseModel

__all__ = ["ShareRetrieveResponse"]


class ShareRetrieveResponse(BaseModel):
    share_token: Optional[str] = None
