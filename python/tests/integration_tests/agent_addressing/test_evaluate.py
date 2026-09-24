"""`evaluate()` beside agent addressing.

An evaluation is project-addressed end to end: the target runs go to the
experiment, the evaluator runs to `evaluators`, and the feedback to the run's
project, all named on the call. An agent configured around it must leak into
none of them, and must not be created.
"""

from __future__ import annotations

import uuid
from typing import Any

from langsmith import target as ls_target
from langsmith.evaluation import evaluate
from langsmith.run_helpers import get_current_run_tree, traceable, tracing_context
from tests.integration_tests.agent_addressing.conftest import (
    Harness,
    InProject,
    _wait_for,
)

ENV_AGENT = {
    "LANGSMITH_TARGET_AGENT_ID": "{agent}",
    "LANGSMITH_TARGET_ENVIRONMENT": "staging",
}


def _target(inputs: dict) -> dict:
    return {"answer": inputs["question"]}


def _evaluator(run: Any, example: Any) -> dict:
    return {"key": "quality", "score": 1}


def _evaluate(ls: Harness, target: Any = _target) -> tuple[str, uuid.UUID]:
    """Run one evaluation; return the experiment name and the target run id."""
    results = evaluate(
        target,
        data=ls.dataset().name,
        evaluators=[_evaluator],
        experiment_prefix=ls.project_name,
        client=ls.client,
    )
    ls.remember_project(results.experiment_name)
    rows = list(results)
    results.wait()
    ls.client.flush()
    assert len(rows) == 1
    return results.experiment_name, rows[0]["run"].id


def _assert_all_in_projects(ls: Harness, experiment: str, run_id: uuid.UUID) -> None:
    """The run, its feedback and the evaluator run each sit in a project."""
    run = ls.assert_landed(run_id, InProject(experiment), patched=True)
    assert run is not None
    feedback = _wait_for(
        lambda: next(iter(ls.client.list_feedback(run_ids=[run_id])), None),
        what=f"feedback on run {run_id}",
    )
    assert feedback.session_id == run.session_id, (
        f"the feedback landed in {feedback.session_id}, the run in {run.session_id}"
    )
    source = feedback.feedback_source
    assert source is not None and source.metadata, "the feedback names no evaluator run"
    ls.assert_landed(
        uuid.UUID(source.metadata["__run"]["run_id"]), InProject("evaluators")
    )


def test_an_agent_in_the_environment_leaks_nowhere(ls: Harness) -> None:
    ls.configure_env(ENV_AGENT)
    experiment, run_id = _evaluate(ls)
    _assert_all_in_projects(ls, experiment, run_id)


def test_an_agent_in_the_context_leaks_nowhere(ls: Harness) -> None:
    """Evaluating under an ambient agent works as it does under a project.

    The evaluators run under `tracing_context(**current_context,
    project_name="evaluators")`, where the snapshot carries the agent. That
    restored pair is not read as a second destination, and `evaluate` clears
    it besides, so the project named here addresses the run on its own.
    """
    with tracing_context(target=ls_target(ls.agent_key, environment="staging")):
        experiment, run_id = _evaluate(ls)
    _assert_all_in_projects(ls, experiment, run_id)


def test_a_target_addressing_an_agent_stays_in_the_experiment(ls: Harness) -> None:
    """An app that addresses itself to an agent, evaluated: its nested runs join
    the experiment, since a child follows its parent whatever it names."""
    nested: dict = {}

    @traceable
    def answer(inputs: dict) -> dict:
        run = get_current_run_tree()
        assert run is not None
        nested["id"] = run.id
        return _target(inputs)

    def target(inputs: dict) -> dict:
        with tracing_context(target=ls_target(ls.agent_key, environment="staging")):
            return answer(inputs)

    experiment, run_id = _evaluate(ls, target)
    _assert_all_in_projects(ls, experiment, run_id)
    ls.assert_landed(nested["id"], InProject(experiment))
