from abc import abstractmethod
from typing import Any, Callable, Optional, Tuple, Union

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


SCORE_TYPE = Union[bool, int, float, None]


class StringEvaluator(RunEvaluator, BaseModel):
    """Evaluator that grades the run against the optional answer."""

    evaluation_name: str
    """The name evaluation, such as 'Accuracy' or 'Salience'."""
    input_key: str
    """The key in the run inputs to extract the input string."""
    prediction_key: str
    """The key in the run outputs to extra the prediction string."""
    answer_key: str
    """The key in the example outputs the answer string."""
    grading_function: Callable[
        [str, str, Optional[str]], Tuple[Optional[str], SCORE_TYPE]
    ]
    """Function that grades the run output against the example output."""

    def evaluate_run(
        self, run: Run, example: Optional[Example] = None
    ) -> EvaluationResult:
        """Evaluate a single run."""
        if run.outputs is None:
            raise ValueError("Run outputs cannot be None.")
        if not example or example.outputs is None:
            answer = None
        else:
            answer = example.outputs.get(self.answer_key)
        run_input = run.inputs[self.input_key]
        run_output = run.outputs[self.prediction_key]
        feedback, score = self.grading_function(run_input, run_output, answer)
        return EvaluationResult(key=self.evaluation_name, score=score, value=feedback)
