# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional
from typing_extensions import Literal, TypedDict

from .._types import SequenceNotStr

__all__ = ["CreateOnlineCodeEvaluatorRequestParam", "ManagedCodeEvaluatorSettings"]


class ManagedCodeEvaluatorSettings(TypedDict, total=False):
    is_enabled: bool

    key_name: str


class CreateOnlineCodeEvaluatorRequestParam(TypedDict, total=False):
    advanced_features_enabled: bool

    code: str

    code_evaluator_input: Optional[
        Literal["thread", "all_messages", "human_ai_pairs", "first_human_last_ai", "trajectory"]
    ]
    """
    CodeEvaluatorInput is which thread data the evaluator receives. Null or omitted
    for run evaluators.
    """

    dependencies: Optional[str]

    language: str
    """Default: "python" """

    managed_code_evaluator_key: Literal["voice_metrics"]

    managed_code_evaluator_settings: Dict[str, ManagedCodeEvaluatorSettings]

    require_attachments: bool
    """
    RequireAttachments opts the evaluator into selecting/presigning run attachments
    (s3_urls) at evaluation time. Default false.
    """

    workspace_secrets_keys: SequenceNotStr[str]
    """
    WorkspaceSecretsKeys names the workspace secrets this evaluator may use. Each is
    sent as a header on requests to the hosts allowed for that secret; evaluator
    code never sees the value. Requires advanced_features_enabled, and each secret
    needs an allowed host with a header.
    """
