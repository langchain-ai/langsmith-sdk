# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from datetime import datetime
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["SandboxListUsageCostsResponse"]


class SandboxListUsageCostsResponse(BaseModel):
    lcu: str
    """
    Recorded compute usage in LangSmith Compute Units (LCU), as a decimal string
    with up to six fractional digits and trailing zeros omitted. Snapshots return
    "0".
    """

    lsu: str
    """
    Allocated storage usage in LangSmith Storage Units (LSU), as a decimal string
    with up to six fractional digits and trailing zeros omitted.
    """

    period_start: datetime

    resource_id: str

    resource_type: Literal["SANDBOX", "SNAPSHOT"]
