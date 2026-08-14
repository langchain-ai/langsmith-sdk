# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional

from .._models import BaseModel

__all__ = ["OnlineLlmEvaluator"]


class OnlineLlmEvaluator(BaseModel):
    annotation_queue_id: Optional[str] = None

    commit_hash_or_tag: Optional[str] = None

    corrections_dataset_id: Optional[str] = None

    evaluator_id: Optional[str] = None

    num_few_shot_examples: Optional[int] = None

    prompt_id: Optional[str] = None

    prompt_repo_handle: Optional[str] = None

    use_corrections_dataset: Optional[bool] = None
    """
    Derived from the evaluator's run rules — shared across all rules on this
    evaluator. Nil when the evaluator has no run rules.
    """

    variable_mapping: Optional[object] = None
    """JSONB"""
