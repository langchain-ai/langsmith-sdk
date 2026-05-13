# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["RepoUpdateParams"]


class RepoUpdateParams(TypedDict, total=False):
    owner: Required[str]

    description: Optional[str]

    is_archived: Optional[bool]

    is_public: Optional[bool]

    readme: Optional[str]

    restricted_mode: Optional[bool]

    tags: Optional[SequenceNotStr[str]]
