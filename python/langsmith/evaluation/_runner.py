"""V2 Evaluation Interface."""

from __future__ import annotations

import concurrent.futures as cf
import datetime
import itertools
import logging
import threading
import uuid
from typing import (
    Callable,
    Generator,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Union,
    cast,
)

from requests import HTTPError
from typing_extensions import TypedDict

import langsmith
from langsmith import env as ls_env
from langsmith import run_helpers as rh
from langsmith import run_trees, schemas
from langsmith import utils as ls_utils
from langsmith.evaluation.integrations import LangChainStringEvaluator
from langsmith.evaluation.evaluator import (
    EvaluationResult,
    EvaluationResults,
    RunEvaluator,
    run_evaluator,
)

logger = logging.getLogger(__name__)

PIPELINE_T = Callable[[dict], dict]
TARGET_T = Union[PIPELINE_T, Callable[[], PIPELINE_T]]
# dataset-name, dataset_id, or examples
DATA_T = Union[str, uuid.UUID, Iterable[schemas.Example]]
BATCH_EVALUATOR_T = Callable[
    [Sequence[schemas.Run], Sequence[schemas.Example]],
    Union[EvaluationResult, EvaluationResults],
]
EVALUATOR_T = Union[
    RunEvaluator,
    Callable[[schemas.Run, Optional[schemas.Example]], EvaluationResult],
]


def evaluate(
    target: TARGET_T,
    /,
    data: DATA_T,
    evaluators: Optional[Sequence[EVALUATOR_T]] = None,
    batch_evaluators: Optional[Sequence[BATCH_EVALUATOR_T]] = None,
    metadata: Optional[dict] = None,
    experiment: str | None = None,
    max_concurrency: int | None = None,
    client: langsmith.Client | None = None,
    blocking: bool = False,
) -> ExperimentResults:
    manager = _ExperimentManager(
        data, client=client, metadata=metadata, experiment=experiment
    ).start()
    manager = manager.with_predictions(
        target,
        max_concurrency=max_concurrency,
    )
    if evaluators:
        manager = manager.with_scores(evaluators, max_concurrency=max_concurrency)
    if batch_evaluators:
        manager = manager.with_batch_scores(batch_evaluators)
    results = ExperimentResults(
        manager,
    )
    if blocking:
        results.wait()
    return results


class ExperimentResultRow(TypedDict):
    run: schemas.Run
    example: schemas.Example
    evaluation_results: EvaluationResults


class ExperimentResults:
    def __init__(
        self,
        experiment_manager: _ExperimentManager,
    ):
        self._manager = experiment_manager
        self._results: List[ExperimentResultRow] = []
        self._lock = threading.Lock()
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
        results = manager.get_results()
        for item in results:
            with self._lock:
                self._results.append(item)
        batch_scores = manager.get_batch_scores()
        with self._lock:
            self._aggregate_results = batch_scores

    def __len__(self) -> int:
        return len(self._results)

    # TODO: Implement this
    # def __getitem__(self, index: int | slice) -> dict | List[dict]:
    #     if isinstance(index, int):
    #         with self._lock:
    #             if index < len(self._results):
    #                 return self._results[index]
    #             elif not self._thread.is_alive():
    #                 raise IndexError("Index out of range")
    #         self._thread.join()
    #         return self._results[index]
    #     elif isinstance(index, slice):
    #         start, stop, step = index.indices(len(self))
    #         with self._lock:
    #             if stop <= len(self._results):
    #                 return self._results[start:stop:step]
    #             elif not self._thread.is_alive():
    #                 return self._results[start:stop:step]
    #         self._thread.join()
    #         return self._results[start:stop:step]
    #     else:
    #         raise TypeError("Invalid index type")

    def __repr__(self) -> str:
        return f"<ExperimentResults {self.experiment_name}>"

    def wait(self) -> None:
        self._thread.join()


class _ExperimentManager:
    def __init__(
        self,
        data: DATA_T,
        /,
        runs: Optional[Iterable[schemas.Run]] = None,
        experiment: Optional[Union[str, schemas.TracerSession]] = None,
        metadata: Optional[dict] = None,
        client: Optional[langsmith.Client] = None,
        evaluation_results: Optional[Iterable[EvaluationResults]] = None,
        aggregate_results: Optional[Iterable[EvaluationResults]] = None,
    ):
        self._experiment: Optional[schemas.TracerSession] = (
            experiment if isinstance(experiment, schemas.TracerSession) else None
        )
        if isinstance(experiment, str):
            self.experiment_name: str = experiment
        elif isinstance(experiment, schemas.TracerSession) and experiment.name:
            self.experiment_name = experiment.name
        else:
            self.experiment_name = uuid.uuid4().hex
        metadata = metadata or {}
        if not metadata.get("revision_id"):
            metadata = {
                "revision_id": ls_env.get_langchain_env_var_metadata().get(
                    "revision_id"
                ),
                **metadata,
            }
        self._metadata = metadata or {}
        self.client = client or langsmith.Client()
        self._data = data
        self._examples: Optional[Iterable[schemas.Example]] = None
        self._runs = runs
        self._evaluation_results = evaluation_results
        self._aggregate_results = aggregate_results

    @staticmethod
    def _resolve_data(
        data: DATA_T, *, client: langsmith.Client
    ) -> Iterable[schemas.Example]:
        if isinstance(data, str):
            return client.list_examples(dataset_name=data)
        elif isinstance(data, uuid.UUID):
            return client.list_examples(dataset_id=data)
        return data

    @property
    def examples(self) -> Iterable[schemas.Example]:
        if self._examples is None:
            self._examples = self._resolve_data(self._data, client=self.client)
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
        _examples = itertools.chain([first_example], self.examples)
        if self._experiment is None:
            try:
                project_metadata = self._metadata or {}
                git_info = ls_env.get_git_info()
                if git_info:
                    project_metadata = {
                        **project_metadata,
                        "git": git_info,
                    }
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
            # HACKHACK
            project_url = project.url.split("?")[0]
            dataset_id = first_example.dataset_id
            base_url = project_url.split("/projects/p/")[0]
            comparison_url = (
                f"{base_url}/datasets/{dataset_id}/compare?"
                f"selectedSessions={project.id}"
            )
            logger.info(  # noqa: T201
                f"View the evaluation results for project '{self.experiment_name}'"
                f" at:\n{comparison_url}\n\n"
            )
        else:
            # HACKHACK
            logger.info("Starting evaluation of experiment: %s", self.experiment_name)
        return _ExperimentManager(
            _examples,
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
        _experiment_results = self._predict(target, max_concurrency=max_concurrency)
        r1, r2 = itertools.tee(_experiment_results, 2)
        return _ExperimentManager(
            (pred["example"] for pred in r1),
            experiment=self._experiment,
            metadata=self._metadata,
            client=self.client,
            runs=(pred["run"] for pred in r2),
            # TODO: Can't do multiple prediction rounds rn.
            # evaluation_results=(
            #     pred["evaluation_results"] for pred in _experiment_results
            # ),
        )

    def with_scores(
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
        evaluators = _resolve_evaluators(evaluators)
        experiment_results = self._score(evaluators, max_concurrency=max_concurrency)
        r1, r2, r3 = itertools.tee(experiment_results, 3)
        return _ExperimentManager(
            (result["example"] for result in r1),
            experiment=self._experiment,
            metadata=self._metadata,
            client=self.client,
            runs=(result["run"] for result in r2),
            evaluation_results=(result["evaluation_results"] for result in r3),
            aggregate_results=self._aggregate_results,
        )

    def with_batch_scores(
        self,
        batch_evaluators: Sequence[BATCH_EVALUATOR_T],
    ) -> _ExperimentManager:
        aggregate_feedback_gen = self._apply_batch_evaluators(batch_evaluators)
        return _ExperimentManager(
            self.examples,
            experiment=self._experiment,
            metadata=self._metadata,
            client=self.client,
            runs=self.runs,
            evaluation_results=self._evaluation_results,
            aggregate_results=aggregate_feedback_gen,
        )

    def get_results(self) -> Iterable[ExperimentResultRow]:
        for run, example, evaluation_results in zip(
            self.runs, self.examples, self.evaluation_results
        ):
            yield ExperimentResultRow(
                run=run,
                example=example,
                evaluation_results=evaluation_results,
            )

    def get_batch_scores(self):
        if self._aggregate_results is None:
            return {"results": []}
        # Consume the generator
        return {
            "results": [res for results in self._aggregate_results for res in results]
        }

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

        self.client.update_project(
            experiment.id,
            end_time=datetime.datetime.now(datetime.timezone.utc),
            metadata={
                "dataset_version": (
                    max_modified_at.isoformat() if max_modified_at else None
                )
            },
        )

    @staticmethod
    def _wrap_target(target: TARGET_T) -> rh.SupportsLangsmithExtra:
        if rh.is_traceable_function(target):
            fn = cast(rh.SupportsLangsmithExtra, target)
        else:
            fn = rh.traceable(name="Target")(target)
        return fn

    def _predict(
        self, target: TARGET_T, /, max_concurrency: Optional[int] = None
    ) -> Generator[_ForwardResults, None, None]:
        fn = self._wrap_target(target)
        if max_concurrency == 0:
            for example in self.examples:
                yield _forward(fn, example, self.experiment_name, self._metadata)

        else:
            with cf.ThreadPoolExecutor(max_concurrency) as executor:
                futures = [
                    executor.submit(
                        _forward, fn, example, self.experiment_name, self._metadata
                    )
                    for example in self.examples
                ]
                for future in cf.as_completed(futures):
                    yield future.result()
        # Close out the project
        self._end()

    def _run_evaluators(
        self,
        evaluators: Sequence[RunEvaluator],
        current_results: ExperimentResultRow,
    ) -> ExperimentResultRow:
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
                    f" run {run.id}: {repr(e)}"
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

    def _apply_batch_evaluators(
        self, batch_evaluators: Sequence[BATCH_EVALUATOR_T]
    ) -> Generator[EvaluationResults, None, None]:
        runs, examples = [], []
        for run, example in zip(self.runs, self.examples):
            runs.append(run)
            examples.append(example)
        aggregate_feedback = []
        with cf.ThreadPoolExecutor() as executor:
            project_id = self._get_experiment().id
            for evaluator in batch_evaluators:
                try:
                    # HACKHACK
                    batch_eval_result = evaluator(runs, examples)
                    flattened_results = self.client._select_eval_results(
                        batch_eval_result,
                        fn_name=evaluator.__name__,
                    )
                    aggregate_feedback.extend(flattened_results)
                    for result in flattened_results:
                        feedback = result.dict(exclude={"target_run_id"})
                        evaluator_info = feedback.pop("evaluator_info", None)
                        executor.submit(
                            self.client.create_feedback,
                            **result.dict(),
                            run_id=None,
                            project_id=project_id,
                            source_info=evaluator_info,
                        )
                except Exception as e:
                    logger.error(
                        f"Error running batch evaluator {repr(evaluator)}: {e}"
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


class _ForwardResults(TypedDict):
    run: schemas.Run
    example: schemas.Example


def _forward(
    fn: rh.SupportsLangsmithExtra,
    example: schemas.Example,
    experiment_name: str,
    metadata: dict,
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
                metadata=metadata,
            ),
        )
    except Exception as e:
        logger.error(f"Error running target function: {e}")
    return _ForwardResults(
        run=cast(schemas.Run, run),
        example=example,
    )
