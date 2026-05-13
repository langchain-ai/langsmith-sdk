# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List

from ..._models import BaseModel

__all__ = ["VersionRetrieveDiffResponse"]


class VersionRetrieveDiffResponse(BaseModel):
    """Dataset diff schema."""

    examples_added: List[str]

    examples_modified: List[str]

    examples_removed: List[str]
