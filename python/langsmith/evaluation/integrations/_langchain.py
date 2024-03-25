from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional, TypedDict, Union

from langchain.evaluation.schema import StringEvaluator
from langsmith.evaluation.evaluator import run_evaluator
from langsmith.run_helpers import traceable
from langsmith.schemas import Example, Run
from langchain_core.prompts import BasePromptTemplate

if TYPE_CHECKING:
    from langchain.evaluation.schema import StringEvaluator
    from langchain_core.language_models import BaseLanguageModel

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
            of the evaluator to 

    Methods:
        as_run_evaluator() -> RunEvaluator:
            Convert the LangChainStringEvaluator to a RunEvaluator.

    Examples:
        Creating a LangChainStringEvaluator from a configuration dictionary:

        .. code-block:: python

            evaluator = LangChainStringEvaluator("exact_match")

        Converting a LangChainStringEvaluator to a RunEvaluator:

        .. code-block:: python

            evaluator = LangChainStringEvaluator(...)
            run_evaluator = evaluator.as_run_evaluator()

        Preparing evaluator inputs:

        .. code-block:: python

            run = Run(...)
            example = Example(...)
            inputs = prepare_evaluator_inputs(run, example)

        Evaluating a run using the underlying StringEvaluator:

        .. code-block:: python

            run = Run(...)
            example = Example(...)
            results = evaluate(run, example)
    """

    def __init__(self, evaluator: Union[StringEvaluator, str], *, config: Optional[dict] = None):
        """Initialize a LangChainStringEvaluator.

        See: https://api.python.langchain.com/en/latest/evaluation/langchain.evaluation.schema.StringEvaluator.html#langchain-evaluation-schema-stringevaluator

        Args:
            evaluator (StringEvaluator): The underlying StringEvaluator.
        """
        from langchain.evaluation.schema import StringEvaluator # noqa: F811

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

        Examples:
            Loading an embedding distance evaluator:

            .. code-block:: python

                from langchain.evaluation import load_evaluator

                evaluator = load_evaluator("embedding_distance")

            Evaluating string similarity using embedding distance:

            .. code-block:: python

                evaluator.evaluate_strings(prediction="I shall go", reference="I shan't go")
                # Output: {'score': 0.0966466944859925}

                evaluator.evaluate_strings(prediction="I shall go", reference="I will go")
                # Output: {'score': 0.03761174337464557}

            Loading a regex match evaluator:

            .. code-block:: python

                from langchain.evaluation import load_evaluator

                evaluator = load_evaluator("regex_match")

            Evaluating string matches using regex patterns:

            .. code-block:: python

                evaluator.evaluate_strings(
                    prediction="The delivery will be made on 2024-01-05",
                    reference=".*\\b\\d{4}-\\d{2}-\\d{2}\\b.*",
                )
                # Output: {'score': 1}

                evaluator.evaluate_strings(
                    prediction="The delivery will be made on 01-05-2024",
                    reference="|".join(
                        [".*\\b\\d{4}-\\d{2}-\\d{2}\\b.*", ".*\\b\\d{2}-\\d{2}-\\d{4}\\b.*"]
                    ),
                )
                # Output: {'score': 1}
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


# TODO: Add classes
# class CriteriaEvalConfig(TypedDict):
#     llm: Optional[BaseLanguageModel]
#     criteria: Optional[Union[str, Dict[str, str]]]
#     prompt: Optional[BasePromptTemplate]

# class CriteriaEvaluator(LangChainStringEvaluator):

#     def __init__(self, config: Optional[CriteriaEvalConfig] = None):
#         super().__init__("criteria", config=config)


# class ScoreStringEvalConfig(CriteriaEvalConfig):
#     normalize_by: Optional[float]


# class ScoreStringEvaluator(LangChainStringEvaluator):

#     def __init__(self, config: Optional[ScoreStringEvalConfig] = None):
#         super().__init__("score_string", config=config)