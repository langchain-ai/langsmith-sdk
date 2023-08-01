import json
from abc import abstractmethod
from typing import Any, Dict, Optional, Union

from langsmith.schemas import SCORE_TYPE, VALUE_TYPE, Example, Run
from langsmith.utils import serialize_json


class EvaluationResult(dict):
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
        setattr(self, "key", key)
        setattr(self, "score", score)
        setattr(self, "value", value)
        setattr(self, "comment", comment)
        setattr(self, "correction", correction)
        setattr(self, "evaluator_info", evaluator_info)

    def __setattr__(self, k: str, v: Any):
        if k[0] == "_" or k in self.__dict__:
            return super().__setattr__(k, v)
        self[k] = v
        return None

    def __getattr__(self, k):
        if k[0] == "_":
            raise AttributeError(k)
        try:
            return self[k]
        except KeyError as err:
            raise AttributeError(*err.args)

    def __delattr__(self, k):
        if k[0] == "_" or k in self.__dict__:
            return super().__delattr__(k)
        else:
            del self[k]

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return json.dumps(self.__dict__, indent=2, default=serialize_json)


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
