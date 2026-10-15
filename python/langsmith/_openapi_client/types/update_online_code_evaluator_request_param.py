# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional
from typing_extensions import Literal, TypedDict

from .._types import SequenceNotStr

__all__ = ["UpdateOnlineCodeEvaluatorRequestParam", "ManagedCodeEvaluatorSettings"]


class ManagedCodeEvaluatorSettings(TypedDict, total=False):
    is_enabled: bool

    key_name: str


class UpdateOnlineCodeEvaluatorRequestParam(TypedDict, total=False):
    advanced_features_enabled: bool

    code: str

    code_evaluator_input: Optional[Literal["thread", "all_messages", "human_ai_pairs", "first_human_last_ai"]]
    """CodeEvaluatorInput is config (not a snapshot rebuild). Null clears it."""

    dependencies: Optional[str]

    language: str

    managed_code_evaluator_settings: Dict[str, ManagedCodeEvaluatorSettings]

    require_attachments: bool
    """
    RequireAttachments is fetch-time config: updating it does not rebuild the
    sandbox snapshot.
    """

    workspace_secrets_keys: SequenceNotStr[str]
    """
    WorkspaceSecretsKeys names the workspace secrets this evaluator may use. Each is
    sent as a header on requests to the hosts allowed for that secret; evaluator
    code never sees the value. Requires advanced_features_enabled, and each secret
    needs an allowed host with a header. Omit to keep the current list; [] clears
    it. Changing it does not rebuild the evaluator.
    """
