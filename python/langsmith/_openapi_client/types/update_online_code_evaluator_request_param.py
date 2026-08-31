# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import TypedDict

from .._types import SequenceNotStr

__all__ = ["UpdateOnlineCodeEvaluatorRequestParam"]


class UpdateOnlineCodeEvaluatorRequestParam(TypedDict, total=False):
    code: str

    dependencies: str

    language: str

    workspace_secrets_keys: SequenceNotStr[str]
