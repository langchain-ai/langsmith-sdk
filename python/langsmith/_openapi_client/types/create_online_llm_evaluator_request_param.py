# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import TypedDict

__all__ = ["CreateOnlineLlmEvaluatorRequestParam"]


class CreateOnlineLlmEvaluatorRequestParam(TypedDict, total=False):
    commit_hash_or_tag: str

    prompt_repo_handle: str

    variable_mapping: object
