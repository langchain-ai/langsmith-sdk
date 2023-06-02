from abc import abstractmethod
from typing import Any, Optional

from pydantic import BaseModel

from langchainplus_sdk.schemas import Example, Run


class EvaluationResult(BaseModel):
    """Evaluation result."""

    key: str
    score: Optional[float] = None
    value: Optional[Any] = None
    comment: Optional[str] = None
    correction: Optional[str] = None


class RunEvaluator:
    """Evaluator interface class."""

    @abstractmethod
    def evaluate_run(
        self, run: Run, example: Optional[Example] = None
    ) -> EvaluationResult:
        """Evaluate an example."""
