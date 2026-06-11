# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import TypedDict

__all__ = ["UpdateOnlineLlmEvaluatorRequestParam"]


class UpdateOnlineLlmEvaluatorRequestParam(TypedDict, total=False):
    commit_hash_or_tag: str

    num_few_shot_examples: int

    prompt_repo_handle: str

    use_corrections_dataset: bool

    variable_mapping: object
