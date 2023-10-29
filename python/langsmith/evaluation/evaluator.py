import asyncio
import uuid
from abc import abstractmethod
from typing import Dict, Optional, TypedDict, Union

try:
    from pydantic.v1 import BaseModel, Field  # type: ignore[import]
except ImportError:
    from pydantic import BaseModel, Field

from langsmith.schemas import SCORE_TYPE, VALUE_TYPE, Example, Run


class EvaluationResult(BaseModel):
    """Evaluation result."""

    key: str
    """The aspect, metric name, or label for this evaluation."""
    score: SCORE_TYPE = None
    """The numeric score for this evaluation."""
    value: VALUE_TYPE = None
    """The value for this evaluation, if not numeric."""
    comment: Optional[str] = None
    """An explanation regarding the evaluation."""
    correction: Optional[Dict] = None
    """What the correct value should be, if applicable."""
    evaluator_info: Dict = Field(default_factory=dict)
    """Additional information about the evaluator."""
    source_run_id: Optional[Union[uuid.UUID, str]] = None
    """The ID of the trace of the evaluator itself."""
    target_run_id: Optional[Union[uuid.UUID, str]] = None
    """The ID of the trace this evaluation is applied to.
    
    If none provided, the evaluation feedback is applied to the
    root trace being."""

    class Config:
        """Pydantic model configuration."""

        allow_extra = False


class EvaluationResults(TypedDict, total=False):
    """Batch evaluation results, if your evaluator wishes
    to return multiple scores."""

    results: Dict[str, EvaluationResult]
    """The evaluation results."""


class RunEvaluator:
    """Evaluator interface class."""

    @abstractmethod
    def evaluate_run(
        self, run: Run, example: Optional[Example] = None
    ) -> Union[EvaluationResult, EvaluationResults]:
        """Evaluate an example."""

    async def aevaluate_run(
        self, run: Run, example: Optional[Example] = None
    ) -> Union[EvaluationResult, EvaluationResults]:
        """Evaluate an example asynchronously."""
        return await asyncio.get_running_loop().run_in_executor(
            None, self.evaluate_run, run, example
        )
