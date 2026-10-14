# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing_extensions import Literal

from ..._models import BaseModel

__all__ = ["ThreadActivateSandboxResponse"]


class ThreadActivateSandboxResponse(BaseModel):
    sandbox_slug: str

    scope: Literal["agent", "thread"]

    status: Literal["provisioning", "ready", "failed", "stopped", "deleting"]
