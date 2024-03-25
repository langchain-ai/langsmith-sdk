from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, TypedDict, Union

from langchain.evaluation.schema import StringEvaluator

from langsmith.evaluation.evaluator import run_evaluator
from langsmith.run_helpers import traceable
from langsmith.schemas import Example, Run

if TYPE_CHECKING:
    from langchain.evaluation.schema import StringEvaluator

    from langsmith.evaluation.evaluator import RunEvaluator


class SingleEvaluatorInput(TypedDict):
    """The input to a `StringEvaluator`."""

    prediction: Optional[str]
    """The prediction string."""
    reference: Optional[Any]
    """The reference string."""
    input: Optional[str]
    """The input string."""


class LangChainStringEvaluator:
    """A class for wrapping a LangChain StringEvaluator.

    Attributes:
        evaluator (StringEvaluator): The underlying StringEvaluator OR the name
            of the evaluator to load.

    Methods:
        as_run_evaluator() -> RunEvaluator:
            Convert the LangChainStringEvaluator to a RunEvaluator.

    Examples:
        Creating a simple LangChainStringEvaluator:

        .. code-block:: python

            evaluator = LangChainStringEvaluator("exact_match")

        Converting a LangChainStringEvaluator to a RunEvaluator:

        .. code-block:: python

            from langsmith.evaluation import LangChainStringEvaluator

            evaluator = LangChainStringEvaluator(
                "criteria", 
                config={
                    "criteria": {
                        "usefulness": "The prediction is useful if"
                        " it is correct and/or asks a useful followup question."
                    },
            )
            run_evaluator = evaluator.as_run_evaluator()

        Using the `evaluate` API with different evaluators:

        .. code-block:: python

            from langchain_anthropic import ChatAnthropic

            import langsmith
            from langsmith.evaluation import LangChainStringEvaluator, evaluate

            # Criteria evaluator
            criteria_evaluator = LangChainStringEvaluator(
                "criteria", config={
                    "criteria": {
                        "usefulness": "The prediction is useful if it is correct"
                                " and/or asks a useful followup question."
                    },
                    "llm": ChatAnthropic(model="claude-3-opus-20240229")
                }
            )

            # Embedding distance evaluator
            embedding_evaluator = LangChainStringEvaluator("embedding_distance")

            # Exact match evaluator
            exact_match_evaluator = LangChainStringEvaluator("exact_match")

            # Regex match evaluator
            regex_match_evaluator = LangChainStringEvaluator(
                "regex_match", config={
                    "flags": re.IGNORECASE
                }
            )

            # Scoring evaluator
            scoring_evaluator = LangChainStringEvaluator(
                "scoring", config={
                    "criteria": {
                        "accuracy": "Score 1: Completely inaccurate\nScore 5: Somewhat accurate\nScore 10: Completely accurate"
                    },
                    "normalize_by": 10
                }
            )

            # String distance evaluator
            string_distance_evaluator = LangChainStringEvaluator(
                "string_distance", config={
                    "distance_metric": "levenshtein"
                }
            )

            results = evaluate(
                lambda inputs: {"prediction": "foo"},
                data="my-dataset",
                evaluators=[
                    embedding_evaluator,
                    criteria_evaluator,
                    exact_match_evaluator,
                    regex_match_evaluator,
                    scoring_evaluator,
                    string_distance_evaluator
                ],
                batch_evaluators=[equal_length],
            )
    """

    def __init__(self, evaluator: Union[StringEvaluator, str], *, config: Optional[dict] = None):
        """Initialize a LangChainStringEvaluator.

        See: https://api.python.langchain.com/en/latest/evaluation/langchain.evaluation.schema.StringEvaluator.html#langchain-evaluation-schema-stringevaluator

        Args:
            evaluator (StringEvaluator): The underlying StringEvaluator.
        """
        from langchain.evaluation.schema import StringEvaluator  # noqa: F811

        if isinstance(evaluator, StringEvaluator):
            self.evaluator = evaluator
        elif isinstance(evaluator, str):
            from langchain.evaluation import load_evaluator  # noqa: F811
            self.evaluator = load_evaluator(evaluator, **{config or {}})
        else:
            raise NotImplementedError(f"Unsupported evaluator type: {type(evaluator)}")

    def as_run_evaluator(self) -> RunEvaluator:
        """Convert the LangChainStringEvaluator to a RunEvaluator,

        which is the object used in the LangSmith `evaluate` API.

        Returns:
            RunEvaluator: The converted RunEvaluator.
        """

        @traceable
        def prepare_evaluator_inputs(
            run: Run, example: Optional[Example] = None
        ) -> SingleEvaluatorInput:
            return SingleEvaluatorInput(
                prediction=next(iter(run.outputs.values())) if run.outputs else None,
                reference=next(iter(example.outputs.values())) if (self.evaluator.requires_reference and example and example.outputs) else None,
                input=next(iter(example.inputs.values())) if (self.evaluator.requires_input and example.inputs) else None,
            )

        @traceable(name=self.evaluator.evaluation_name)
        def evaluate(run: Run, example: Optional[Example] = None) -> dict:
            eval_inputs = prepare_evaluator_inputs(run, example)
            results = self.evaluator.evaluate_strings(**eval_inputs)
            return {"key": self.evaluator.evaluation_name, **results}

        return run_evaluator(evaluate)
