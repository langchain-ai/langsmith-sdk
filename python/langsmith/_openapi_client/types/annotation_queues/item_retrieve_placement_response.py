# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional
from typing_extensions import Literal

from ..._models import BaseModel

__all__ = ["ItemRetrievePlacementResponse"]


class ItemRetrievePlacementResponse(BaseModel):
    cursor: Optional[str] = None

    item_type: Optional[Literal["RUN", "THREAD"]] = None

    position: Optional[int] = None

    section: Optional[Literal["needs_my_review", "needs_others_review", "archived"]] = None
