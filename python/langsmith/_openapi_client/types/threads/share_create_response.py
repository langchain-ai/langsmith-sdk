# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional

from ..._models import BaseModel

__all__ = ["ShareCreateResponse"]


class ShareCreateResponse(BaseModel):
    share_token: Optional[str] = None
