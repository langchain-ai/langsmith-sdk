"""`Client.multipart_ingest`, addressed by agent.

The dict-input surface. It still runs through `Client._run_transform`, so it
cannot send a payload the rest of the SDK would not: what is under test here is
that addressing fields on a raw run dict are resolved the same way as
arguments, and that a create and an update sent together agree on where they
go. The endpoint's own contract for payloads no SDK would build (an agent
beside a `session_name`, a non-string field) is covered by the backend's tests
in langchainplus, not here.
"""

from __future__ import annotations

import datetime
import uuid

import pytest

from tests.integration_tests.agent_addressing.conftest import (
    AGENT,
    PROJECT,
    Case,
    Harness,
    InAgent,
    InProject,
)

CASES = [
    Case(
        "env_agent",
        env={"LANGSMITH_TARGET_ID": AGENT, "LANGSMITH_TARGET_ENVIRONMENT": "staging"},
        lands_in=InAgent("STAGING"),
    ),
    # Addressing on the run dict rather than in the environment.
    Case(
        "agent_on_the_run",
        kwargs={"agent_id": AGENT, "agent_environment": "staging"},
        lands_in=InAgent("STAGING"),
    ),
    # A project on the run dict wins over an agent in the environment.
    Case(
        "env_agent_and_project_on_the_run",
        env={"LANGSMITH_TARGET_ID": AGENT, "LANGSMITH_TARGET_ENVIRONMENT": "staging"},
        kwargs={"session_name": PROJECT},
        lands_in=InProject(PROJECT),
    ),
]


@pytest.mark.parametrize("case", CASES, ids=str)
def test_addressing(case: Case, ls: Harness) -> None:
    """A create and an update in one call land in the same project."""
    args = ls.configure(case)
    run_id = uuid.uuid4()
    dotted_order = f"{ls.start_time.strftime('%Y%m%dT%H%M%S%fZ')}{run_id}"

    ls.client.multipart_ingest(
        create=[
            {
                "id": str(run_id),
                "trace_id": str(run_id),
                "dotted_order": dotted_order,
                "name": "agent-addressing",
                "run_type": "chain",
                "inputs": {"question": "where does this run land?"},
                "start_time": ls.start_time,
                **args.create,
            }
        ],
        update=[
            {
                "id": str(run_id),
                "trace_id": str(run_id),
                "dotted_order": dotted_order,
                "outputs": {"answer": "see the assertion"},
                "end_time": datetime.datetime.now(datetime.timezone.utc),
                **args.create,
            }
        ],
    )
    ls.client.flush()

    ls.assert_landed(run_id, case.lands_in)
