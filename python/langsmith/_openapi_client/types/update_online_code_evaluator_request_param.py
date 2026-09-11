# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict

__all__ = ["UpdateOnlineCodeEvaluatorRequestParam"]


class UpdateOnlineCodeEvaluatorRequestParam(TypedDict, total=False):
    advanced_features_enabled: bool

    code: str

    dependencies: Optional[str]

    language: str
