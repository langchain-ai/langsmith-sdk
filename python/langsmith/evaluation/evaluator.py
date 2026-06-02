# This module contains the evaluator classes for evaluating runs."

from __future__ import annotations

import asyncio
import inspect
import logging
import uuid
from abc import abstractmethod
from collections.abc import Awaitable, Sequence
from functools import wraps
from typing import (
    Any,
    Callable,
    Literal,
    Optional,
    Union,
    cast,
)

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from typing_extensions import TypedDict

from langsmith import run_helpers as rh
from langsmith import schemas
from langsmith.schemas import SCORE_TYPE, VALUE_TYPE, Example, Run

logger = logging.getLogger(__name__)


class Category(TypedDict):
    """A category for categorical feedback."""

    value: Optional[Union[float, int]]
    """The numeric score/ordinal corresponding to this category."""
    label: str
    """The label for this category."""


class FeedbackConfig(TypedDict, total=False):
    """Configuration to define a type of feedback.

    Applied on on the first creation of a `feedback_key`.
    """

    type: Literal["continuous", "categorical", "freeform"]
    """The type of feedback."""
    min: Optional[Union[float, int]]
    """The minimum permitted value (if continuous type)."""
    max: Optional[Union[float, int]]
    """The maximum permitted value (if continuous type)."""
    categories: Optional[list[Union[Category, dict]]]

VALID_FEEDBACK_CONFIG_KEYS: set = {"type", "min", "max", "categories"}

class EvaluationResult(BaseModel):
    """Evaluation result."""

    key: str
    """The aspect, metric name, or label for this evaluation."""
    score: SCORE_TYPE = None
    """The numeric score for this evaluation."""
    value: VALUE_TYPE = None
    """The value for this evaluation, if not numeric."""
    metadata: Optional[dict] = None
    """Arbitrary metadata attached to the evaluation."""
    comment: Optional[str] = None
    """An explanation regarding the evaluation."""
    correction: Optional[dict] = None
    """What the correct value should be, if applicable."""
    evaluator_info: dict = Field(default_factory=dict)
    """Additional information about the evaluator."""
    feedback_config: Optional[Union[FeedbackConfig, dict]] = None
    """The configuration used to generate this feedback."""
    source_run_id: Optional[Union[uuid.UUID, str]] = None
    """The ID of the trace of the evaluator itself."""
    target_run_id: Optional[Union[uuid.UUID, str]] = None
    """The ID of the trace this evaluation is applied to.

    If none provided, the evaluation feedback is applied to the
    root trace being."""
    extra: Optional[dict] = None
    """Metadata for the evaluator run."""

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def check_value_non_numeric(self) -> EvaluationResult:
        """Warn when numeric values are passed via the `value` field."""
        if self.score is None and isinstance(self.value, (int, float)):
            logger.warning(
                "Numeric values should be provided in the 'score' field, not 'value'."
                f" Got: {self.value}"
            )
        return self

    @field_validator("feedback_config", mode="before")
    @classmethod
    def validate_feedback_config(cls, v):
        if isinstance(v, dict):
            extra_keys = set(v.keys()) - VALID_FEEDBACK_CONFIG_KEYS
            if extra_keys:
                raise ValueError(
                    f"Unsupported key(s) in feedback_config: {', '.join(sorted(extra_keys))}. "
                    f"Supported keys are: {', '.join(sorted(VALID_FEEDBACK_CONFIG_KEYS))}"
                )
        return v


class EvaluationResults(TypedDict, total=False):
    """Batch evaluation results.

    This makes it easy for your evaluator to return multiple
    metrics at once.
    """

    results: list[EvaluationResult]
    """The evaluation results."""
