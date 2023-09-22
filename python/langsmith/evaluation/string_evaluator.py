from typing import Callable, Dict, Optional

from langsmith.evaluation.evaluator import EvaluationResult, RunEvaluator
from langsmith.schemas import Example, Run


class StringEvaluator(RunEvaluator):
    """Grades the run's string input, output, and optional answer.

    Args:
        evaluation_name: The name evaluation, such as 'Accuracy' or 'Salience'.
        input_key: The key in the run inputs to extract the input string.
        prediction_key: The key in the run outputs to extra the prediction string.
        answer_key: The key in the example outputs the answer string.
        grading_function: Function that grades the run output against
            the example output.
    """

    def __init__(
        self,
        evaluation_name: str,
        *,
        input_key: str = "input",
        prediction_key: str = "output",
        answer_key: Optional[str] = "output",
        grading_function: Callable[[str, str, Optional[str]], Dict]
    ) -> None:
        """Initialize the evaluator.

        Args:
            evaluation_name: The name evaluation, such as 'Accuracy' or 'Salience'.
            input_key: The key in the run inputs to extract the input string.
            prediction_key: The key in the run outputs to extra the prediction string.
            answer_key: The key in the example outputs the answer string.
            grading_function: Function that grades the run output
                against the example output.
        """
        self.evaluation_name = evaluation_name
        self.input_key = input_key
        self.prediction_key = prediction_key
        self.answer_key = answer_key
        self.grading_function = grading_function

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
