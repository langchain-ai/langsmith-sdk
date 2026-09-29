"""Agent addressing when the workspace is not on the rollout flag.

The 403 is stubbed: a workspace with the flag on cannot produce one, and a
flag-off workspace would mean a second API key in CI.
"""

from __future__ import annotations

import json
from typing import Callable

import pytest
import requests

from langsmith import address as ls_address
from langsmith.run_helpers import get_current_run_tree, traceable
from tests.integration_tests.agent_addressing.conftest import (
    AGENT,
    Case,
    Harness,
    InAgent,
    Rejected,
)

REFUSED = Rejected(
    reason="agent addressing is not enabled for this workspace",
    remedy="Address the part by session_id, or by session_name on a run part",
    status=403,
)


def _refusal_body(part: str, refused: Rejected) -> bytes:
    """The real body: status phrase, then the sentinel, then remedy and reason."""
    return json.dumps(
        {
            "error": (
                f"Forbidden: feature not enabled for {part}:"
                f" {refused.remedy}: {refused.reason}"
            )
        }
    ).encode()


def _refuse_agent_addressing(
    client,
    monkeypatch: pytest.MonkeyPatch,
    part: Callable[[], str],
    refused: Rejected,
) -> None:
    """Refuse ingestion only, so other routes reach the real API."""
    send = client.session.request

    def request(method, url, *args, **kwargs):
        if str(url).endswith("/runs/multipart"):
            response = requests.Response()
            response.status_code = refused.status
            response.url = str(url)
            response._content = _refusal_body(part(), refused)
            return response
        return send(method, url, *args, **kwargs)

    monkeypatch.setattr(client.session, "request", request)


def test_a_refused_workspace_loses_the_run_without_raising(
    ls: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The 403 is reported, never raised at the call site, and creates nothing.

    A rejected batch is logged on the flush thread, so a misconfigured
    workspace shows up as missing traces rather than as a failure.
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
    sent: dict = {}

    @traceable
    def traced_function() -> str:
        run = get_current_run_tree()
        sent.update(id=run.id, address=run.address, session_name=run.session_name)
        return "ok"

    # Read lazily: the run id exists only after the call, the refusal only on
    # flush.
    _refuse_agent_addressing(
        ls.client, monkeypatch, lambda: f"post.{sent.get('id')}", REFUSED
    )

    assert traced_function(langsmith_extra={"client": ls.client}) == "ok"
    ls.client.flush()

    # The stub refuses any multipart request, so without this the test would
    # pass for a project-addressed run too.
    assert (sent["address"], sent["session_name"]) == (
        ls_address(agent_id=ls.agent_key, agent_environment="staging"),
        None,
    )
    ls.assert_rejected(REFUSED)


def test_a_refused_workspace_loses_the_feedback_without_raising(
    ls: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same for a feedback part, whose remedy names the part, not the run."""
    run = ls.ingest(InAgent("STAGING"))
    sent: dict = {}
    _refuse_agent_addressing(
        ls.client, monkeypatch, lambda: f"feedback.{sent.get('id')}", REFUSED
    )

    feedback = ls.client.create_feedback(
        run.id,
        key="quality",
        score=1,
        trace_id=run.trace_id,
        address=ls_address(agent_id=ls.agent_key, agent_environment="staging"),
    )
    sent["id"] = feedback.id
    ls.client.flush()

    ls.assert_feedback_landed(feedback.id, REFUSED)
