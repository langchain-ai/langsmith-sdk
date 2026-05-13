# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Optional
from typing_extensions import Literal, TypedDict

from .._types import SequenceNotStr

__all__ = ["RepoListParams"]


class RepoListParams(TypedDict, total=False):
    has_commits: Optional[bool]

    is_archived: Optional[Literal["true", "allow", "false"]]

    is_public: Optional[Literal["true", "false"]]

    limit: int

    offset: int

    query: Optional[str]

    repo_type: Optional[Literal["prompt", "file", "agent", "skill"]]

    repo_types: Optional[List[Literal["prompt", "file", "agent", "skill"]]]

    sort_direction: Optional[Literal["asc", "desc"]]

    sort_field: Optional[Literal["num_likes", "num_downloads", "num_views", "updated_at", "relevance"]]

    source: Optional[Literal["internal", "external"]]

    tag_value_id: Optional[SequenceNotStr[str]]

    tags: Optional[SequenceNotStr[str]]

    tenant_handle: Optional[str]

    tenant_id: Optional[str]

    upstream_repo_handle: Optional[str]

    upstream_repo_owner: Optional[str]

    with_latest_manifest: bool
