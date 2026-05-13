# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime

from .._models import BaseModel

__all__ = ["CommitManifestResponse", "Example"]


class Example(BaseModel):
    """Response model for example runs"""

    id: str

    session_id: str

    inputs: Optional[Dict[str, object]] = None

    outputs: Optional[Dict[str, object]] = None

    start_time: Optional[datetime] = None


class CommitManifestResponse(BaseModel):
    """Response model for get_commit_manifest."""

    commit_hash: str

    manifest: Dict[str, object]

    examples: Optional[List[Example]] = None
