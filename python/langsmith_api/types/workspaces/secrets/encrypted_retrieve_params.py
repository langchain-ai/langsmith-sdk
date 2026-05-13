# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Literal, Required, TypedDict

from ...._types import SequenceNotStr

__all__ = ["EncryptedRetrieveParams"]


class EncryptedRetrieveParams(TypedDict, total=False):
    service: Required[Literal["agent_builder", "polly"]]
    """Service requesting encrypted secrets"""

    expand_iam_role: bool
    """If true, expand AWS_IAM_ROLE_ARN into temporary credentials via STS"""

    key_names: Optional[SequenceNotStr[str]]
    """Optional list of workspace secret keys to return"""
