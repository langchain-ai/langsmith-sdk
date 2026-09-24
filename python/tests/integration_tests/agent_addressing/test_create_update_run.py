"""`Client.create_run` and `Client.update_run`, addressed by agent.

Every case sends one root run and then patches it, because the two halves of a
run are addressed separately in the SDK and have gone to two different places
before. `Client._apply_agent_addressing` is the resolution under test.
"""

from __future__ import annotations

import datetime
import uuid

import pytest

from langsmith import target as ls_target
from tests.integration_tests.agent_addressing.conftest import (
    AGENT,
    PROJECT,
    Case,
    Harness,
    InAgent,
    InProject,
    Untraced,
)

CASES = [
    # The plain agent-addressed configuration: two env vars, no project.
    Case(
        "env_agent",
        env={"LANGSMITH_TARGET_ID": AGENT, "LANGSMITH_TARGET_ENVIRONMENT": "staging"},
        lands_in=InAgent("STAGING"),
    ),
    # A project named on the call always wins over agent addressing: the agent
    # replaces only the project the SDK would have defaulted in.
    Case(
        "env_agent_and_explicit_project",
        env={"LANGSMITH_TARGET_ID": AGENT, "LANGSMITH_TARGET_ENVIRONMENT": "staging"},
        kwargs={"project_name": PROJECT},
        lands_in=InProject(PROJECT),
    ),
    # Both from the environment, the same level: neither outranks the other,
    # so the SDK drops the run and logs why, rather than moving a customer's
    # traces without asking.
    Case(
        "env_agent_and_env_project",
        env={
            "LANGSMITH_TARGET_ID": AGENT,
            "LANGSMITH_TARGET_ENVIRONMENT": "staging",
            "LANGSMITH_PROJECT": PROJECT,
        },
        lands_in=Untraced(reason="are both set in the environment"),
    ),
    # Addressing passed per call rather than configured in the environment.
    Case(
        "explicit_agent",
        kwargs={"target": ls_target(AGENT, environment="staging")},
        lands_in=InAgent("STAGING"),
    ),
    # A genuinely incomplete target is dropped and logged, not a run that
    # quietly landed in `default`.
    Case(
        "env_agent_id_only",
        env={"LANGSMITH_TARGET_ID": AGENT},
        lands_in=Untraced(reason="incomplete target"),
    ),
    # The legacy path, unchanged: a project by name, and no addressing at all.
    Case(
        "env_project",
        env={"LANGSMITH_PROJECT": PROJECT},
        lands_in=InProject(PROJECT),
    ),
    Case(
        "no_addressing",
        lands_in=InProject("default"),
    ),
]


@pytest.mark.parametrize("case", CASES, ids=str)
def test_addressing(case: Case, ls: Harness) -> None:
    """A configuration resolves to exactly one destination, on both halves."""
    args = ls.configure(case)
    run = ls.root_run()

    ls.client.create_run(
        **run,
        name="agent-addressing",
        run_type="chain",
        inputs={"question": "where does this run land?"},
        start_time=ls.start_time,
        **args.create,
    )
    ls.client.update_run(
        run["id"],
        trace_id=run["trace_id"],
        dotted_order=run["dotted_order"],
        outputs={"answer": "see the assertion"},
        end_time=datetime.datetime.now(datetime.timezone.utc),
        **args.update,
    )
    ls.client.flush()

    ls.assert_landed(run["id"], case.lands_in)


def test_an_unknown_agent_is_created_with_every_environment(ls: Harness) -> None:
    """Ingesting into an agent that does not exist creates it, whole.

    All four environments, not just the one the run named: an agent is only
    readable through its production environment, so an agent holding staging
    alone would be invisible to the API that lists it.
    """
    ls.configure(
        Case(
            "created",
            env={
                "LANGSMITH_TARGET_ID": AGENT,
                "LANGSMITH_TARGET_ENVIRONMENT": "staging",
            },
            lands_in=InAgent("STAGING"),
        )
    )
    run = ls.root_run()

    ls.client.create_run(
        **run,
        name="agent-addressing",
        run_type="chain",
        inputs={},
        start_time=ls.start_time,
    )
    ls.client.flush()
    ls.assert_landed(run["id"], InAgent("STAGING"), patched=False)

    agent = ls.agent()
    assert agent is not None
    # An ingestion-created agent is EXTERNAL, and has no name to take but its
    # own key.
    assert agent["id"] == ls.agent_key
    assert agent["name"] == ls.agent_key
    assert agent["source_type"] == "EXTERNAL"
    environments = {
        env["environment"]: env["tracer_session_name"] for env in agent["environments"]
    }
    assert environments == {
        "LOCAL": f"{ls.agent_key}-local",
        "DEVELOPMENT": f"{ls.agent_key}-development",
        "STAGING": f"{ls.agent_key}-staging",
        "PRODUCTION": f"{ls.agent_key}-production",
    }


def test_a_new_project_is_adopted_as_an_agent(ls: Harness) -> None:
    """The legacy path creates an agent too, with production alone.

    The project already exists by the time the agent is registered, so the
    agent adopts it rather than bringing four projects of its own.
    """
    ls.configure(
        Case("adopted", env={"LANGSMITH_PROJECT": PROJECT}, lands_in=InProject(PROJECT))
    )
    run = ls.root_run()

    ls.client.create_run(
        **run,
        name="agent-addressing",
        run_type="chain",
        inputs={},
        start_time=ls.start_time,
    )
    ls.client.flush()
    ls.assert_landed(run["id"], InProject(PROJECT), patched=False)

    adopted = ls.agent(key=ls.project_name)
    assert adopted is not None, (
        f"the project {ls.project_name!r} should have been adopted as an agent"
    )
    assert [env["environment"] for env in adopted["environments"]] == ["PRODUCTION"]


def test_a_run_off_the_multipart_path_falls_back_to_the_default_project(
    ls: Harness,
) -> None:
    """TEMPORARY: pins today's behavior so that fixing it is noticed.

    Delete this test once the non-multipart ingestion endpoints read the agent
    pair. It asserts the *wrong* outcome on purpose, and turns red the moment
    the right one starts happening.

    `create_run` and `update_run` only reach `POST /runs/multipart` when the
    run carries both `trace_id` and `dotted_order`. Without them they fall back
    to `POST /runs` and `PATCH /runs/{run_id}`, which do not read the agent
    pair at all, so an agent-addressed run silently lands in `default`: the SDK
    has already suppressed the defaulted project, and nothing on the way
    reports that the addressing it sent was ignored.

    That makes it worse than a missing feature. The traces do not fail, they
    arrive somewhere the caller never named, which is exactly what the design
    doc refuses to let the `session_name` path do. The same hole exists on
    `POST /runs/batch` via `batch_ingest_runs`, and on `AsyncClient`, which
    have their own files in the plan.
    """
    ls.configure(
        Case(
            "off_the_multipart_path",
            env={
                "LANGSMITH_TARGET_ID": AGENT,
                "LANGSMITH_TARGET_ENVIRONMENT": "staging",
            },
            lands_in=InProject("default"),
        )
    )
    # Deliberately no `trace_id` and no `dotted_order`, which is what sends
    # this run down the non-multipart path.
    run_id = uuid.uuid4()

    ls.client.create_run(
        id=run_id,
        name="agent-addressing",
        run_type="chain",
        inputs={},
        start_time=ls.start_time,
    )
    ls.client.flush()

    # `InProject` also asserts no agent was created under the key, which is the
    # other half of the loss: the agent the caller named never comes into being.
    ls.assert_landed(run_id, InProject("default"), patched=False)
