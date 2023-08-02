from abc import abstractmethod
from typing import Dict, Optional, Union

from langsmith.schemas import SCORE_TYPE, VALUE_TYPE, Example, Run
from langsmith.utils import DictMixin


class EvaluationResult(DictMixin):
    """Evaluation result."""

    def __init__(
        self,
        key: str,
        *,
        score: SCORE_TYPE = None,
        value: VALUE_TYPE = None,
        comment: Optional[str] = None,
        correction: Optional[Union[Dict, str]] = None,
        evaluator_info: Optional[Dict] = None,
    ) -> None:
        """Initialize the evaluation result.

        Args:
            key: The aspect, metric name, or label for this evaluation.
            score: The numeric score for this evaluation.
            value: The value for this evaluation, if not numeric.
            comment: An explanation regarding the evaluation.
            correction: What the correct value should be, if applicable.
            evaluator_info: Additional information about the evaluator.
        """
        super().__init__()
        self.key = key
        self.score = score
        self.value = value
        self.comment = comment
        self.correction = correction
        self.evaluator_info = evaluator_info


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
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement aevaluate_run"
        )
