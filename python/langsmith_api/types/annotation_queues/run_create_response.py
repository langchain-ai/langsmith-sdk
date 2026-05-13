# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from datetime import datetime
from typing_extensions import TypeAlias

from ..._models import BaseModel

__all__ = ["RunCreateResponse", "RunCreateResponseItem"]


class RunCreateResponseItem(BaseModel):
    id: str

    queue_id: str

    run_id: str

    added_at: Optional[datetime] = None

    last_reviewed_time: Optional[datetime] = None

    source_proposed_example_id: Optional[str] = None


RunCreateResponse: TypeAlias = List[RunCreateResponseItem]
