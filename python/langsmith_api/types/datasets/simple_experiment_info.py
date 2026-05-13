# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from ..._models import BaseModel

__all__ = ["SimpleExperimentInfo"]


class SimpleExperimentInfo(BaseModel):
    """Simple experiment info schema for use with comparative experiments"""

    id: str

    name: str
