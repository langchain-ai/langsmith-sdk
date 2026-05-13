# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional

from ..._models import BaseModel

__all__ = ["InsightRetrieveRunsResponse"]


class InsightRetrieveRunsResponse(BaseModel):
    offset: Optional[int] = None

    runs: List[Dict[str, object]]
