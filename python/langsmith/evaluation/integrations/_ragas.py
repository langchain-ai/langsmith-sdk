from __future__ import annotations

from typing import TYPE_CHECKING

from langsmith.evaluation.evaluator import RunEvaluator
from langsmith.evaluation.integrations._base import EvaluatorWrapper

if TYPE_CHECKING:
    from ragas.integrations.langchain import EvaluatorChain
    from ragas.metrics import Metric


def _import_ragas() -> EvaluatorChain:
    try:
        from ragas.integrations.langchain import EvaluatorChain

        return EvaluatorChain
    except ImportError:
        raise ImportError(
            "Please install a recent version of the `ragas` package to"
            " use the RAGAS metrics."
        )


class RagasEvaluator(EvaluatorWrapper):
    """A class that represents a RagasEvaluator.

    This class is responsible for wrapping an evaluator and providing a method
    to retrieve it as a RunEvaluator.

    Attributes:
        evaluator (Metric): The evaluator to be wrapped.

    Methods:
        __init__(self, evaluator: Metric) -> None: Initializes
            the RagasEvaluator instance.
        as_run_evaluator(self) -> RunEvaluator: Returns the wrapped evaluator
            as a RunEvaluator.

    Examples:
        Creating a simple RagasEvaluator:

        >>> from ragas.metrics import answer_correctness
        >>> evaluator = RagasEvaluator(answer_correctness)  # doctest: +SKIP
        ...

        Using the `evaluate` API to evaluate a RAG run:
        >>> import langsmith
        >>> client = langsmith.Client()
        >>> client.clone_public_dataset("https://smith.langchain.com/public/56fe54cd-b7d7-4d3b-aaa0-88d7a2d30931/d")
        >>> dataset_name = "BaseCamp Q&A"
        >>> from langsmith.evaluation import evaluate
        >>> from langsmith.evaluation.integrations import RagasEvaluator
        >>> from ragas.metrics import (
            answer_correctness,
            answer_relevancy,
            context_precision,
            context_recall,
            context_relevancy,
            faithfulness,
        )

        >>> evaluators = [RagasEvaluator(eval) for eval in [
            answer_correctness,
            answer_relevancy,
            context_precision,
            context_recall,
            context_relevancy,
            faithfulness,
        ]]
        >>> def predict(inputs: dict) -> dict:
        ...     return {
        ...        "answer": "42",
        ...        "context": [
        ...            "LangSmith is cool",
        ...            "The meaning of life is 42",
        ...        ],
        ...      }
        >>> evaluate(
        ...    "my_project",
        ...     data=client.list_examples(dataset_name=dataset_name, limit=1),
        ...     evaluators=evaluators,
        ...     experiment_prefix="Placeholder Model",
        ...   )  # doctest: +SKIP
    """

    def __init__(self, evaluator: Metric) -> None:
        EvaluatorChain = _import_ragas()
        self.evaluator = EvaluatorChain(evaluator)

    def as_run_evaluator(self) -> RunEvaluator:
        """Returns the wrapped evaluator as a RunEvaluator.

        Returns:
            RunEvaluator: The wrapped evaluator as a RunEvaluator.
        """
        return self.evaluator
