# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional

from .._models import BaseModel

__all__ = ["OnlineSpendLimit"]


class OnlineSpendLimit(BaseModel):
    limit_usd: Optional[float] = None

    utilization_pct: Optional[float] = None

    window: Optional[str] = None
