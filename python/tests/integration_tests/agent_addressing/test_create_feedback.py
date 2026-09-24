"""`Client.create_feedback`, addressed by agent.

Feedback describes a run, so every case sends one agent-addressed root run
first, then feedback for it, and asserts which project the feedback landed in.
The environment is never read here, by design: feedback copies the run's
addressing, or takes the pair as keyword arguments.
"""

from __future__ import annotations

import dataclasses

import pytest

from langsmith import target as ls_target
from langsmith.async_client import AsyncClient
from tests.integration_tests.agent_addressing.conftest import (
    AGENT,
    OTHER_AGENT,
    PROJECT,
    Case,
    Destination,
    Harness,
    InAgent,
    InProject,
    Rejected,
)

# The project of the run the feedback describes, known only once it is sent.
RUN_PROJECT = "{run_project}"

# `smith-go/agentplatform/errors.go::ErrAgentEnvironmentUnresolvable`.
REJECTED_UNKNOWN_AGENT = Rejected(
    reason=(
        "no Agent environment matches this Agent id and environment, and"
        " sending feedback does not create one"
    ),
    remedy="Create the Agent and this environment before sending feedback for them",
)


@dataclasses.dataclass(frozen=True)
class FeedbackCase(Case):
    """`kwargs` go to `create_feedback`; the run it describes is sent to `run_in`."""

    run_in: Destination = InAgent("STAGING")
    with_trace_id: bool = True


CASES = [
    FeedbackCase(
        "agent_pair",
        kwargs={"target": ls_target(AGENT, environment="staging")},
        lands_in=InAgent("STAGING"),
    ),
    # The legacy way: the run's own project.
    FeedbackCase(
        "session_id",
        kwargs={"session_id": RUN_PROJECT},
        lands_in=InAgent("STAGING"),
    ),
    # Feedback has its own conflict message: its schema has no `session_name`.
    FeedbackCase(
        "agent_and_session_id",
        kwargs={
            "target": ls_target(AGENT, environment="staging"),
            "session_id": RUN_PROJECT,
        },
        lands_in=Rejected(
            reason="agent_id cannot be combined with session_id",
            remedy="Address the feedback by agent_id, or by session_id, but not both",
        ),
    ),
    # Unlike a run, feedback never creates the agent it names.
    FeedbackCase(
        "unknown_agent",
        kwargs={"target": ls_target(OTHER_AGENT, environment="staging")},
        lands_in=REJECTED_UNKNOWN_AGENT,
    ),
    # An agent adopted from a project has production only, so staging is
    # missing rather than unknown.
    FeedbackCase(
        "missing_environment",
        run_in=InProject(PROJECT),
        kwargs={"target": ls_target(PROJECT, environment="staging")},
        lands_in=REJECTED_UNKNOWN_AGENT,
    ),
    # No addressing on the call: the run is looked up, and the agent in the
    # environment is not read. It points at another agent so that reading it
    # would show.
    FeedbackCase(
        "env_agent_not_read",
        env={
            "LANGSMITH_TARGET_ID": OTHER_AGENT,
            "LANGSMITH_TARGET_ENVIRONMENT": "staging",
        },
        lands_in=InAgent("STAGING"),
    ),
    # TEMPORARY: pins today's behavior so that fixing it is noticed. Without a
    # `trace_id`, feedback goes through `POST /feedback`, whose schema has no
    # agent fields, so the pair is dropped in silence and the feedback lands
    # wherever the run lookup says. The right answer is the 400 of
    # `unknown_agent`, or a refusal from the SDK before sending.
    FeedbackCase(
        "agent_without_trace_id",
        kwargs={"target": ls_target(OTHER_AGENT, environment="staging")},
        with_trace_id=False,
        lands_in=InAgent("STAGING"),
    ),
]


@pytest.mark.parametrize("case", CASES, ids=str)
def test_addressing(case: FeedbackCase, ls: Harness) -> None:
    """Feedback for a run resolves to one project, or is refused."""
    ls.configure(case)
    run = ls.ingest(case.run_in)
    kwargs = ls.format(case.kwargs, run_project=str(run.session_id))

    feedback = ls.client.create_feedback(
        run.id,
        key="quality",
        score=1,
        trace_id=run.trace_id if case.with_trace_id else None,
        **kwargs,
    )
    ls.client.flush()

    ls.assert_feedback_landed(feedback.id, case.lands_in)


async def test_the_async_client_drops_the_pair_in_silence(ls: Harness) -> None:
    """TEMPORARY: pins today's behavior so that fixing it is noticed.

    `AsyncClient.create_feedback` takes the pair and only ever sends JSON, so
    it goes the way of `agent_without_trace_id` above, every time.
    """
    run = ls.ingest(InAgent("STAGING"))

    feedback = await AsyncClient().create_feedback(
        run.id,
        key="quality",
        score=1,
        trace_id=run.trace_id,
        target=ls_target(ls.other_agent_key, environment="staging"),
    )

    ls.assert_feedback_landed(feedback.id, InAgent("STAGING"))
