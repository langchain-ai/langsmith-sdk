from abc import abstractmethod
from typing import Callable, Dict, Optional, Union

from pydantic import BaseModel

from langchainplus_sdk.schemas import SCORE_TYPE, VALUE_TYPE, Example, Run


class EvaluationResult(BaseModel):
    """Evaluation result."""

    key: str
    score: SCORE_TYPE = None
    value: VALUE_TYPE = None
    comment: Optional[str] = None
    correction: Optional[Union[Dict, str]] = None

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


class StringEvaluator(RunEvaluator, BaseModel):
    """Grades the run's string input, output, and optional answer."""

    evaluation_name: Optional[str] = None
    """The name evaluation, such as 'Accuracy' or 'Salience'."""
    input_key: str = "input"
    """The key in the run inputs to extract the input string."""
    prediction_key: str = "output"
    """The key in the run outputs to extra the prediction string."""
    answer_key: Optional[str] = None
    """The key in the example outputs the answer string."""
    grading_function: Callable[[str, str, Optional[str]], Dict]
    """Function that grades the run output against the example output."""

    def evaluate_run(
        self, run: Run, example: Optional[Example] = None
    ) -> EvaluationResult:
        """Evaluate a single run."""
        if run.outputs is None:
            raise ValueError("Run outputs cannot be None.")
        if not example or example.outputs is None or self.answer_key is None:
            answer = None
        else:
            answer = example.outputs.get(self.answer_key)
        run_input = run.inputs[self.input_key]
        run_output = run.outputs[self.prediction_key]
        grading_results = self.grading_function(run_input, run_output, answer)
        return EvaluationResult(key=self.evaluation_name, **grading_results)
