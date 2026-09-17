"""What the SDK does when agent addressing is off for the workspace.

Agent addressing rolls out per workspace on the `agent_platform_unified_experience`
flag. A workspace that is not on it gets a 403, answered before any lookup so
nothing is created.

The 403 is stubbed at the transport rather than reached for real, because a
workspace with the flag on cannot produce one and a second flag-off workspace
would mean a second API key in CI. What is asserted is the SDK's side, which is
the part that is ours: the rejection is reported rather than swallowed, and it
does not surface as an exception at the call site. The status itself is
langchainplus's contract and is tested there.

One test, not one per SDK method: every method funnels into the same sender,
and a 403 is handled in shared transport code, so the other methods would
re-prove this one.
"""

from __future__ import annotations

import pytest
import requests

from tests.integration_tests.agent_addressing.conftest import (
    AGENT,
    Case,
    Harness,
    InAgent,
)


def _refuse_agent_addressing(client, monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer ingestion with the 403 a workspace off the rollout would get.

    Only `/runs/multipart` is refused, so the agent lookup this test asserts
    with still talks to the real API.
    """
    send = client.session.request

    def request(method, url, *args, **kwargs):
        if str(url).endswith("/runs/multipart"):
            refused = requests.Response()
            refused.status_code = 403
            refused.url = str(url)
            refused._content = (
                b'{"detail":"agent addressing is not enabled for this workspace"}'
            )
            return refused
        return send(method, url, *args, **kwargs)

    monkeypatch.setattr(client.session, "request", request)


def test_a_refused_workspace_loses_the_run_without_raising(
    ls: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 403 is reported through the client, and creates no agent.

    Losing the traces is the accepted trade-off of resolving addressing
    server-side: multipart flushes on a background thread, so a rejected batch
    is reported rather than raised, and a misconfigured workspace shows up as
    missing traces plus this log line. The half that must hold either way is
    that nothing was created under the agent key.
    """
    ls.configure(
        Case(
            "rollout_disabled",
            env={
                "LANGSMITH_AGENT_ID": AGENT,
                "LANGSMITH_AGENT_ENVIRONMENT": "staging",
            },
            lands_in=InAgent("STAGING"),
        )
    )
    _refuse_agent_addressing(ls.client, monkeypatch)
    run = ls.root_run()

    # No `pytest.raises`: the point is that the caller is not interrupted.
    ls.client.create_run(
        **run,
        name="agent-addressing",
        run_type="chain",
        inputs={},
        start_time=ls.start_time,
    )
    ls.client.flush()

    # Also asserts no agent exists under the key, which is the half that has
    # to hold whatever the transport did.
    ls.assert_rejected(because="403")
