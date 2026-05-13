# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from datetime import datetime

from ..._models import BaseModel

__all__ = ["TagCreateResponse"]


class TagCreateResponse(BaseModel):
    """Fields for a prompt tag"""

    id: str

    commit_hash: str

    commit_id: str

    created_at: datetime

    repo_id: str

    tag_name: str

    updated_at: datetime
