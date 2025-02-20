"""This module contains the evaluator classes for evaluating runs."""

from __future__ import annotations

import asyncio
import inspect
import uuid
from abc import abstractmethod
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Sequence,
    Union,
    cast,
)

from typing_extensions import TypedDict

from langsmith import schemas

try:
    from pydantic.v1 import (  # type: ignore[import]
        BaseModel,
        Field,
        ValidationError,
        validator,
    )
except ImportError:
    from pydantic import (  # type: ignore[assignment]
        BaseModel,
        Field,
        ValidationError,
        validator,
    )

import logging
from functools import wraps

from langsmith.schemas import SCORE_TYPE, VALUE_TYPE, Example, Run

logger = logging.getLogger(__name__)


class Category(TypedDict):
    """A category for categorical feedback."""

    value: Optional[Union[float, int]]
    """The numeric score/ordinal corresponding to this category."""
    label: str
    """The label for this category."""


class FeedbackConfig(TypedDict, total=False):
    """Configuration to define a type of feedback.

    Applied on on the first creation of a feedback_key.
    """

    type: Literal["continuous", "categorical", "freeform"]
    """The type of feedback."""
    min: Optional[Union[float, int]]
    """The minimum permitted value (if continuous type)."""
    max: Optional[Union[float, int]]
    """The maximum value permitted value (if continuous type)."""
    categories: Optional[List[Union[Category, dict]]]


class EvaluationResult(BaseModel):
    """Evaluation result."""

    key: str
    """The aspect, metric name, or label for this evaluation."""
    score: SCORE_TYPE = None
    """The numeric score for this evaluation."""
    value: VALUE_TYPE = None
    """The value for this evaluation, if not numeric."""
    comment: Optional[str] = None
    """An explanation regarding the evaluation."""
    correction: Optional[Dict] = None
    """What the correct value should be, if applicable."""
    evaluator_info: Dict = Field(default_factory=dict)
    """Additional information about the evaluator."""
    feedback_config: Optional[Union[FeedbackConfig, dict]] = None
    """The configuration used to generate this feedback."""
    source_run_id: Optional[Union[uuid.UUID, str]] = None
    """The ID of the trace of the evaluator itself."""
    target_run_id: Optional[Union[uuid.UUID, str]] = None
    """The ID of the trace this evaluation is applied to.
    
    If none provided, the evaluation feedback is applied to the
    root trace being."""
    extra: Optional[Dict] = None
    """Metadata for the evaluator run."""

    class Config:
        """Pydantic model configuration."""

        allow_extra = False

    @validator("value", pre=True)
    def check_value_non_numeric(cls, v, values):
        """Check that the value is not numeric."""
        # If a score isn't provided and the value is numeric
        # it's more likely the user intended use the score field
        if "score" not in values or values["score"] is None:
            if isinstance(v, (int, float)):
                logger.warning(
                    "Numeric values should be provided in"
                    " the 'score' field, not 'value'."
                    f" Got: {v}"
                )
        return v


class EvaluationResults(TypedDict, total=False):
    """Batch evaluation results.

    This makes it easy for your evaluator to return multiple
    metrics at once.
    """

    results: List[EvaluationResult]
    """The evaluation results."""


class RunEvaluator:
    """Evaluator interface class."""

    @abstractmethod
    def evaluate_run(
        self, run: Run, example: Optional[Example] = None
    ) -> Union[EvaluationResult, EvaluationResults]:
        """Evaluate an example."""

    async def aevaluate_run(
        self, run: Run, example: Optional[Example] = None
    ) -> Union[EvaluationResult, EvaluationResults]:
        """Evaluate an example asynchronously."""
        return await asyncio.get_running_loop().run_in_executor(
            None, self.evaluate_run, run, example
        )


_RUNNABLE_OUTPUT = Union[EvaluationResult, EvaluationResults, dict]


class ComparisonEvaluationResult(BaseModel):
    """Feedback scores for the results of comparative evaluations.

    These are generated by functions that compare two or more runs,
    returning a ranking or other feedback.
    """

    key: str
    """The aspect, metric name, or label for this evaluation."""
    scores: Dict[Union[uuid.UUID, str], SCORE_TYPE]
    """The scores for each run in the comparison."""
    source_run_id: Optional[Union[uuid.UUID, str]] = None
    """The ID of the trace of the evaluator itself."""
    comment: Optional[Union[str, Dict[Union[uuid.UUID, str], str]]] = None
    """Comment for the scores. If a string, it's shared across all target runs.
    If a dict, it maps run IDs to individual comments."""


_COMPARISON_OUTPUT = Union[ComparisonEvaluationResult, dict]


class DynamicRunEvaluator(RunEvaluator):
    """A dynamic evaluator that wraps a function and transforms it into a `RunEvaluator`.

    This class is designed to be used with the `@run_evaluator` decorator, allowing
    functions that take a `Run` and an optional `Example` as arguments, and return
    an `EvaluationResult` or `EvaluationResults`, to be used as instances of `RunEvaluator`.

    Attributes:
        func (Callable): The function that is wrapped by this evaluator.
    """  # noqa: E501

    def __init__(
        self,
        func: Callable[
            [Run, Optional[Example]],
            Union[_RUNNABLE_OUTPUT, Awaitable[_RUNNABLE_OUTPUT]],
        ],
        # Async function to be used for async evaluation. Optional
        afunc: Optional[
            Callable[
                [Run, Optional[Example]],
                Awaitable[_RUNNABLE_OUTPUT],
            ]
        ] = None,
    ):
        """Initialize the DynamicRunEvaluator with a given function.

        Args:
            func (Callable): A function that takes a `Run` and an optional `Example` as
            arguments, and returns a dict or `ComparisonEvaluationResult`.
        """
        func = _normalize_evaluator_func(func)
        if afunc:
            afunc = _normalize_evaluator_func(afunc)  # type: ignore[assignment]

        wraps(func)(self)
        from langsmith import run_helpers  # type: ignore

        if afunc is not None:
            self.afunc = run_helpers.ensure_traceable(
                afunc, process_inputs=_serialize_inputs
            )
            self._name = getattr(afunc, "__name__", "DynamicRunEvaluator")
        if inspect.iscoroutinefunction(func):
            if afunc is not None:
                raise TypeError(
                    "Func was provided as a coroutine function, but afunc was "
                    "also provided. If providing both, func should be a regular "
                    "function to avoid ambiguity."
                )
            self.afunc = run_helpers.ensure_traceable(
                func, process_inputs=_serialize_inputs
            )
            self._name = getattr(func, "__name__", "DynamicRunEvaluator")
        else:
            self.func = run_helpers.ensure_traceable(
                cast(Callable[[Run, Optional[Example]], _RUNNABLE_OUTPUT], func),
                process_inputs=_serialize_inputs,
            )
            self._name = getattr(func, "__name__", "DynamicRunEvaluator")

    def _coerce_evaluation_result(
        self,
        result: Union[EvaluationResult, dict],
        source_run_id: uuid.UUID,
        allow_no_key: bool = False,
    ) -> EvaluationResult:
        if isinstance(result, EvaluationResult):
            if not result.source_run_id:
                result.source_run_id = source_run_id
            return result
        try:
            if not result:
                raise ValueError(
                    "Expected an EvaluationResult object, or dict with a metric"
                    f" 'key' and optional 'score'; got empty result: {result}"
                )
            if "key" not in result and allow_no_key:
                result["key"] = self._name
            if all(k not in result for k in ("score", "value", "comment")):
                raise ValueError(
                    "Expected an EvaluationResult object, or dict with a metric"
                    f" 'key' and optional 'score' or categorical 'value'; got {result}"
                )
            return EvaluationResult(**{"source_run_id": source_run_id, **result})
        except ValidationError as e:
            raise ValueError(
                "Expected an EvaluationResult object, or dict with a metric"
                f" 'key' and optional 'score'; got {result}"
            ) from e

    def _coerce_evaluation_results(
        self,
        results: Union[dict, EvaluationResults],
        source_run_id: uuid.UUID,
    ) -> Union[EvaluationResult, EvaluationResults]:
        if "results" in results:
            cp = results.copy()
            cp["results"] = [
                self._coerce_evaluation_result(r, source_run_id=source_run_id)
                for r in results["results"]
            ]
            return EvaluationResults(**cp)

        return self._coerce_evaluation_result(
            cast(dict, results), source_run_id=source_run_id, allow_no_key=True
        )

    def _format_result(
        self,
        result: Union[
            EvaluationResult, EvaluationResults, dict, str, int, bool, float, list
        ],
        source_run_id: uuid.UUID,
    ) -> Union[EvaluationResult, EvaluationResults]:
        if isinstance(result, EvaluationResult):
            if not result.source_run_id:
                result.source_run_id = source_run_id
            return result
        result = _format_evaluator_result(result)
        return self._coerce_evaluation_results(result, source_run_id)

    @property
    def is_async(self) -> bool:
        """Check if the evaluator function is asynchronous.

        Returns:
            bool: True if the evaluator function is asynchronous, False otherwise.
        """
        return hasattr(self, "afunc")

    def evaluate_run(
        self, run: Run, example: Optional[Example] = None
    ) -> Union[EvaluationResult, EvaluationResults]:
        """Evaluate a run using the wrapped function.

        This method directly invokes the wrapped function with the provided arguments.

        Args:
            run (Run): The run to be evaluated.
            example (Optional[Example]): An optional example to be used in the evaluation.

        Returns:
            Union[EvaluationResult, EvaluationResults]: The result of the evaluation.
        """  # noqa: E501
        if not hasattr(self, "func"):
            running_loop = asyncio.get_event_loop()
            if running_loop.is_running():
                raise RuntimeError(
                    "Cannot call `evaluate_run` on an async run evaluator from"
                    " within an running event loop. Use `aevaluate_run` instead."
                )
            else:
                return running_loop.run_until_complete(self.aevaluate_run(run, example))
        source_run_id = uuid.uuid4()
        metadata: Dict[str, Any] = {"target_run_id": run.id}
        if getattr(run, "session_id", None):
            metadata["experiment"] = str(run.session_id)
        result = self.func(
            run,
            example,
            langsmith_extra={"run_id": source_run_id, "metadata": metadata},
        )
        return self._format_result(result, source_run_id)

    async def aevaluate_run(self, run: Run, example: Optional[Example] = None):
        """Evaluate a run asynchronously using the wrapped async function.

        This method directly invokes the wrapped async function with the
            provided arguments.

        Args:
            run (Run): The run to be evaluated.
            example (Optional[Example]): An optional example to be used
                in the evaluation.

        Returns:
            Union[EvaluationResult, EvaluationResults]: The result of the evaluation.
        """
        if not hasattr(self, "afunc"):
            return await super().aevaluate_run(run, example)
        source_run_id = uuid.uuid4()
        metadata: Dict[str, Any] = {"target_run_id": run.id}
        if getattr(run, "session_id", None):
            metadata["experiment"] = str(run.session_id)
        result = await self.afunc(
            run,
            example,
            langsmith_extra={"run_id": source_run_id, "metadata": metadata},
        )
        return self._format_result(result, source_run_id)

    def __call__(
        self, run: Run, example: Optional[Example] = None
    ) -> Union[EvaluationResult, EvaluationResults]:
        """Make the evaluator callable, allowing it to be used like a function.

        This method enables the evaluator instance to be called directly, forwarding the
        call to `evaluate_run`.

        Args:
            run (Run): The run to be evaluated.
            example (Optional[Example]): An optional example to be used in the evaluation.

        Returns:
            Union[EvaluationResult, EvaluationResults]: The result of the evaluation.
        """  # noqa: E501
        return self.evaluate_run(run, example)

    def __repr__(self) -> str:
        """Represent the DynamicRunEvaluator object."""
        return f"<DynamicRunEvaluator {self._name}>"


def run_evaluator(
    func: Callable[
        [Run, Optional[Example]], Union[_RUNNABLE_OUTPUT, Awaitable[_RUNNABLE_OUTPUT]]
    ],
):
    """Create a run evaluator from a function.

    Decorator that transforms a function into a `RunEvaluator`.
    """
    return DynamicRunEvaluator(func)


_MAXSIZE = 10_000


def _maxsize_repr(obj: Any):
    s = repr(obj)
    if len(s) > _MAXSIZE:
        s = s[: _MAXSIZE - 4] + "...)"
    return s


def _serialize_inputs(inputs: dict) -> dict:
    run_truncated = _maxsize_repr(inputs.get("run"))
    example_truncated = _maxsize_repr(inputs.get("example"))
    return {"run": run_truncated, "example": example_truncated}


class DynamicComparisonRunEvaluator:
    """Compare predictions (as traces) from 2 or more runs."""

    def __init__(
        self,
        func: Callable[
            [Sequence[Run], Optional[Example]],
            Union[_COMPARISON_OUTPUT, Awaitable[_COMPARISON_OUTPUT]],
        ],
        # Async function to be used for async evaluation. Optional
        afunc: Optional[
            Callable[
                [Sequence[Run], Optional[Example]],
                Awaitable[_COMPARISON_OUTPUT],
            ]
        ] = None,
    ):
        """Initialize the DynamicRunEvaluator with a given function.

        Args:
            func (Callable): A function that takes a `Run` and an optional `Example` as
            arguments, and returns an `EvaluationResult` or `EvaluationResults`.
        """
        func = _normalize_comparison_evaluator_func(func)
        if afunc:
            afunc = _normalize_comparison_evaluator_func(afunc)  # type: ignore[assignment]

        wraps(func)(self)
        from langsmith import run_helpers  # type: ignore

        if afunc is not None:
            self.afunc = run_helpers.ensure_traceable(
                afunc, process_inputs=_serialize_inputs
            )
            self._name = getattr(afunc, "__name__", "DynamicRunEvaluator")
        if inspect.iscoroutinefunction(func):
            if afunc is not None:
                raise TypeError(
                    "Func was provided as a coroutine function, but afunc was "
                    "also provided. If providing both, func should be a regular "
                    "function to avoid ambiguity."
                )
            self.afunc = run_helpers.ensure_traceable(
                func, process_inputs=_serialize_inputs
            )
            self._name = getattr(func, "__name__", "DynamicRunEvaluator")
        else:
            self.func = run_helpers.ensure_traceable(
                cast(
                    Callable[
                        [Sequence[Run], Optional[Example]],
                        _COMPARISON_OUTPUT,
                    ],
                    func,
                ),
                process_inputs=_serialize_inputs,
            )
            self._name = getattr(func, "__name__", "DynamicRunEvaluator")

    @property
    def is_async(self) -> bool:
        """Check if the evaluator function is asynchronous.

        Returns:
            bool: True if the evaluator function is asynchronous, False otherwise.
        """
        return hasattr(self, "afunc")

    def compare_runs(
        self, runs: Sequence[Run], example: Optional[Example] = None
    ) -> ComparisonEvaluationResult:
        """Compare runs to score preferences.

        Args:
            runs: A list of runs to compare.
            example: An optional example to be used in the evaluation.

        """  # noqa: E501
        if not hasattr(self, "func"):
            running_loop = asyncio.get_event_loop()
            if running_loop.is_running():
                raise RuntimeError(
                    "Cannot call `evaluate_run` on an async run evaluator from"
                    " within an running event loop. Use `aevaluate_run` instead."
                )
            else:
                return running_loop.run_until_complete(
                    self.acompare_runs(runs, example)
                )
        source_run_id = uuid.uuid4()
        tags = self._get_tags(runs)
        # TODO: Add metadata for the "comparison experiment" here
        result = self.func(
            runs,
            example,
            langsmith_extra={"run_id": source_run_id, "tags": tags},
        )
        return self._format_results(result, source_run_id, runs)

    async def acompare_runs(
        self, runs: Sequence[Run], example: Optional[Example] = None
    ) -> ComparisonEvaluationResult:
        """Evaluate a run asynchronously using the wrapped async function.

        This method directly invokes the wrapped async function with the
            provided arguments.

        Args:
            runs (Run): The runs to be evaluated.
            example (Optional[Example]): An optional example to be used
                in the evaluation.

        Returns:
            ComparisonEvaluationResult: The result of the evaluation.
        """
        if not hasattr(self, "afunc"):
            return self.compare_runs(runs, example)
        source_run_id = uuid.uuid4()
        tags = self._get_tags(runs)
        # TODO: Add metadata for the "comparison experiment" here
        result = await self.afunc(
            runs,
            example,
            langsmith_extra={"run_id": source_run_id, "tags": tags},
        )
        return self._format_results(result, source_run_id, runs)

    def __call__(
        self, runs: Sequence[Run], example: Optional[Example] = None
    ) -> ComparisonEvaluationResult:
        """Make the evaluator callable, allowing it to be used like a function.

        This method enables the evaluator instance to be called directly, forwarding the
        call to `evaluate_run`.

        Args:
            run (Run): The run to be evaluated.
            example (Optional[Example]): An optional example to be used in the evaluation.

        Returns:
            ComparisonEvaluationResult: The result of the evaluation.
        """  # noqa: E501
        return self.compare_runs(runs, example)

    def __repr__(self) -> str:
        """Represent the DynamicRunEvaluator object."""
        return f"<DynamicComparisonRunEvaluator {self._name}>"

    @staticmethod
    def _get_tags(runs: Sequence[Run]) -> List[str]:
        """Extract tags from runs."""
        # Add tags to support filtering
        tags = []
        for run in runs:
            tags.append("run:" + str(run.id))
            if getattr(run, "session_id", None):
                tags.append("experiment:" + str(run.session_id))
        return tags

    def _format_results(
        self,
        result: Union[dict, list, ComparisonEvaluationResult],
        source_run_id: uuid.UUID,
        runs: Sequence[Run],
    ) -> ComparisonEvaluationResult:
        if isinstance(result, ComparisonEvaluationResult):
            if not result.source_run_id:
                result.source_run_id = source_run_id
            return result
        elif isinstance(result, list):
            result = {
                "scores": {run.id: score for run, score in zip(runs, result)},
                "key": self._name,
                "source_run_id": source_run_id,
            }
        elif isinstance(result, dict):
            if "key" not in result:
                result["key"] = self._name
        else:
            msg = (
                "Expected 'dict', 'list' or 'ComparisonEvaluationResult' result "
                f"object. Received: {result=}"
            )
            raise ValueError(msg)
        try:
            return ComparisonEvaluationResult(
                **{"source_run_id": source_run_id, **result}
            )
        except ValidationError as e:
            raise ValueError(
                f"Expected a dictionary with a 'key' and dictionary of scores mapping"
                "run IDs to numeric scores, or ComparisonEvaluationResult object,"
                f" got {result}"
            ) from e


def comparison_evaluator(
    func: Callable[
        [Sequence[Run], Optional[Example]],
        Union[_COMPARISON_OUTPUT, Awaitable[_COMPARISON_OUTPUT]],
    ],
) -> DynamicComparisonRunEvaluator:
    """Create a comaprison evaluator from a function."""
    return DynamicComparisonRunEvaluator(func)


def _normalize_evaluator_func(
    func: Callable,
) -> Union[
    Callable[[Run, Optional[Example]], _RUNNABLE_OUTPUT],
    Callable[[Run, Optional[Example]], Awaitable[_RUNNABLE_OUTPUT]],
]:
    supported_args = (
        "run",
        "example",
        "inputs",
        "outputs",
        "reference_outputs",
        "attachments",
    )
    sig = inspect.signature(func)
    all_args = [pname for pname, _ in sig.parameters.items()]
    args_with_defaults = [
        pname
        for pname, p in sig.parameters.items()
        if p.default is not inspect.Parameter.empty
    ]
    if not all_args or (
        not all(
            pname in supported_args or pname in args_with_defaults for pname in all_args
        )
        and len([a for a in all_args if a not in args_with_defaults]) != 2
    ):
        msg = (
            f"Invalid evaluator function. Must have at least one "
            f"argument. Supported arguments are {supported_args}. Please "
            f"see https://docs.smith.langchain.com/evaluation/how_to_guides/evaluation/evaluate_llm_application#use-custom-evaluators"
            # noqa: E501
        )
        raise ValueError(msg)
    # For backwards compatibility we assume custom arg names are Run and Example
    # types, respectively.
    elif not all(
        pname in supported_args or pname in args_with_defaults for pname in all_args
    ) or all_args == [
        "run",
        "example",
    ]:
        if inspect.iscoroutinefunction(func):

            async def awrapper(
                run: Run, example: Optional[Example]
            ) -> _RUNNABLE_OUTPUT:
                args = []
                kwargs = {}
                for i, (param_name, param) in enumerate(sig.parameters.items()):
                    if param.kind == param.POSITIONAL_ONLY:
                        args.append(run if i == 0 else example)
                    else:
                        kwargs[param_name] = run if i == 0 else example
                return await func(*args, **kwargs)  # type: ignore

            awrapper.__name__ = (
                getattr(func, "__name__")
                if hasattr(func, "__name__")
                else awrapper.__name__
            )
            return awrapper  # type: ignore[return-value]

        else:

            def wrapper(run: Run, example: Optional[Example]) -> _RUNNABLE_OUTPUT:
                args = []
                kwargs = {}
                for i, (param_name, param) in enumerate(sig.parameters.items()):
                    if param.kind == param.POSITIONAL_ONLY:
                        args.append(run if i == 0 else example)
                    else:
                        kwargs[param_name] = run if i == 0 else example
                return func(*args, **kwargs)  # type: ignore

            wrapper.__name__ = (
                getattr(func, "__name__")
                if hasattr(func, "__name__")
                else wrapper.__name__
            )
            return wrapper  # type: ignore[return-value]
    else:
        if inspect.iscoroutinefunction(func):

            async def awrapper(
                run: Run, example: Optional[Example]
            ) -> _RUNNABLE_OUTPUT:
                arg_map = {
                    "run": run,
                    "example": example,
                    "inputs": example.inputs if example else {},
                    "outputs": run.outputs or {},
                    "attachments": example.attachments or {} if example else {},
                    "reference_outputs": example.outputs or {} if example else {},
                }
                kwargs = {}
                args = []
                for param_name, param in sig.parameters.items():
                    # Could have params with defaults that are not in the arg map
                    if param_name in arg_map:
                        if param.kind in (
                            param.POSITIONAL_OR_KEYWORD,
                            param.POSITIONAL_ONLY,
                        ):
                            args.append(arg_map[param_name])
                        else:
                            kwargs[param_name] = arg_map[param_name]
                return await func(*args, **kwargs)

            awrapper.__name__ = (
                getattr(func, "__name__")
                if hasattr(func, "__name__")
                else awrapper.__name__
            )
            return awrapper  # type: ignore[return-value]

        else:

            def wrapper(run: Run, example: Example) -> _RUNNABLE_OUTPUT:
                arg_map = {
                    "run": run,
                    "example": example,
                    "inputs": example.inputs if example else {},
                    "outputs": run.outputs or {},
                    "attachments": example.attachments or {},
                    "reference_outputs": example.outputs or {} if example else {},
                }
                kwargs = {}
                args = []
                for param_name, param in sig.parameters.items():
                    # Could have params with defaults that are not in the arg map
                    if param_name in arg_map:
                        if param.kind in (
                            param.POSITIONAL_OR_KEYWORD,
                            param.POSITIONAL_ONLY,
                        ):
                            args.append(arg_map[param_name])
                        else:
                            kwargs[param_name] = arg_map[param_name]

                return func(*args, **kwargs)

            wrapper.__name__ = (
                getattr(func, "__name__")
                if hasattr(func, "__name__")
                else wrapper.__name__
            )
            return wrapper  # type: ignore[return-value]


def _normalize_comparison_evaluator_func(
    func: Callable,
) -> Union[
    Callable[[Sequence[Run], Optional[Example]], _COMPARISON_OUTPUT],
    Callable[[Sequence[Run], Optional[Example]], Awaitable[_COMPARISON_OUTPUT]],
]:
    supported_args = ("runs", "example", "inputs", "outputs", "reference_outputs")
    sig = inspect.signature(func)
    all_args = [pname for pname, _ in sig.parameters.items()]
    args_with_defaults = [
        pname
        for pname, p in sig.parameters.items()
        if p.default is not inspect.Parameter.empty
    ]
    if not all_args or (
        not all(
            pname in supported_args or pname in args_with_defaults for pname in all_args
        )
        and len([a for a in all_args if a not in args_with_defaults]) != 2
    ):
        msg = (
            f"Invalid evaluator function. Must have at least one "
            f"argument. Supported arguments are {supported_args}. Please "
            f"see https://docs.smith.langchain.com/evaluation/how_to_guides/evaluation/evaluate_llm_application#use-custom-evaluators"
            # noqa: E501
        )
        raise ValueError(msg)
    # For backwards compatibility we assume custom arg names are List[Run] and
    # List[Example] types, respectively.
    elif not all(
        pname in supported_args or pname in args_with_defaults for pname in all_args
    ) or all_args == [
        "runs",
        "example",
    ]:
        if inspect.iscoroutinefunction(func):

            async def awrapper(
                run: Run, example: Optional[Example]
            ) -> _RUNNABLE_OUTPUT:
                args = []
                kwargs = {}
                for i, (param_name, param) in enumerate(sig.parameters.items()):
                    if param.kind == param.POSITIONAL_ONLY:
                        args.append(run if i == 0 else example)
                    else:
                        kwargs[param_name] = run if i == 0 else example
                return await func(*args, **kwargs)  # type: ignore

            awrapper.__name__ = (
                getattr(func, "__name__")
                if hasattr(func, "__name__")
                else awrapper.__name__
            )
            return awrapper  # type: ignore[return-value]

        else:

            def wrapper(run: Run, example: Optional[Example]) -> _RUNNABLE_OUTPUT:
                args = []
                kwargs = {}
                for i, (param_name, param) in enumerate(sig.parameters.items()):
                    if param.kind == param.POSITIONAL_ONLY:
                        args.append(run if i == 0 else example)
                    else:
                        kwargs[param_name] = run if i == 0 else example
                return func(*args, **kwargs)  # type: ignore

            wrapper.__name__ = (
                getattr(func, "__name__")
                if hasattr(func, "__name__")
                else wrapper.__name__
            )
            return wrapper  # type: ignore[return-value]
    else:
        if inspect.iscoroutinefunction(func):

            async def awrapper(
                runs: Sequence[Run], example: Optional[Example]
            ) -> _COMPARISON_OUTPUT:
                arg_map = {
                    "runs": runs,
                    "example": example,
                    "inputs": example.inputs if example else {},
                    "outputs": [run.outputs or {} for run in runs],
                    "reference_outputs": example.outputs or {} if example else {},
                }
                kwargs = {}
                args = []
                for param_name, param in sig.parameters.items():
                    # Could have params with defaults that are not in the arg map
                    if param_name in arg_map:
                        if param.kind in (
                            param.POSITIONAL_OR_KEYWORD,
                            param.POSITIONAL_ONLY,
                        ):
                            args.append(arg_map[param_name])
                        else:
                            kwargs[param_name] = arg_map[param_name]
                return await func(*args, **kwargs)

            awrapper.__name__ = (
                getattr(func, "__name__")
                if hasattr(func, "__name__")
                else awrapper.__name__
            )
            return awrapper  # type: ignore[return-value]

        else:

            def wrapper(runs: Sequence[Run], example: Example) -> _COMPARISON_OUTPUT:
                arg_map = {
                    "runs": runs,
                    "example": example,
                    "inputs": example.inputs if example else {},
                    "outputs": [run.outputs or {} for run in runs],
                    "reference_outputs": example.outputs or {} if example else {},
                }
                args = (arg_map[arg] for arg in all_args)
                kwargs = {}
                args = []
                for param_name, param in sig.parameters.items():
                    # Could have params with defaults that are not in the arg map
                    if param_name in arg_map:
                        if param.kind in (
                            param.POSITIONAL_OR_KEYWORD,
                            param.POSITIONAL_ONLY,
                        ):
                            args.append(arg_map[param_name])
                        else:
                            kwargs[param_name] = arg_map[param_name]

                return func(*args, **kwargs)

            wrapper.__name__ = (
                getattr(func, "__name__")
                if hasattr(func, "__name__")
                else wrapper.__name__
            )
            return wrapper  # type: ignore[return-value]


def _format_evaluator_result(
    result: Union[EvaluationResults, dict, str, int, bool, float, list],
) -> Union[EvaluationResults, dict]:
    if isinstance(result, (bool, float, int)):
        result = {"score": result}
    elif not result:
        raise ValueError(
            f"Expected a non-empty dict, str, bool, int, float, list, "
            f"EvaluationResult, or EvaluationResults. Got {result}"
        )
    elif isinstance(result, list):
        if not all(isinstance(x, dict) for x in result):
            raise ValueError(
                f"Expected a list of dicts or EvaluationResults. Received {result}."
            )
        result = {"results": result}  # type: ignore[misc]
    elif isinstance(result, str):
        result = {"value": result}
    elif isinstance(result, dict):
        pass
    else:
        raise ValueError(
            f"Expected a dict, str, bool, int, float, list, EvaluationResult, or "
            f"EvaluationResults. Got {result}"
        )
    return result


SUMMARY_EVALUATOR_T = Union[
    Callable[
        [Sequence[schemas.Run], Sequence[schemas.Example]],
        Union[EvaluationResult, EvaluationResults],
    ],
    Callable[
        [List[schemas.Run], List[schemas.Example]],
        Union[EvaluationResult, EvaluationResults],
    ],
]


def _normalize_summary_evaluator(func: Callable) -> SUMMARY_EVALUATOR_T:
    supported_args = ("runs", "examples", "inputs", "outputs", "reference_outputs")
    sig = inspect.signature(func)
    all_args = [pname for pname, p in sig.parameters.items()]
    args_with_defaults = [
        pname
        for pname, p in sig.parameters.items()
        if p.default is not inspect.Parameter.empty
    ]
    if not all_args or (
        not all(
            pname in supported_args or pname in args_with_defaults for pname in all_args
        )
        and len([a for a in all_args if a not in args_with_defaults]) != 2
    ):
        msg = (
            f"Invalid evaluator function. Must have at least one "
            f"argument. Supported arguments are {supported_args}."
        )
        if all_args:
            msg += f" Received arguments {all_args}."
        raise ValueError(msg)
    # For backwards compatibility we assume custom arg names are Sequence[Run] and
    # Sequence[Example] types, respectively.
    elif not all(pname in supported_args for pname in all_args) or all_args == [
        "runs",
        "examples",
    ]:
        return func
    else:

        def wrapper(
            runs: Sequence[schemas.Run], examples: Sequence[schemas.Example]
        ) -> Union[EvaluationResult, EvaluationResults]:
            arg_map = {
                "runs": runs,
                "examples": examples,
                "inputs": [example.inputs for example in examples],
                "outputs": [run.outputs or {} for run in runs],
                "reference_outputs": [example.outputs or {} for example in examples],
            }
            kwargs = {}
            args = []
            for param_name, param in sig.parameters.items():
                # Could have params with defaults that are not in the arg map
                if param_name in arg_map:
                    if param.kind in (
                        param.POSITIONAL_OR_KEYWORD,
                        param.POSITIONAL_ONLY,
                    ):
                        args.append(arg_map[param_name])
                    else:
                        kwargs[param_name] = arg_map[param_name]

            return func(*args, **kwargs)  # type: ignore[return-value]

        wrapper.__name__ = (
            getattr(func, "__name__") if hasattr(func, "__name__") else wrapper.__name__
        )
        return wrapper  # type: ignore[return-value]
