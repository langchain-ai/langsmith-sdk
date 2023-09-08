import asyncio
import uuid
from abc import abstractmethod
from typing import Dict, Optional, Union

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

    class Config:
        """Pydantic model configuration."""

        frozen = True
        allow_extra = False


class RunEvaluator:
    """Evaluator interface class."""

    @abstractmethod
    def evaluate_run(
        self, run: Run, example: Optional[Example] = None
    ) -> EvaluationResult:
        """Evaluate an example."""

    async def aevaluate_run(
        self, run: Run, example: Optional[Example] = None
    ) -> EvaluationResult:
        """Evaluate an example asynchronously."""
        return await asyncio.get_running_loop().run_in_executor(
            None, self.evaluate_run, run, example
        )
