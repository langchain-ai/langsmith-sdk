# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Literal, Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["RepoCreateParams"]


class RepoCreateParams(TypedDict, total=False):
    is_public: Required[bool]

    repo_handle: Required[str]

    description: Optional[str]

    readme: Optional[str]

    repo_type: Literal["prompt", "file", "agent", "skill"]

    restricted_mode: Optional[bool]

    source: Optional[Literal["internal", "external"]]

    tags: Optional[SequenceNotStr[str]]
