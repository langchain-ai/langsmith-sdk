# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional
from typing_extensions import TypedDict

__all__ = ["UpdateOnlineCodeEvaluatorRequestParam", "ManagedCodeEvaluatorSettings"]


class ManagedCodeEvaluatorSettings(TypedDict, total=False):
    is_enabled: bool

    key_name: str


class UpdateOnlineCodeEvaluatorRequestParam(TypedDict, total=False):
    advanced_features_enabled: bool

    code: str

    dependencies: Optional[str]

    language: str

    managed_code_evaluator_settings: Dict[str, ManagedCodeEvaluatorSettings]
