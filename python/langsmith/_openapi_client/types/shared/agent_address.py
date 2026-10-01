# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing_extensions import Literal

from ..._models import BaseModel

__all__ = ["AgentAddress"]


class AgentAddress(BaseModel):
    id: str
    """`id` is the Agent's user-assigned id."""

    environment: Literal["LOCAL", "DEVELOPMENT", "STAGING", "PRODUCTION"]
    """`environment` is the Agent environment."""

    kind: Literal["AGENT"]
