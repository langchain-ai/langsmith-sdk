# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel
from .repo_with_lookups import RepoWithLookups

__all__ = ["CreateRepoResponse"]


class CreateRepoResponse(BaseModel):
    repo: RepoWithLookups
    """All database fields for repos, plus helpful computed fields."""
