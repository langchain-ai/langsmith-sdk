"""V2 Evaluation Interface."""

from __future__ import annotations

import collections
import concurrent.futures as cf
import datetime
import functools
import itertools
import logging
import threading
import uuid
from contextvars import copy_context
from typing import (
    Callable,
    DefaultDict,
    Dict,
    Generator,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast,
)

from requests import HTTPError
from typing_extensions import TypedDict

import langsmith
from langsmith import beta as ls_beta
from langsmith import env as ls_env
from langsmith import run_helpers as rh
from langsmith import run_trees, schemas
from langsmith import utils as ls_utils
from langsmith.evaluation.evaluator import (
    EvaluationResult,
    EvaluationResults,
    RunEvaluator,
    run_evaluator,
)
from langsmith.evaluation.integrations import LangChainStringEvaluator

logger = logging.getLogger(__name__)

TARGET_T = Callable[[dict], dict]
# Data format: dataset-name, dataset_id, or examples
DATA_T = Union[str, uuid.UUID, Iterable[schemas.Example]]
# Summary evaluator runs over the whole dataset
# and reports aggregate metric(s)
SUMMARY_EVALUATOR_T = Callable[
    [Sequence[schemas.Run], Sequence[schemas.Example]],
    Union[EvaluationResult, EvaluationResults],
]
# Row-level evaluator
EVALUATOR_T = Union[
    RunEvaluator,
    Callable[[schemas.Run, Optional[schemas.Example]], EvaluationResult],
]


@ls_beta.warn_beta
def evaluate(
    target: TARGET_T,
    /,
    data: DATA_T,
    evaluators: Optional[Sequence[EVALUATOR_T]] = None,
    summary_evaluators: Optional[Sequence[SUMMARY_EVALUATOR_T]] = None,
    metadata: Optional[dict] = None,
    experiment_prefix: Optional[str] = None,
    max_concurrency: Optional[int] = None,
    client: Optional[langsmith.Client] = None,
    blocking: bool = True,
) -> ExperimentResults:
    r"""Evaluate a target system or function on a given dataset.

    Args:
        target (TARGET_T): The target system or function to evaluate.
        data (DATA_T): The dataset to evaluate on. Can be a dataset name, a list of
            examples, or a generator of examples.
        evaluators (Optional[Sequence[EVALUATOR_T]]): A list of evaluators to run
            on each example. Defaults to None.
        summary_evaluators (Optional[Sequence[SUMMARY_EVALUATOR_T]]): A list of summary
            evaluators to run on the entire dataset. Defaults to None.
        metadata (Optional[dict]): Metadata to attach to the experiment.
            Defaults to None.
        experiment_prefix (Optional[str]): A prefix to provide for your experiment name.
            Defaults to None.
        max_concurrency (Optional[int]): The maximum number of concurrent
            evaluations to run. Defaults to None.
        client (Optional[langsmith.Client]): The LangSmith client to use.
            Defaults to None.
        blocking (bool): Whether to block until the evaluation is complete.
            Defaults to True.

    Returns:
        ExperimentResults: The results of the evaluation.

    Examples:
        Prepare the dataset:

        >>> from typing import Sequence
        >>> from langsmith import Client
        >>> from langsmith.evaluation import evaluate
        >>> from langsmith.schemas import Example, Run
        >>> client = Client()
        >>> client.clone_public_dataset(
        ...     "https://smith.langchain.com/public/419dcab2-1d66-4b94-8901-0357ead390df/d"
        ... )
        >>> dataset_name = "Evaluate Examples"

        Basic usage:

        >>> def accuracy(run: Run, example: Example):
        ...     # Row-level evaluator for accuracy.
        ...     pred = run.outputs["output"]
        ...     expected = example.outputs["answer"]
        ...     return {"score": expected.lower() == pred.lower()}
        >>> def precision(runs: Sequence[Run], examples: Sequence[Example]):
        ...     # Experiment-level evaluator for precision.
        ...     # TP / (TP + FP)
        ...     predictions = [run.outputs["output"].lower() for run in runs]
        ...     expected = [example.outputs["answer"].lower() for example in examples]
        ...     # yes and no are the only possible answers
        ...     tp = sum([p == e for p, e in zip(predictions, expected) if p == "yes"])
        ...     fp = sum([p == "yes" and e == "no" for p, e in zip(predictions, expected)])
        ...     return {"score": tp / (tp + fp)}
        >>> def predict(inputs: dict) -> dict:
        ...     # This can be any function or just an API call to your app.
        ...     return {"output": "Yes"}
        >>> results = evaluate(
        ...     predict,
        ...     data=dataset_name,
        ...     evaluators=[accuracy],
        ...     summary_evaluators=[precision],
        ...     metadata={
        ...         "my-prompt-version": "abcd-1234",
        ...     },
        ... )  # doctest: +ELLIPSIS
        View the evaluation results for experiment:...

        Evaluating over only a subset of the examples

        >>> experiment_name = results.experiment_name
        >>> examples = client.list_examples(dataset_name=dataset_name, limit=5)
        >>> results = evaluate(
        ...     predict,
        ...     data=examples,
        ...     evaluators=[accuracy],
        ...     summary_evaluators=[precision],
        ...     experiment_prefix="My Experiment",
        ... )  # doctest: +ELLIPSIS
        View the evaluation results for experiment:...

        Streaming each prediction to more easily + eagerly debug.

        >>> results = evaluate(
        ...     predict,
        ...     data=dataset_name,
        ...     evaluators=[accuracy],
        ...     summary_evaluators=[precision],
        ...     blocking=False,
        ... )  # doctest: +ELLIPSIS
        View the evaluation results for experiment:...
        >>> for i, result in enumerate(results):  # doctest: +ELLIPSIS
        ...     pass

        Using the `evaluate` API with an off-the-shelf LangChain evaluator:

        >>> from langsmith.evaluation import LangChainStringEvaluator
        >>> def prepare_criteria_data(run: Run, example: Example):
        ...     return {
        ...         "prediction": run.outputs["output"],
        ...         "reference": example.outputs["answer"],
        ...         "input": str(example.inputs),
        ...     }
        >>> results = evaluate(
        ...     predict,
        ...     data=dataset_name,
        ...     evaluators=[
        ...         accuracy,
        ...         LangChainStringEvaluator("embedding_distance"),
        ...         LangChainStringEvaluator(
        ...             "labeled_criteria",
        ...             config={
        ...                 "criteria": {
        ...                     "usefulness": "The prediction is useful if it is correct"
        ...                     " and/or asks a useful followup question."
        ...                 },
        ...             },
        ...             prepare_data=prepare_criteria_data,
        ...         ),
        ...     ],
        ...     summary_evaluators=[precision],
        ... )  # doctest: +ELLIPSIS
        View the evaluation results for experiment:...

        Evaluating a LangChain object:

        >>> from langchain_core.runnables import chain as as_runnable
        >>> @as_runnable
        ... def nested_predict(inputs):
        ...     return {"output": "Yes"}
        >>> @as_runnable
        ... def lc_predict(inputs):
        ...     return nested_predict.invoke(inputs)
        >>> results = evaluate(
        ...     lc_predict.invoke,
        ...     data=dataset_name,
        ...     evaluators=[accuracy],
        ...     summary_evaluators=[precision],
        ... )  # doctest: +ELLIPSIS
        View the evaluation results for experiment:...
    """  # noqa: E501
    return _evaluate(
        target,
        data=data,
        evaluators=evaluators,
        summary_evaluators=summary_evaluators,
        metadata=metadata,
        experiment_prefix=experiment_prefix,
        max_concurrency=max_concurrency,
        client=client,
        blocking=blocking,
    )


@ls_beta.warn_beta
def evaluate_existing(
    experiment: Union[str, uuid.UUID],
    /,
    evaluators: Optional[Sequence[EVALUATOR_T]] = None,
    summary_evaluators: Optional[Sequence[SUMMARY_EVALUATOR_T]] = None,
    metadata: Optional[dict] = None,
    max_concurrency: Optional[int] = None,
    client: Optional[langsmith.Client] = None,
    load_nested: bool = False,
    blocking: bool = True,
) -> ExperimentResults:
    r"""Evaluate existing experiment runs.

    Args:
        experiment (Union[str, uuid.UUID]): The identifier of the experiment to evaluate.
        data (DATA_T): The data to use for evaluation.
        evaluators (Optional[Sequence[EVALUATOR_T]]): Optional sequence of evaluators to use for individual run evaluation.
        summary_evaluators (Optional[Sequence[SUMMARY_EVALUATOR_T]]): Optional sequence of evaluators
            to apply over the entire dataset.
        metadata (Optional[dict]): Optional metadata to include in the evaluation results.
        max_concurrency (Optional[int]): Optional maximum number of concurrent evaluations.
        client (Optional[langsmith.Client]): Optional Langsmith client to use for evaluation.
        load_nested: Whether to load all child runs for the experiment.
            Default is to only load the top-level root runs.
        blocking (bool): Whether to block until evaluation is complete.

    Returns:
        ExperimentResults: The evaluation results.

    Examples:
        >>> from langsmith.evaluation import evaluate, evaluate_existing
        >>> dataset_name = "Evaluate Examples"
        >>> def predict(inputs: dict) -> dict:
        ...     # This can be any function or just an API call to your app.
        ...     return {"output": "Yes"}
        >>> # First run inference on the dataset
        ... results = evaluate(
        ...     predict,
        ...     data=dataset_name,
        ... )  # doctest: +ELLIPSIS
        View the evaluation results for experiment:...
        >>> # Then apply evaluators to the experiment
        ... def accuracy(run: Run, example: Example):
        ...     # Row-level evaluator for accuracy.
        ...     pred = run.outputs["output"]
        ...     expected = example.outputs["answer"]
        ...     return {"score": expected.lower() == pred.lower()}
        >>> def precision(runs: Sequence[Run], examples: Sequence[Example]):
        ...     # Experiment-level evaluator for precision.
        ...     # TP / (TP + FP)
        ...     predictions = [run.outputs["output"].lower() for run in runs]
        ...     expected = [example.outputs["answer"].lower() for example in examples]
        ...     # yes and no are the only possible answers
        ...     tp = sum([p == e for p, e in zip(predictions, expected) if p == "yes"])
        ...     fp = sum([p == "yes" and e == "no" for p, e in zip(predictions, expected)])
        ...     return {"score": tp / (tp + fp)}
        >>> experiment_name = (
        ...     results.experiment_name
        ... )  # Can use the returned experiment name
        >>> experiment_name = "My Experiment:64e6e91"  # Or manually specify
        >>> results = evaluate_existing(
        ...     experiment_name,
        ...     summary_evaluators=[precision],
        ... )  # doctest: +ELLIPSIS
        View the evaluation results for experiment:...
    """  # noqa: E501
    client = client or langsmith.Client()
    project = _load_experiment(experiment, client)
    runs = _load_traces(experiment, client, load_nested=load_nested)
    data = list(
        client.list_examples(
            dataset_id=project.reference_dataset_id,
            as_of=project.metadata.get("dataset_version"),
        )
    )
    runs = sorted(runs, key=lambda r: str(r.reference_example_id))
    data = sorted(data, key=lambda d: str(d.id))
    return _evaluate(
        runs,
        data=data,
        evaluators=evaluators,
        summary_evaluators=summary_evaluators,
        metadata=metadata,
        max_concurrency=max_concurrency,
        client=client,
        blocking=blocking,
    )


class ExperimentResultRow(TypedDict):
    run: schemas.Run
    example: schemas.Example
    evaluation_results: EvaluationResults


class ExperimentResults:
    """Represents the results of an evaluate() call.

    This class provides an iterator interface to iterate over the experiment results
    as they become available. It also provides methods to access the experiment name,
    the number of results, and to wait for the results to be processed.

    Methods:
        experiment_name() -> str: Returns the name of the experiment.
        wait() -> None: Waits for the experiment data to be processed.
    """

    def __init__(
        self,
        experiment_manager: _ExperimentManager,
    ):
        self._manager = experiment_manager
        self._results: List[ExperimentResultRow] = []
        self._lock = threading.RLock()
        self._thread = threading.Thread(
            target=lambda: self._process_data(self._manager)
        )
        self._thread.start()

    @property
    def experiment_name(self) -> str:
        return self._manager.experiment_name

    def __iter__(self) -> Iterator[ExperimentResultRow]:
        processed_count = 0
        while True:
            with self._lock:
                if processed_count < len(self._results):
                    yield self._results[processed_count]
                    processed_count += 1
                elif not self._thread.is_alive():
                    break

    def _process_data(self, manager: _ExperimentManager) -> None:
        tqdm = _load_tqdm()
        results = manager.get_results()
        for item in tqdm(results):
            with self._lock:
                self._results.append(item)
        summary_scores = manager.get_summary_scores()
        with self._lock:
            self._summary_results = summary_scores

    def __len__(self) -> int:
        return len(self._results)

    def __repr__(self) -> str:
        return f"<ExperimentResults {self.experiment_name}>"

    def wait(self) -> None:
        """Wait for the evaluation runner to complete.

        This method blocks the current thread until the evaluation runner has
        finished its execution.
        """
        self._thread.join()


## Private API


def _is_callable(target: Union[TARGET_T, Iterable[schemas.Run]]) -> bool:
    return callable(target) or (hasattr(target, "invoke") and callable(target.invoke))


def _evaluate(
    target: Union[TARGET_T, Iterable[schemas.Run]],
    /,
    data: DATA_T,
    evaluators: Optional[Sequence[EVALUATOR_T]] = None,
    summary_evaluators: Optional[Sequence[SUMMARY_EVALUATOR_T]] = None,
    metadata: Optional[dict] = None,
    experiment_prefix: Optional[str] = None,
    max_concurrency: Optional[int] = None,
    client: Optional[langsmith.Client] = None,
    blocking: bool = True,
    experiment: Optional[schemas.TracerSession] = None,
) -> ExperimentResults:
    # Initialize the experiment manager.
    manager = _ExperimentManager(
        data,
        client=client,
        metadata=metadata,
        experiment_prefix=experiment_prefix,
        experiment=experiment,
        # If provided, we don't need to create a new experiment.
        runs=None if _is_callable(target) else cast(Iterable[schemas.Run], target),
        # Create or resolve the experiment.
    ).start()
    if _is_callable(target):
        # Add predictions to the experiment.
        manager = manager.with_predictions(
            cast(TARGET_T, target), max_concurrency=max_concurrency
        )
    if evaluators:
        # Apply evaluators to the predictions.
        manager = manager.with_evaluators(evaluators, max_concurrency=max_concurrency)
    if summary_evaluators:
        # Apply the experiment-level summary evaluators.
        manager = manager.with_summary_evaluators(summary_evaluators)
    # Start consuming the results.
    results = ExperimentResults(manager)
    if blocking:
        # Wait for the evaluation to complete.
        results.wait()
    return results


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def _load_experiment(
    project: Union[str, uuid.UUID], client: langsmith.Client
) -> schemas.TracerSession:
    if isinstance(project, uuid.UUID) or _is_uuid(project):
        return client.read_project(project_id=project)
    return client.read_project(project_name=project)


def _load_traces(
    project: Union[str, uuid.UUID], client: langsmith.Client, load_nested: bool = False
) -> List[schemas.Run]:
    """Load nested traces for a given project."""
    execution_order = None if load_nested else 1
    if isinstance(project, uuid.UUID) or _is_uuid(project):
        runs = client.list_runs(project_id=project, execution_order=execution_order)
    else:
        runs = client.list_runs(project_name=project, execution_order=execution_order)
    if not load_nested:
        return list(runs)

    treemap: DefaultDict[uuid.UUID, List[schemas.Run]] = collections.defaultdict(list)
    results = []
    all_runs = {}
    for run in runs:
        if run.parent_run_id is not None:
            treemap[run.parent_run_id].append(run)
        else:
            results.append(run)
        all_runs[run.id] = run
    for run_id, child_runs in treemap.items():
        all_runs[run_id].child_runs = sorted(child_runs, key=lambda r: r.dotted_order)
    return results


def _load_tqdm() -> Callable[[Iterable], Iterable]:
    try:
        from tqdm.auto import tqdm
    except ImportError:
        return lambda x: x
    return tqdm


class _ExperimentManager:
    """Manage the execution of experiments.

    Supports lazily running predictions and evaluations in parallel to facilitate
    result streaming and early debugging.

    Args:
        data (DATA_T): The data used for the experiment. Can be a dataset name or ID OR
            a generator of examples.
        runs (Optional[Iterable[schemas.Run]]): The runs associated with the experiment
            predictions.
        experiment (Optional[schemas.TracerSession]): The tracer session
            associated with the experiment.
        experiment_prefix (Optional[str]): The prefix for the experiment name.
        metadata (Optional[dict]): Additional metadata for the experiment.
        client (Optional[langsmith.Client]): The Langsmith client used for
             the experiment.
        evaluation_results (Optional[Iterable[EvaluationResults]]): The evaluation
            sresults for the experiment.
        summary_results (Optional[Iterable[EvaluationResults]]): The aggregate results
            for the experiment.
    """

    def __init__(
        self,
        data: DATA_T,
        /,
        metadata: Optional[dict] = None,
        experiment_prefix: Optional[str] = None,
        runs: Optional[Iterable[schemas.Run]] = None,
        experiment: Optional[schemas.TracerSession] = None,
        client: Optional[langsmith.Client] = None,
        evaluation_results: Optional[Iterable[EvaluationResults]] = None,
        summary_results: Optional[Iterable[EvaluationResults]] = None,
    ):
        self.client = client or langsmith.Client()
        # If we've already created or started the experiment,
        # use that name.
        experiment_name, experiment, runs = _resolve_experiment_name(
            experiment,
            experiment_prefix,
            runs,
            self.client,
        )
        self.experiment_name = experiment_name
        self._experiment = experiment
        self._runs = runs
        metadata = metadata or {}
        if not metadata.get("revision_id"):
            metadata = {
                "revision_id": ls_env.get_langchain_env_var_metadata().get(
                    "revision_id"
                ),
                **metadata,
            }
        self._metadata = metadata or {}
        self._data = data
        self._examples: Optional[Iterable[schemas.Example]] = None
        self._evaluation_results = evaluation_results
        self._summary_results = summary_results

    @property
    def examples(self) -> Iterable[schemas.Example]:
        if self._examples is None:
            self._examples = _resolve_data(self._data, client=self.client)
        self._examples, examples_iter = itertools.tee(self._examples)
        return examples_iter

    @property
    def evaluation_results(self) -> Iterable[EvaluationResults]:
        if self._evaluation_results is None:
            return [{"results": []} for _ in self.examples]
        return self._evaluation_results

    @property
    def runs(self) -> Iterable[schemas.Run]:
        if self._runs is None:
            raise ValueError(
                "Runs not provided in this experiment." " Please predict first."
            )
        self._runs, runs_iter = itertools.tee(self._runs)
        return runs_iter

    def start(self) -> _ExperimentManager:
        first_example = next(itertools.islice(self.examples, 1))
        if self._experiment is None:
            try:
                project_metadata = self._get_experiment_metadata()
                project = self.client.create_project(
                    self.experiment_name,
                    reference_dataset_id=first_example.dataset_id,
                    metadata=project_metadata,
                )
            except (HTTPError, ValueError, ls_utils.LangSmithError) as e:
                if "already exists " not in str(e):
                    raise e
                raise ValueError(
                    # TODO: Better error
                    f"Experiment {self.experiment_name} already exists."
                    " Please use a different name."
                )
        else:
            project = self._experiment
        if project.url:
            # TODO: Make this a public API
            project_url = project.url.split("?")[0]
            dataset_id = first_example.dataset_id
            base_url = project_url.split("/projects/p/")[0]
            comparison_url = (
                f"{base_url}/datasets/{dataset_id}/compare?"
                f"selectedSessions={project.id}"
            )
            print(  # noqa: T201
                f"View the evaluation results for experiment: '{self.experiment_name}'"
                f" at:\n{comparison_url}\n\n"
            )
        else:
            # HACKHACK
            print("Starting evaluation of experiment: %s", self.experiment_name)
        return _ExperimentManager(
            self.examples,
            experiment=project,
            metadata=self._metadata,
            client=self.client,
            runs=self._runs,
            evaluation_results=self._evaluation_results,
        )

    def with_predictions(
        self,
        target: TARGET_T,
        /,
        max_concurrency: Optional[int] = None,
    ) -> _ExperimentManager:
        """Lazily apply the target function to the experiment."""
        context = copy_context()
        _experiment_results = context.run(
            self._predict, target, max_concurrency=max_concurrency
        )
        r1, r2 = itertools.tee(_experiment_results, 2)
        return _ExperimentManager(
            (pred["example"] for pred in r1),
            experiment=self._experiment,
            metadata=self._metadata,
            client=self.client,
            runs=(pred["run"] for pred in r2),
            # TODO: Can't do multiple prediction rounds rn.
        )

    def with_evaluators(
        self,
        evaluators: Sequence[
            Union[
                EVALUATOR_T,
                RunEvaluator,
            ]
        ],
        *,
        max_concurrency: Optional[int] = None,
    ) -> _ExperimentManager:
        """Lazily apply the provided evaluators to the experiment."""
        evaluators = _resolve_evaluators(evaluators)
        context = copy_context()
        experiment_results = context.run(
            self._score, evaluators, max_concurrency=max_concurrency
        )
        # Split the generator into three so the manager
        # can consume each value individually.
        r1, r2, r3 = itertools.tee(experiment_results, 3)
        return _ExperimentManager(
            (result["example"] for result in r1),
            experiment=self._experiment,
            metadata=self._metadata,
            client=self.client,
            runs=(result["run"] for result in r2),
            evaluation_results=(result["evaluation_results"] for result in r3),
            summary_results=self._summary_results,
        )

    def with_summary_evaluators(
        self,
        summary_evaluators: Sequence[SUMMARY_EVALUATOR_T],
    ) -> _ExperimentManager:
        """Lazily apply the provided summary evaluators to the experiment."""
        wrapped_evaluators = _wrap_summary_evaluators(summary_evaluators)
        context = copy_context()
        aggregate_feedback_gen = context.run(
            self._apply_summary_evaluators, wrapped_evaluators
        )
        return _ExperimentManager(
            self.examples,
            experiment=self._experiment,
            metadata=self._metadata,
            client=self.client,
            runs=self.runs,
            evaluation_results=self._evaluation_results,
            summary_results=aggregate_feedback_gen,
        )

    def get_results(self) -> Iterable[ExperimentResultRow]:
        """Return the traces, evaluation results, and associated examples."""
        for run, example, evaluation_results in zip(
            self.runs, self.examples, self.evaluation_results
        ):
            yield ExperimentResultRow(
                run=run,
                example=example,
                evaluation_results=evaluation_results,
            )

    def get_summary_scores(self) -> Dict[str, List[dict]]:
        """If summary_evaluators were applied, consume and return the results."""
        if self._summary_results is None:
            return {"results": []}
        # Consume the generator
        return {
            "results": [
                res for results in self._summary_results for res in results["results"]
            ]
        }

    # Private methods.

    def _get_experiment_metadata(self):
        project_metadata = self._metadata or {}
        git_info = ls_env.get_git_info()
        if git_info:
            project_metadata = {
                **project_metadata,
                "git": git_info,
            }
        if self._experiment:
            project_metadata = {
                **self._experiment.metadata,
                **project_metadata,
            }
        return project_metadata

    def _get_experiment(self) -> schemas.TracerSession:
        if self._experiment is None:
            raise ValueError("Experiment not started yet.")
        return self._experiment

    def _end(self) -> None:
        experiment = self._experiment
        if experiment is None:
            raise ValueError("Experiment not started yet.")
        examples = list(self.examples)
        modified_at = [ex.modified_at for ex in examples if ex.modified_at]
        # Should always be defined in practice when fetched,
        # but the typing permits None
        max_modified_at = max(modified_at) if modified_at else None
        project_metadata = self._get_experiment_metadata()
        project_metadata["dataset_version"] = (
            max_modified_at.isoformat() if max_modified_at else None
        )

        self.client.update_project(
            experiment.id,
            end_time=datetime.datetime.now(datetime.timezone.utc),
            metadata=project_metadata,
        )

    def _predict(
        self, target: TARGET_T, /, max_concurrency: Optional[int] = None
    ) -> Generator[_ForwardResults, None, None]:
        """Run the target function on the examples."""
        fn = _ensure_traceable(target)
        if max_concurrency == 0:
            for example in self.examples:
                yield _forward(
                    fn, example, self.experiment_name, self._metadata, self.client
                )

        else:
            with cf.ThreadPoolExecutor(max_concurrency) as executor:
                futures = [
                    executor.submit(
                        _forward,
                        fn,
                        example,
                        self.experiment_name,
                        self._metadata,
                        self.client,
                    )
                    for example in self.examples
                ]
                for future in cf.as_completed(futures):
                    yield future.result()
        # Close out the project.
        self._end()

    def _run_evaluators(
        self,
        evaluators: Sequence[RunEvaluator],
        current_results: ExperimentResultRow,
    ) -> ExperimentResultRow:
        current_context = rh.get_tracing_context()
        metadata = {
            **(current_context["metadata"] or {}),
            **{"experiment": self.experiment_name},
        }
        with rh.tracing_context(
            **{**current_context, "project_name": "evaluators", "metadata": metadata}
        ):
            run = current_results["run"]
            example = current_results["example"]
            eval_results = current_results["evaluation_results"]
            for evaluator in evaluators:
                try:
                    evaluator_response = evaluator.evaluate_run(
                        run=run,
                        example=example,
                    )
                    eval_results["results"].extend(
                        # TODO: This is a hack
                        self.client._log_evaluation_feedback(
                            evaluator_response,
                            run=run,
                        )
                    )
                except Exception as e:
                    logger.error(
                        f"Error running evaluator {repr(evaluator)} on"
                        f" run {run.id}: {repr(e)}",
                        exc_info=True,
                    )
            return ExperimentResultRow(
                run=run,
                example=example,
                evaluation_results=eval_results,
            )

    def _score(
        self,
        evaluators: Sequence[RunEvaluator],
        max_concurrency: Optional[int] = None,
    ) -> Iterable[ExperimentResultRow]:
        """Run the evaluators on the prediction stream.

        Expects runs to be available in the manager.
        (e.g. from a previous prediction step)
        """
        if max_concurrency == 0:
            for current_results in self.get_results():
                yield self._run_evaluators(evaluators, current_results)
        else:
            with cf.ThreadPoolExecutor(max_workers=max_concurrency) as executor:
                futures = []
                for current_results in self.get_results():
                    futures.append(
                        executor.submit(
                            self._run_evaluators,
                            evaluators,
                            current_results,
                        )
                    )
                for future in cf.as_completed(futures):
                    result = future.result()
                    yield result

    def _apply_summary_evaluators(
        self, summary_evaluators: Sequence[SUMMARY_EVALUATOR_T]
    ) -> Generator[EvaluationResults, None, None]:
        runs, examples = [], []
        for run, example in zip(self.runs, self.examples):
            runs.append(run)
            examples.append(example)
        aggregate_feedback = []
        with cf.ThreadPoolExecutor() as executor:
            project_id = self._get_experiment().id
            for evaluator in summary_evaluators:
                try:
                    summary_eval_result = evaluator(runs, examples)
                    # TODO: Expose public API for this.
                    flattened_results = self.client._select_eval_results(
                        summary_eval_result,
                        fn_name=evaluator.__name__,
                    )
                    aggregate_feedback.extend(flattened_results)
                    for result in flattened_results:
                        feedback = result.dict(exclude={"target_run_id"})
                        evaluator_info = feedback.pop("evaluator_info", None)
                        executor.submit(
                            self.client.create_feedback,
                            **feedback,
                            run_id=None,
                            project_id=project_id,
                            source_info=evaluator_info,
                        )
                except Exception as e:
                    logger.error(
                        f"Error running summary evaluator {repr(evaluator)}: {e}"
                    )
        yield {"results": aggregate_feedback}


def _resolve_evaluators(
    evaluators: Sequence[EVALUATOR_T],
) -> Sequence[RunEvaluator]:
    results = []
    for evaluator in evaluators:
        if isinstance(evaluator, RunEvaluator):
            results.append(evaluator)
        elif isinstance(evaluator, LangChainStringEvaluator):
            results.append(evaluator.as_run_evaluator())
        else:
            results.append(run_evaluator(evaluator))
    return results


def _wrap_summary_evaluators(
    evaluators: Sequence[SUMMARY_EVALUATOR_T],
) -> List[SUMMARY_EVALUATOR_T]:
    def _wrap(evaluator: SUMMARY_EVALUATOR_T) -> SUMMARY_EVALUATOR_T:
        eval_name = getattr(evaluator, "__name__", "BatchEvaluator")

        @functools.wraps(evaluator)
        def _wrapper_inner(
            runs: Sequence[schemas.Run], examples: Sequence[schemas.Example]
        ) -> EvaluationResults:
            @rh.traceable(name=eval_name)
            def _wrapper_super_inner(runs_: str, examples_: str) -> EvaluationResults:
                return evaluator(runs, examples)

            return _wrapper_super_inner(
                f"Runs[] (Length={len(runs)})", f"Examples[] (Length={len(examples)})"
            )

        return _wrapper_inner

    results = []
    for evaluator in evaluators:
        results.append(_wrap(evaluator))
    return results


class _ForwardResults(TypedDict):
    run: schemas.Run
    example: schemas.Example


def _forward(
    fn: rh.SupportsLangsmithExtra,
    example: schemas.Example,
    experiment_name: str,
    metadata: dict,
    client: langsmith.Client,
) -> _ForwardResults:
    run: Optional[schemas.RunBase] = None

    def _get_run(r: run_trees.RunTree) -> None:
        nonlocal run
        run = r

    try:
        fn(
            example.inputs,
            langsmith_extra=rh.LangSmithExtra(
                reference_example_id=example.id,
                on_end=_get_run,
                project_name=experiment_name,
                metadata={
                    **metadata,
                    "example_version": (
                        example.modified_at.isoformat()
                        if example.modified_at
                        else example.created_at.isoformat()
                    ),
                },
                client=client,
            ),
        )
    except Exception as e:
        logger.error(f"Error running target function: {e}")
    return _ForwardResults(
        run=cast(schemas.Run, run),
        example=example,
    )


def _resolve_data(
    data: DATA_T, *, client: langsmith.Client
) -> Iterable[schemas.Example]:
    """Return the examples for the given dataset."""
    if isinstance(data, str):
        return client.list_examples(dataset_name=data)
    elif isinstance(data, uuid.UUID):
        return client.list_examples(dataset_id=data)
    return data


def _ensure_traceable(target: TARGET_T) -> rh.SupportsLangsmithExtra:
    """Ensure the target function is traceable."""
    if not callable(target):
        raise ValueError("Target must be a callable function.")
    if rh.is_traceable_function(target):
        fn = cast(rh.SupportsLangsmithExtra, target)
    else:
        fn = rh.traceable(name="Target")(target)
    return fn


def _resolve_experiment_name(
    experiment: Optional[schemas.TracerSession],
    experiment_prefix: Optional[str],
    runs: Optional[Iterable[schemas.Run]],
    client: langsmith.Client,
) -> Tuple[str, Optional[schemas.TracerSession], Optional[Iterable[schemas.Run]]]:
    if experiment is not None:
        if not experiment.name:
            raise ValueError("Experiment name must be defined if provided.")
        return experiment.name, experiment, runs
    # If we have runs, that means the experiment was already started.
    if runs is not None:
        runs, runs_iter = itertools.tee(runs)
        first_run = next(runs_iter)
        experiment = client.read_project(project_id=first_run.session_id)
        if not experiment.name:
            raise ValueError("Experiment name not found for provided runs.")
        return experiment.name, experiment, runs
    # Otherwise, we will generate a new experiment name.
    if isinstance(experiment_prefix, str):
        return experiment_prefix + ":" + uuid.uuid4().hex[:7], None, None
    return _get_random_name(), None, None


def _get_random_name() -> str:
    from langsmith.evaluation._name_generation import random_name  # noqa: F401

    return random_name()
