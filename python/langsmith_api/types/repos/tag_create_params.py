# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union
from typing_extensions import Required, TypedDict

from ..._types import SequenceNotStr

__all__ = ["TagCreateParams"]


class TagCreateParams(TypedDict, total=False):
    owner: Required[str]

    commit_id: Required[str]

    tag_name: Required[str]

    skip_webhooks: Union[bool, SequenceNotStr[str]]
