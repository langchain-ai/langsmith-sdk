from typing import Protocol, runtime_checkable

from langsmith.evaluation.evaluator import RunEvaluator


@runtime_checkable
class EvaluatorWrapper(Protocol):
    """A protocol that represents an evaluator wrapper."""

    def as_run_evaluator(self) -> RunEvaluator:
        """Convert the object into a `RunEvaluator` instance."""
