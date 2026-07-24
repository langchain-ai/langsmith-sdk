"""This module contains the StringEvaluator class."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Callable, Optional, Union, cast

from pydantic import BaseModel

from langsmith.evaluation.evaluator import EvaluationResult, RunEvaluator
from langsmith.schemas import Example, Run, RunBase

if TYPE_CHECKING:
    from langsmith._openapi_client.types.run import Run as V2Run


class StringEvaluator(RunEvaluator, BaseModel):
    """Grades the run's string input, output, and optional answer.

    .. deprecated:: 0.5.0

       StringEvaluator is deprecated. Use openevals instead: https://github.com/langchain-ai/openevals
    """

    evaluation_name: Optional[str] = None
    """The name evaluation, such as `'Accuracy'` or `'Salience'`."""
    input_key: str = "input"
    """The key in the run inputs to extract the input string."""
    prediction_key: str = "output"
    """The key in the run outputs to extra the prediction string."""
    answer_key: Optional[str] = "output"
    """The key in the example outputs the answer string."""
    grading_function: Callable[[str, str, Optional[str]], dict]
    """Function that grades the run output against the example output."""

    def evaluate_run(
        self,
        run: Union[Run, RunBase, V2Run],
        example: Optional[Example] = None,
        evaluator_run_id: Optional[uuid.UUID] = None,
    ) -> EvaluationResult:
        """Evaluate a single run."""
        run_outputs = cast(Optional[dict], run.outputs)
        run_inputs = cast(dict, run.inputs)
        if run_outputs is None:
            raise ValueError("Run outputs cannot be None.")
        if not example or example.outputs is None or self.answer_key is None:
            answer = None
        else:
            answer = example.outputs.get(self.answer_key)
        run_input = run_inputs[self.input_key]
        run_output = run_outputs[self.prediction_key]
        grading_results = self.grading_function(run_input, run_output, answer)
        return EvaluationResult(**{"key": self.evaluation_name, **grading_results})

    @property
    def feedback_keys(self) -> list[str]:
        """The single key this evaluator emits, when its name is set."""
        return [self.evaluation_name] if self.evaluation_name else []
