"""End-to-end: a wrapped secret never reaches the wire."""

import json
import uuid
from typing import Any, List
from unittest.mock import MagicMock

import pytest

import langsmith
from langsmith import utils as ls_utils
from langsmith._internal._operations import serialize_run_dict
from langsmith.anonymizer import create_anonymizer, create_secret_anonymizer
from langsmith.client import Client
from langsmith.run_helpers import traceable, tracing_context
from langsmith.run_trees import RunTree
from langsmith.secret import LANGSMITH_SECRET_MASK, LangSmithSecret
from tests.unit_tests.conftest import parse_request_data

PLAINTEXT = "sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz"


def _mock_client(**kwargs: Any) -> Client:
    ls_utils.get_env_var.cache_clear()
    from langsmith.run_trees import _parse_write_replicas_from_env_var

    _parse_write_replicas_from_env_var.cache_clear()
    return Client(session=MagicMock(), api_key="test", **kwargs)


@pytest.fixture
def mock_client() -> Client:
    return _mock_client()


def _posted_payloads(client: Client) -> List[dict]:
    """Everything the client actually handed to the transport, decoded."""
    payloads: List[dict] = []
    for call in client.session.request.mock_calls:  # type: ignore[attr-defined]
        if not (call.args and call.args[0] == "POST"):
            continue
        data = call.kwargs.get("data")
        if data is None:
            continue
        parsed = parse_request_data(data)
        for verb in ("post", "patch"):
            payloads.extend(parsed.get(verb) or [])
    return payloads


def _assert_masked(payloads: List[dict]) -> None:
    assert payloads, "nothing was sent"
    blob = json.dumps(payloads)
    assert PLAINTEXT not in blob, "plaintext secret reached the wire"
    assert LANGSMITH_SECRET_MASK in blob


def test_exported_from_the_top_level_package():
    assert langsmith.LangSmithSecret is LangSmithSecret
    assert "LangSmithSecret" in langsmith.__all__


def test_traceable_masks_a_secret_argument(mock_client: Client):
    with tracing_context(enabled=True):

        @traceable(client=mock_client)
        def call_external_api(api_key: str, prompt: str) -> str:
            assert api_key == PLAINTEXT, "the function still sees the real key"
            return f"Response to:{prompt}"

        call_external_api(
            api_key=LangSmithSecret(PLAINTEXT), prompt="What is LangSmith?"
        )
        mock_client.flush()

    payloads = _posted_payloads(mock_client)
    _assert_masked(payloads)
    inputs = next(p["inputs"] for p in payloads if p.get("inputs"))
    assert inputs["api_key"] == LANGSMITH_SECRET_MASK
    assert inputs["prompt"] == "What is LangSmith?"


def test_traceable_masks_a_secret_returned_from_a_function(mock_client: Client):
    with tracing_context(enabled=True):

        @traceable(client=mock_client)
        def load_key() -> dict:
            return {"key": LangSmithSecret(PLAINTEXT), "model": "gpt-4o"}

        assert load_key()["key"] == PLAINTEXT
        mock_client.flush()

    payloads = _posted_payloads(mock_client)
    _assert_masked(payloads)
    outputs = next(p["outputs"] for p in payloads if p.get("outputs"))
    assert outputs == {"key": LANGSMITH_SECRET_MASK, "model": "gpt-4o"}


def test_nested_tool_headers_are_masked():
    """The hosted-MCP shape from the proposal: a key deep inside a tool spec."""
    payload = {
        "id": uuid.uuid4(),
        "trace_id": uuid.uuid4(),
        "inputs": {
            "model": "gpt-5",
            "tools": [
                {
                    "type": "mcp",
                    "server_label": "kagi",
                    "server_url": "https://mcp.kagi.com/mcp",
                    "headers": {
                        "Authorization": LangSmithSecret(f"Bearer {PLAINTEXT}")
                    },
                },
                {"type": "function", "name": "get_weather"},
            ],
            "extra_headers": {"X-Org-Token": LangSmithSecret(PLAINTEXT)},
        },
    }
    op = serialize_run_dict("post", payload)

    assert PLAINTEXT.encode() not in (op.inputs or b"")
    inputs = json.loads(op.inputs or b"{}")
    assert inputs["tools"][0]["headers"]["Authorization"] == LANGSMITH_SECRET_MASK
    assert inputs["extra_headers"]["X-Org-Token"] == LANGSMITH_SECRET_MASK
    # Everything alongside the secret is preserved.
    assert inputs["tools"][0]["server_url"] == "https://mcp.kagi.com/mcp"
    assert inputs["tools"][1] == {"type": "function", "name": "get_weather"}


@pytest.mark.parametrize("field", ["inputs", "outputs", "metadata", "error"])
def test_run_tree_masks_every_field(field: str, mock_client: Client):
    secret = LangSmithSecret(PLAINTEXT)
    # `error` is wrapped whole: interpolating a secret into a plain f-string
    # would drop the marker (see LangSmithSecret's documented limits).
    init, end = {
        "inputs": ({"inputs": {"api_key": secret}}, {"outputs": {"ok": True}}),
        "outputs": ({}, {"outputs": {"api_key": secret}}),
        "metadata": ({"extra": {"metadata": {"api_key": secret}}}, {"outputs": {}}),
        "error": ({}, {"error": LangSmithSecret(f"failed calling with {PLAINTEXT}")}),
    }[field]

    run = RunTree(name="run", run_type="chain", client=mock_client, **init)
    run.end(**end)
    run.post()
    run.patch()
    mock_client.flush()

    payloads = _posted_payloads(mock_client)
    assert payloads, "nothing was sent"
    assert PLAINTEXT not in json.dumps(payloads)


def test_secret_survives_the_regex_anonymizer():
    """A configured anonymizer must not strip the marker off a secret."""
    client = _mock_client(anonymizer=create_secret_anonymizer())
    with tracing_context(enabled=True):

        @traceable(client=client)
        def fn(api_key: str, note: str) -> str:
            return "ok"

        fn(api_key=LangSmithSecret("hunter2-not-a-known-key-format"), note="hello")
        client.flush()

    payloads = _posted_payloads(client)
    assert payloads, "nothing was sent"
    inputs = next(p["inputs"] for p in payloads if p.get("inputs"))
    # Masked by LangSmithSecret, not by the anonymizer: the token proves which.
    assert inputs["api_key"] == LANGSMITH_SECRET_MASK
    assert inputs["note"] == "hello"


def test_anonymizer_does_not_partially_rewrite_a_secret():
    """A partial regex match would write back a plain `str` and drop the marker."""
    anonymizer = create_anonymizer([{"pattern": r"proj", "replace": "X"}])
    data = {"api_key": LangSmithSecret(PLAINTEXT), "note": "sk-proj-visible"}

    result = anonymizer(data)

    assert isinstance(result["api_key"], LangSmithSecret)
    assert result["api_key"] == PLAINTEXT, "the secret is left untouched"
    assert result["note"] == "sk-X-visible", "other strings are still processed"


def test_create_dataset_masks_secret_metadata(mock_client: Client):
    mock_client.session.request.return_value = MagicMock(  # type: ignore[attr-defined]
        status_code=200,
        json=lambda: {
            "id": str(uuid.uuid4()),
            "name": "ds",
            "created_at": "2026-01-01T00:00:00Z",
        },
    )

    mock_client.create_dataset("ds", metadata={"api_key": LangSmithSecret(PLAINTEXT)})

    bodies = [
        call.kwargs["data"]
        for call in mock_client.session.request.mock_calls  # type: ignore[attr-defined]
        if call.args[:1] == ("POST",) and call.args[1].endswith("/datasets")
    ]
    assert len(bodies) == 1
    assert PLAINTEXT.encode() not in bodies[0]
    assert LANGSMITH_SECRET_MASK.encode() in bodies[0]
