"""Score attribution in evaluate_comparative with randomize_order and concurrency."""

import datetime
import random
import threading
import types
import uuid
from typing import Any

import pytest

from langsmith import schemas, tracing_context
from langsmith.evaluation import evaluate_comparative

_NOW = datetime.datetime.now(datetime.timezone.utc)


class _StubClient:
    """Serves two stored experiments for one example and records feedback."""

    def __init__(self) -> None:
        tenant_id, dataset_id, example_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.tenant_id, self.dataset_id = tenant_id, dataset_id
        self.projects = [
            schemas.TracerSessionResult(
                id=uuid.uuid4(),
                name=name,
                start_time=_NOW,
                tenant_id=tenant_id,
                reference_dataset_id=dataset_id,
            )
            for name in ("right", "wrong")
        ]
        self.example = schemas.Example(
            id=example_id,
            dataset_id=dataset_id,
            inputs={"question": "2+2"},
            outputs={"answer": "4"},
            created_at=_NOW,
        )
        self.runs = [
            schemas.Run(
                id=uuid.uuid4(),
                name=project.name,
                run_type="chain",
                start_time=_NOW,
                inputs={"question": "2+2"},
                outputs={"answer": answer},
                reference_example_id=example_id,
                session_id=project.id,
                trace_id=uuid.uuid4(),
                dotted_order="stub",
            )
            for project, answer in zip(self.projects, ("4", "5"))
        ]
        self.info = types.SimpleNamespace(instance_flags={})
        self.feedback: list[dict[str, Any]] = []

    def list_runs(self, project_id: uuid.UUID, **kwargs: Any) -> list[schemas.Run]:
        return [run for run in self.runs if run.session_id == project_id]

    def list_examples(self, **kwargs: Any) -> list[schemas.Example]:
        return [self.example]

    def create_comparative_experiment(self, name: str, **kwargs: Any) -> Any:
        return schemas.ComparativeExperiment(
            id=kwargs["id"],
            name=name,
            tenant_id=self.tenant_id,
            reference_dataset_id=self.dataset_id,
            created_at=_NOW,
            modified_at=_NOW,
        )

    def create_feedback(self, **kwargs: Any) -> None:
        self.feedback.append(kwargs)

    def scores_by_answer(self, key: str) -> dict[str, float]:
        answer_of = {str(run.id): run.outputs["answer"] for run in self.runs}
        return {
            answer_of[str(f["run_id"])]: f["score"]
            for f in self.feedback
            if f["key"] == key
        }


@pytest.mark.parametrize("returns", ["list", "id_mapping"])
def test_randomized_concurrent_comparators_keep_scores_with_their_runs(
    monkeypatch: pytest.MonkeyPatch, returns: str
) -> None:
    """Each comparator's scores must land on the runs it actually judged.

    Both comparators score correctly for the order they receive. The shuffle is
    made deterministic (it reverses), and the second comparator's shuffle runs
    while the first comparator is still working, as it does with slow LLM judges.
    """
    first_read = threading.Event()
    both_read = threading.Barrier(2)
    shuffles: list[int] = []
    lock = threading.Lock()

    def reverse_after_first_read(runs: list) -> None:
        with lock:
            shuffles.append(1)
            second = len(shuffles) == 2
        if second:
            assert first_read.wait(timeout=10)
        runs.reverse()

    monkeypatch.setattr(random, "shuffle", reverse_after_first_read)
    client = _StubClient()

    def make_judge(name: str) -> Any:
        def judge(runs: list, example: schemas.Example) -> Any:
            correct = [float(run.outputs["answer"] == "4") for run in runs]
            first_read.set()
            both_read.wait(timeout=10)
            if returns == "list":
                return correct
            # As in the evaluate_comparative docstring: ids read after the judgment.
            return {
                "key": name,
                "scores": {runs[0].id: correct[0], runs[1].id: correct[1]},
            }

        judge.__name__ = name
        return judge

    with tracing_context(enabled=False):
        evaluate_comparative(
            tuple(client.projects),  # type: ignore[arg-type]
            evaluators=[make_judge("judge_a"), make_judge("judge_b")],
            client=client,  # type: ignore[arg-type]
            max_concurrency=2,
            randomize_order=True,
        )

    assert len(shuffles) == 2
    assert client.scores_by_answer("judge_a") == {"4": 1.0, "5": 0.0}
    assert client.scores_by_answer("judge_b") == {"4": 1.0, "5": 0.0}
