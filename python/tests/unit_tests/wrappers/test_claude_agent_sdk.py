from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest import mock

import pytest

from langsmith import Client
from langsmith.integrations.claude_agent_sdk._client import (
    LLM_RUN_NAME,
    TRACE_CHAIN_NAME,
    instrument_claude_client,
)
from langsmith.run_helpers import tracing_context
from tests.unit_tests.test_run_helpers import _get_calls

LS_TEST_CLIENT_INFO = {
    "batch_ingest_config": {
        "use_multipart_endpoint": False,
        "scale_up_qsize_trigger": 1000,
        "scale_up_nthreads_limit": 16,
        "scale_down_nempty_trigger": 4,
        "size_limit": 100,
        "size_limit_bytes": 20971520,
    },
}

# ---------------------------------------------------------------------------
# Mock message / content-block types
# (The integration dispatches on type(msg).__name__, so class names matter.)
# ---------------------------------------------------------------------------


class TextBlock:
    def __init__(self, text: str) -> None:
        self.text = text


class ToolUseBlock:
    def __init__(self, id: str, name: str, input: dict) -> None:
        self.id = id
        self.name = name
        self.input = input


class ToolResultBlock:
    def __init__(self, tool_use_id: str, content: str, is_error: bool = False) -> None:
        self.tool_use_id = tool_use_id
        self.content = content
        self.is_error = is_error


class AssistantMessage:
    def __init__(
        self,
        content: list,
        model: str = "claude-3-5-sonnet-20241022",
        parent_tool_use_id: str | None = None,
    ) -> None:
        self.content = content
        self.model = model
        self.parent_tool_use_id = parent_tool_use_id


class UserMessage:
    def __init__(self, content: list) -> None:
        self.content = content


class ResultMessage:
    def __init__(
        self,
        usage: Any = None,
        total_cost_usd: float | None = None,
        num_turns: int | None = None,
        session_id: str | None = None,
        is_error: bool = False,
    ) -> None:
        self.usage = usage
        self.total_cost_usd = total_cost_usd
        self.num_turns = num_turns
        self.session_id = session_id
        self.is_error = is_error


# ---------------------------------------------------------------------------
# Scripted conversation: one tool call + final answer
# ---------------------------------------------------------------------------

WEATHER_CONVERSATION = [
    AssistantMessage(
        content=[
            ToolUseBlock(id="tool_1", name="get_weather", input={"location": "NYC"}),
        ],
    ),
    UserMessage(
        content=[
            ToolResultBlock(tool_use_id="tool_1", content="Sunny, 72°F"),
        ],
    ),
    AssistantMessage(
        content=[
            TextBlock(text="The weather in NYC is sunny and 72°F."),
        ],
    ),
    ResultMessage(num_turns=2, session_id="sess-abc123"),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_base_client(scripted_messages: list) -> type:
    """Return a minimal base-class that replays *scripted_messages*.

    For UserMessage entries that contain tool results, pre_tool_use_hook and
    post_tool_use_hook are fired before the message is yielded, reproducing
    the hook sequence the Claude Agent SDK CLI performs in production.
    """
    from unittest.mock import MagicMock

    from langsmith.integrations.claude_agent_sdk._hooks import (
        post_tool_use_hook,
        pre_tool_use_hook,
    )

    # Build tool_use_id → tool_name so hooks receive meaningful metadata.
    tool_names: dict[str, str] = {}
    for msg in scripted_messages:
        if type(msg).__name__ == "AssistantMessage":
            for block in getattr(msg, "content", []):
                if type(block).__name__ == "ToolUseBlock":
                    tool_names[block.id] = block.name

    class _BaseMockClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.options = kwargs.get("options", None)

        async def query(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def receive_response(self):  # async generator
            for msg in scripted_messages:
                if type(msg).__name__ == "UserMessage":
                    for block in getattr(msg, "content", []):
                        if type(block).__name__ == "ToolResultBlock":
                            tid = block.tool_use_id
                            ctx = MagicMock()
                            await pre_tool_use_hook(
                                {
                                    "tool_name": tool_names.get(tid, "unknown_tool"),
                                    "tool_input": {},
                                },
                                tid,
                                ctx,
                            )
                            await post_tool_use_hook(
                                {
                                    "tool_name": tool_names.get(tid, "unknown_tool"),
                                    "tool_response": {"output": block.content},
                                },
                                tid,
                                ctx,
                            )
                yield msg

        async def __aenter__(self) -> "_BaseMockClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

    return _BaseMockClient


@pytest.fixture
def mock_ls_client() -> Client:
    mock_session = mock.MagicMock()
    return Client(session=mock_session, info=LS_TEST_CLIENT_INFO)


def _collect_runs(mock_ls_client: Client) -> list[dict[str, Any]]:
    """Collect all run dicts, merging POST and PATCH payloads by run ID."""
    runs_by_id: dict[str, dict[str, Any]] = {}
    for call in _get_calls(mock_ls_client, minimum=0):
        data = call.kwargs.get("data")
        if not isinstance(data, (bytes, bytearray)):
            continue
        try:
            payload = json.loads(data.decode("utf-8"))
        except Exception:
            continue
        for run in payload.get("post") or []:
            run_id = run.get("id")
            if run_id:
                runs_by_id.setdefault(run_id, {}).update(run)
        for run in payload.get("patch") or []:
            run_id = run.get("id")
            if run_id:
                runs_by_id.setdefault(run_id, {}).update(run)
    return list(runs_by_id.values())


def _find_run(runs: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for run in runs:
        if run.get("name") == name:
            return run
    raise AssertionError(
        f"Run '{name}' not found. Present: {[r.get('name') for r in runs]}"
    )


def _find_all_runs(runs: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    return [r for r in runs if r.get("name") == name]


async def _run_conversation(
    scripted_messages: list,
    mock_ls_client: Client,
    prompt: str = "What's the weather in NYC?",
) -> list[dict[str, Any]]:
    BaseCls = _make_base_client(scripted_messages)
    InstrumentedCls = instrument_claude_client(BaseCls)
    with tracing_context(client=mock_ls_client, enabled=True):
        async with InstrumentedCls() as client:
            await client.query(prompt)
            async for _ in client.receive_response():
                pass
    mock_ls_client.flush()
    return _collect_runs(mock_ls_client)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_root_run_inputs_contain_prompt(mock_ls_client: Client) -> None:
    """Root run inputs should record the user's prompt string."""
    runs = asyncio.run(
        _run_conversation(
            WEATHER_CONVERSATION,
            mock_ls_client,
            prompt="What's the weather in NYC?",
        )
    )
    root_run = _find_run(runs, TRACE_CHAIN_NAME)
    inputs = root_run.get("inputs") or {}
    assert inputs.get("prompt") == "What's the weather in NYC?"


def test_root_run_has_no_error(mock_ls_client: Client) -> None:
    """Root run should complete without error for a normal conversation."""
    runs = asyncio.run(_run_conversation(WEATHER_CONVERSATION, mock_ls_client))
    root_run = _find_run(runs, TRACE_CHAIN_NAME)
    assert not root_run.get("error"), root_run


def test_llm_child_run_has_inputs_messages(mock_ls_client: Client) -> None:
    """LLM child runs (claude.assistant.turn) should be created with inputs.messages."""
    runs = asyncio.run(_run_conversation(WEATHER_CONVERSATION, mock_ls_client))
    llm_runs = _find_all_runs(runs, LLM_RUN_NAME)
    assert llm_runs, "At least one claude.assistant.turn LLM run must exist"
    for llm_run in llm_runs:
        inputs = llm_run.get("inputs") or {}
        assert "messages" in inputs, f"LLM child run missing inputs.messages: {llm_run}"


def test_root_run_outputs_messages_contains_full_conversation(
    mock_ls_client: Client,
) -> None:
    """Root run outputs.__LS_INTERNAL_UNSTABLE_MESSAGES must contain the full
    conversation history. For backwards compatibility, the last assistant turn's content
    and role are also available at the top level of outputs.
    """
    runs = asyncio.run(_run_conversation(WEATHER_CONVERSATION, mock_ls_client))
    root_run = _find_run(runs, TRACE_CHAIN_NAME)
    outputs = root_run.get("outputs") or {}

    messages = outputs.get("__LS_INTERNAL_UNSTABLE_MESSAGES")
    assert messages is not None, (
        "Root run outputs must have a 'messages' key with the full conversation. "
        f"Actual outputs: {outputs}"
    )
    assert isinstance(messages, list), (
        f"outputs.messages must be a list, got {type(messages)}"
    )

    # user prompt + assistant (tool_use) + tool result + assistant (final answer)
    assert len(messages) == 4, (
        f"Expected 4 messages (user + assistant tool_use + tool + assistant final), "
        f"got {len(messages)}: {messages}"
    )
    assert messages[0]["role"] == "user", f"First message should be user: {messages[0]}"
    assert messages[0]["content"] == "What's the weather in NYC?"
    assert messages[-1]["role"] == "assistant", (
        f"Last message should be assistant: {messages[-1]}"
    )

    # Backwards compat: last assistant turn exposed at top level.
    assert outputs.get("role") == "assistant", (
        f"outputs.role must be 'assistant' for backwards compat: {outputs}"
    )
    assert "content" in outputs, (
        f"outputs.content must be present for backwards compat: {outputs}"
    )


def test_messages_have_run_id_linking_to_child_runs(
    mock_ls_client: Client,
) -> None:
    """Assistant and tool messages in outputs.__LS_INTERNAL_UNSTABLE_MESSAGES
    must carry a 'run_id' equal to their corresponding child run's id.
    User prompt messages must not have 'run_id'.
    """
    runs = asyncio.run(_run_conversation(WEATHER_CONVERSATION, mock_ls_client))

    llm_run_ids = {r["id"] for r in _find_all_runs(runs, LLM_RUN_NAME) if r.get("id")}
    assert llm_run_ids, "Expected at least one claude.assistant.turn run with an id"

    tool_run_ids = {
        r["id"] for r in runs if r.get("run_type") == "tool" and r.get("id")
    }
    assert tool_run_ids, "Expected at least one tool run with an id"

    root_run = _find_run(runs, TRACE_CHAIN_NAME)
    messages = (root_run.get("outputs") or {}).get(
        "__LS_INTERNAL_UNSTABLE_MESSAGES", []
    )

    for msg in messages:
        role = msg.get("role")
        if role == "assistant":
            assert "run_id" in msg, f"Assistant message missing 'run_id': {msg}"
            assert msg["run_id"] in llm_run_ids, (
                f"Assistant message run_id {msg['run_id']!r} does not match any "
                f"claude.assistant.turn run id. Known ids: {llm_run_ids}"
            )
        elif role == "tool":
            assert "run_id" in msg, f"Tool message missing 'run_id': {msg}"
            assert msg["run_id"] in tool_run_ids, (
                f"Tool message run_id {msg['run_id']!r} does not match any "
                f"tool run id. Known ids: {tool_run_ids}"
            )
        else:
            assert "run_id" not in msg, (
                f"User prompt message should not have 'run_id': {msg}"
            )


def test_llm_child_runs_do_not_have_messages_in_outputs(
    mock_ls_client: Client,
) -> None:
    """LLM child runs must NOT have '__LS_INTERNAL_UNSTABLE_MESSAGES' in their outputs.

    Only the root claude.conversation run should expose
    outputs.__LS_INTERNAL_UNSTABLE_MESSAGES.
    """
    runs = asyncio.run(_run_conversation(WEATHER_CONVERSATION, mock_ls_client))
    llm_runs = _find_all_runs(runs, LLM_RUN_NAME)
    assert llm_runs, "At least one claude.assistant.turn LLM run must exist"
    for llm_run in llm_runs:
        outputs = llm_run.get("outputs") or {}
        assert "__LS_INTERNAL_UNSTABLE_MESSAGES" not in outputs, (
            f"LLM child run must NOT have __LS_INTERNAL_UNSTABLE_MESSAGES: {llm_run}"
        )
