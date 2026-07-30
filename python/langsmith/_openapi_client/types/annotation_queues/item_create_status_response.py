# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional
from typing_extensions import Literal

from ..._models import BaseModel

__all__ = ["ItemCreateStatusResponse"]


class ItemCreateStatusResponse(BaseModel):
    is_archived: Optional[bool] = None

    override_added_at: Optional[str] = None

    queue_item_id: Optional[str] = None

    status: Optional[Literal["viewed", "completed"]] = None
