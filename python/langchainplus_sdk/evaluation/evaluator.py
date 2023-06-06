from abc import abstractmethod
from typing import Dict, Optional, Union

from pydantic import BaseModel

from langchainplus_sdk.schemas import SCORE_TYPE, VALUE_TYPE, Example, Run


class EvaluationResult(BaseModel):
    """Evaluation result."""

    key: str
    score: SCORE_TYPE = None
    value: VALUE_TYPE = None
    comment: Optional[str] = None
    correction: Optional[Union[Dict, str]] = None
    evaluator_info: Optional[Dict] = None

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
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement aevaluate_run"
        )
