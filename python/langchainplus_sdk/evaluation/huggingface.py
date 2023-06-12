"""Huggingface 'Evaluate' metrics connections."""
from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional

from pydantic import BaseModel, Field

from langchainplus_sdk.evaluation.evaluator import EvaluationResult, RunEvaluator
from langchainplus_sdk.schemas import SCORE_TYPE, Example, Run

if TYPE_CHECKING:
    import evaluate  # type: ignore[import]


def lazy_load_evaluate():
    try:
        import evaluate
    except ImportError:
        raise ImportError(
            "Huggingface 'evaluate' module not installed. "
            "Run 'pip install langchainplus-sdk[huggingface]' to install."
        )
    return evaluate


class HuggingFaceScoreParser:
    @abstractmethod
    def parse(self, grading_results: Dict[str, Any]) -> SCORE_TYPE:
        """Maps the Run and Optional[Example] to a dictionary"""


class HuggingFaceEvalutor(RunEvaluator, BaseModel):
    """Grades the run's string input, output, and optional answer."""

    path: str = Field(..., description="The metric name or path to the module.")
    score_key: str = Field(
        ...,
        description="The key in the HF evaluation module result to"
        " map to the feedback score.",
    )
    prediction_key: str = Field(
        default="output", description="The key to use for the prediction input."
    )
    reference_key: Optional[str] = Field(
        default="output", description="The key to use for the reference input."
    )
    compute_kwargs: Optional[dict] = Field(
        default=None, description="Kwargs to pass to the evaluator when calling."
    )
    evaluation_module: evaluate.EvaluationModule = Field(
        ..., description="The HF module to use for evaluation.", export=False
    )

    class Config:
        """Pydantic model configuration."""

        arbitrary_types_allowed = True

    @classmethod
    def from_path(
        cls, path: str, loading_kwargs: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> HuggingFaceEvalutor:
        """Create an evaluator from a path."""
        global evaluate
        evaluate = lazy_load_evaluate()
        cls.update_forward_refs()
        module = evaluate.load(path, **loading_kwargs or {})
        return cls(path=path, evaluation_module=module, **kwargs)

    def evaluate_run(
        self, run: Run, example: Optional[Example] = None
    ) -> EvaluationResult:
        """Evaluate a single run."""
        if run.outputs is None:
            raise ValueError("Run outputs cannot be None.")
        predictions = [run.outputs[self.prediction_key]]
        references = (
            [example.outputs[self.reference_key]]
            if example is not None
            and example.outputs is not None
            and self.reference_key is not None
            else None
        )
        grading_results = self.evaluation_module.compute(
            **self.compute_kwargs, predictions=predictions, references=references
        )
        score = grading_results[self.score_key]
        if isinstance(score, list):  # If the metric is instance-level
            score = score[0]
        if grading_results is None:
            raise ValueError("Grading results cannot be None.")
        return EvaluationResult(key=self.path, score=score, value=grading_results)
