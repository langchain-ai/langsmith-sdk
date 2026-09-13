# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional

from ..._models import BaseModel

__all__ = ["SnapshotRetrieveByNameResponse", "Tag"]


class Tag(BaseModel):
    snapshot_id: Optional[str] = None

    tag: Optional[str] = None


class SnapshotRetrieveByNameResponse(BaseModel):
    name: Optional[str] = None

    tags: Optional[List[Tag]] = None
