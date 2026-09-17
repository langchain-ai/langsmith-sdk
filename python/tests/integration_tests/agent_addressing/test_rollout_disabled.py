"""Agent addressing when the workspace is not on the rollout flag.

A workspace without `agent_platform_unified_experience` gets a 403, answered
before any lookup so nothing is created. That is stubbed here rather than
reached for real: a workspace with the flag on cannot produce a 403, and a
flag-off one would mean a second API key in CI.

Only the SDK's half is asserted. The status is langchainplus's contract.
"""

from __future__ import annotations

import logging

import pytest
import requests

from langsmith.run_helpers import get_current_run_tree, traceable
from tests.integration_tests.agent_addressing.conftest import (
    AGENT,
    Case,
    Harness,
    InAgent,
)

# What the endpoint answers a workspace off the rollout with.
REFUSAL_DETAIL = "agent addressing is not enabled for this workspace"


def _refuse_agent_addressing(client, monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer ingestion with a 403. Other routes still reach the real API."""
    send = client.session.request

    def request(method, url, *args, **kwargs):
        if str(url).endswith("/runs/multipart"):
            refused = requests.Response()
            refused.status_code = 403
            refused.url = str(url)
            refused._content = f'{{"detail":"{REFUSAL_DETAIL}"}}'.encode()
            return refused
        return send(method, url, *args, **kwargs)

    monkeypatch.setattr(client.session, "request", request)


def test_a_refused_workspace_loses_the_run_without_raising(
    ls: Harness, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The 403 is reported, never raised at the call site, and creates nothing.

    Losing the traces is the accepted cost of resolving addressing server-side:
    a rejected batch is logged on the flush thread, so a misconfigured
    workspace shows up as missing traces rather than a failure.
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
    addressing = {}

    @traceable
    def traced_function() -> str:
        run = get_current_run_tree()
        addressing["agent_id"] = run.agent_id
        addressing["agent_environment"] = run.agent_environment
        addressing["session_name"] = run.session_name
        return "ok"

    with caplog.at_level(logging.WARNING, logger="langsmith.client"):
        assert traced_function(langsmith_extra={"client": ls.client}) == "ok"
        ls.client.flush()

    # The stub refuses every multipart request, so without this the test would
    # pass for a project-addressed run too.
    assert addressing == {
        "agent_id": ls.agent_key,
        "agent_environment": "staging",
        "session_name": None,
    }
    ls.assert_rejected(because="403")

    # The log line is all a misconfigured caller gets, so it has to name the
    # failure and carry the server's reason rather than just say something
    # went wrong.
    warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any(
        "multipart ingest" in message and "403" in message and REFUSAL_DETAIL in message
        for message in warnings
    ), f"expected a warning explaining the refused ingest, got {warnings}"
