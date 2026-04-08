"""Integration tests for Claude Agent SDK tracing."""

import pytest

try:
    import claude_agent_sdk

    CLAUDE_SDK_AVAILABLE = True
except ImportError:
    CLAUDE_SDK_AVAILABLE = False

from langsmith import traceable
from langsmith.integrations.claude_agent_sdk._hooks import (
    _active_tool_runs,
    _agent_to_tool_mapping,
    _subagent_runs,
)

pytestmark = pytest.mark.skipif(
    not CLAUDE_SDK_AVAILABLE, reason="Claude Agent SDK not installed"
)


# ── Helpers ───────────────────────────────────────────────────────────────────

_WEATHER_PROMPT = (
    "You have a get_weather tool. "
    "When the user asks about weather, call it. "
    "Only call the tool once."
)


async def _allow_all(tool_name, tool_input, context):  # type: ignore[no-untyped-def]
    return claude_agent_sdk.PermissionResultAllow(
        behavior="allow",
        updated_input=None,
        updated_permissions=None,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tool_failure_creates_error_trace():
    """Failing Bash command -> errored tool run via PostToolUseFailure."""
    from langsmith.integrations.claude_agent_sdk import (
        configure_claude_agent_sdk,
    )

    configure_claude_agent_sdk(name="test.tool_failure")

    options = claude_agent_sdk.ClaudeAgentOptions(
        permission_mode="bypassPermissions",
        allowed_tools=["Bash"],
        max_turns=2,
    )

    tool_result_blocks = []
    async with claude_agent_sdk.ClaudeSDKClient(options=options) as client:
        await client.query(
            "Run this exact bash command: cat /tmp/__langsmith_test_nonexistent.txt"
        )
        async for msg in client.receive_response():
            if type(msg).__name__ == "UserMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    if type(block).__name__ == "ToolResultBlock":
                        tool_result_blocks.append(block)

    assert len(tool_result_blocks) >= 1
    assert tool_result_blocks[0].is_error is True
    assert len(_active_tool_runs) == 0


@pytest.mark.asyncio
@pytest.mark.flaky(reruns=2)
async def test_subagent():
    """Subagent chain nested under Agent tool via live hooks."""
    from unittest.mock import patch

    from langsmith.integrations.claude_agent_sdk import (
        configure_claude_agent_sdk,
    )
    from langsmith.run_trees import RunTree

    configure_claude_agent_sdk()

    options = claude_agent_sdk.ClaudeAgentOptions(
        model="claude-haiku-4-5",
        system_prompt="You must always call the foo subagent.",
        allowed_tools=["Agent"],
        agents={
            "foo": claude_agent_sdk.AgentDefinition(
                description="Does foo things.",
                prompt=(
                    "You must first call the Bash tool with command"
                    " 'echo hello', then call the Bash tool with command"
                    " 'echo world', and then respond with"
                    " exactly: 'done'"
                ),
                model="haiku",
                tools=["Bash"],
            ),
        },
    )

    # Track all posted runs to verify hierarchy
    posted_runs: list[dict] = []
    original_post = RunTree.post

    def tracked_post(self, *args, **kwargs):
        posted_runs.append(
            {
                "name": self.name,
                "run_type": self.run_type,
                "id": str(self.id),
                "parent_run_id": str(self.parent_run_id)
                if self.parent_run_id
                else None,
            }
        )
        return original_post(self, *args, **kwargs)

    with patch.object(RunTree, "post", tracked_post):
        async with claude_agent_sdk.ClaudeSDKClient(options=options) as client:
            await client.query("Call foo.")
            async for message in client.receive_response():
                pass

    # All hook state should be cleaned up
    assert len(_active_tool_runs) == 0
    assert len(_subagent_runs) == 0
    assert len(_agent_to_tool_mapping) == 0

    # Verify the trace hierarchy was created
    run_names = [r["name"] for r in posted_runs]

    # Should have: Agent tool, foo subagent chain, Bash tools (inside subagent)
    assert "Agent" in run_names, f"Expected Agent tool run, saw: {run_names}"
    assert "foo" in run_names, f"Expected foo subagent chain run, saw: {run_names}"
    assert "Bash" in run_names, (
        f"Expected Bash tool run inside subagent, saw: {run_names}"
    )

    # Verify nesting: foo should be a child of Agent
    agent_run = next(r for r in posted_runs if r["name"] == "Agent")
    foo_run = next(r for r in posted_runs if r["name"] == "foo")
    assert foo_run["parent_run_id"] == agent_run["id"], (
        "foo subagent should be nested under Agent tool"
    )

    # Verify both Bash runs are nested under the foo subagent
    bash_runs = [
        r
        for r in posted_runs
        if r["name"] == "Bash" and r["parent_run_id"] == foo_run["id"]
    ]
    assert len(bash_runs) >= 2, (
        f"Expected at least 2 Bash tool runs under foo subagent,"
        f" saw {len(bash_runs)}: {run_names}"
    )

    # Verify LLM runs under the foo subagent.
    # The subagent makes at least 2 LLM turns (tool calls may be batched
    # into one turn by the model, plus a final response).  Only the first
    # is relayed via the stream; the rest come from the transcript.
    subagent_llm_runs = [
        r
        for r in posted_runs
        if r["name"] == "claude.assistant.turn"
        and r["run_type"] == "llm"
        and r["parent_run_id"] == foo_run["id"]
    ]
    assert len(subagent_llm_runs) >= 2, (
        f"Expected at least 2 LLM runs under foo subagent, saw"
        f" {len(subagent_llm_runs)}: {subagent_llm_runs}"
    )


@pytest.mark.asyncio
@pytest.mark.flaky(reruns=2)
async def test_continue_session():
    """Continuing a prior session should not duplicate LLM runs from old turns."""
    from unittest.mock import patch

    from langsmith.integrations.claude_agent_sdk import (
        configure_claude_agent_sdk,
    )
    from langsmith.run_trees import RunTree

    configure_claude_agent_sdk()

    options = claude_agent_sdk.ClaudeAgentOptions(
        model="claude-haiku-4-5",
        system_prompt="Answer concisely.",
        max_turns=1,
    )

    # First conversation — capture the session_id
    session_id = None
    async with claude_agent_sdk.ClaudeSDKClient(options=options) as client:
        await client.query("Say hello.")
        async for msg in client.receive_response():
            sid = getattr(msg, "session_id", None)
            if sid:
                session_id = str(sid)

    assert session_id is not None, "First conversation should produce a session_id"

    # Second conversation — resume the same session
    continue_options = claude_agent_sdk.ClaudeAgentOptions(
        model="claude-haiku-4-5",
        system_prompt="Answer concisely.",
        max_turns=1,
        resume=session_id,
    )

    posted_runs: list[dict] = []
    original_post = RunTree.post

    def tracked_post(self, *args, **kwargs):
        posted_runs.append(
            {
                "name": self.name,
                "run_type": self.run_type,
                "id": str(self.id),
                "parent_run_id": str(self.parent_run_id)
                if self.parent_run_id
                else None,
            }
        )
        return original_post(self, *args, **kwargs)

    with patch.object(RunTree, "post", tracked_post):
        async with claude_agent_sdk.ClaudeSDKClient(options=continue_options) as client:
            await client.query("Say goodbye.")
            async for msg in client.receive_response():
                pass

    assert len(_active_tool_runs) == 0

    # The continued session should only have LLM runs for the NEW
    # conversation, not duplicates from the first one.
    llm_runs = [r for r in posted_runs if r["run_type"] == "llm"]
    assert len(llm_runs) >= 1, f"Expected at least 1 LLM run, saw: {posted_runs}"
    # With max_turns=1 and no tool calls, there should be exactly 1 LLM run.
    assert len(llm_runs) == 1, (
        f"Expected exactly 1 LLM run for the continued session (no duplicates"
        f" from the first session), saw {len(llm_runs)}: {llm_runs}"
    )


@pytest.mark.asyncio
async def test_custom_tool_permission_denied():
    """MCP tool denied by default permissions -> closed from stream."""
    from langsmith.integrations.claude_agent_sdk import (
        configure_claude_agent_sdk,
    )

    configure_claude_agent_sdk(name="test.custom_tool_denied")

    @claude_agent_sdk.tool(
        "get_weather",
        "Gets the current weather for a given city.",
        {"city": str},
    )
    async def get_weather(args):  # type: ignore[no-untyped-def]
        city = args["city"]
        return {"content": [{"type": "text", "text": f"Foggy in {city}"}]}

    server = claude_agent_sdk.create_sdk_mcp_server("weather", tools=[get_weather])

    options = claude_agent_sdk.ClaudeAgentOptions(
        model="claude-haiku-4-5",
        system_prompt=_WEATHER_PROMPT,
        mcp_servers={"weather": server},
        max_turns=3,
    )

    tool_names_seen: list[str] = []
    async with claude_agent_sdk.ClaudeSDKClient(options=options) as client:
        await client.query("What's the weather in San Francisco?")
        async for msg in client.receive_response():
            if type(msg).__name__ == "AssistantMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    if type(block).__name__ == "ToolUseBlock":
                        tool_names_seen.append(block.name)

    assert any("get_weather" in n for n in tool_names_seen), (
        f"Expected get_weather tool call, saw: {tool_names_seen}"
    )
    assert len(_active_tool_runs) == 0


@pytest.mark.asyncio
async def test_custom_tool_permission_granted():
    """MCP tool granted via can_use_tool; @traceable inside handler nests."""
    from langsmith.integrations.claude_agent_sdk import (
        configure_claude_agent_sdk,
    )
    from langsmith.run_helpers import get_current_run_tree

    configure_claude_agent_sdk(name="test.custom_tool_granted")

    captured_parent_run_id = None

    @traceable
    async def inner_helper(city: str) -> str:
        nonlocal captured_parent_run_id
        rt = get_current_run_tree()
        if rt:
            captured_parent_run_id = rt.parent_run_id
        return f"Foggy in {city}"

    @claude_agent_sdk.tool(
        "get_weather",
        "Gets the current weather for a given city.",
        {"city": str},
    )
    async def get_weather(args: dict) -> dict:
        result = await inner_helper(args["city"])
        return {"content": [{"type": "text", "text": result}]}

    server = claude_agent_sdk.create_sdk_mcp_server("weather", tools=[get_weather])

    options = claude_agent_sdk.ClaudeAgentOptions(
        model="claude-haiku-4-5",
        system_prompt=_WEATHER_PROMPT,
        mcp_servers={"weather": server},
        max_turns=3,
        can_use_tool=_allow_all,
    )

    tool_names_seen: list[str] = []
    tool_results_seen: list[str] = []
    async with claude_agent_sdk.ClaudeSDKClient(options=options) as client:
        await client.query("What's the weather in San Francisco?")
        async for msg in client.receive_response():
            if type(msg).__name__ == "AssistantMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    if type(block).__name__ == "ToolUseBlock":
                        tool_names_seen.append(block.name)
            if type(msg).__name__ == "UserMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    if type(block).__name__ == "ToolResultBlock":
                        tool_results_seen.append(str(getattr(block, "content", "")))

    assert any("get_weather" in n for n in tool_names_seen), (
        f"Expected get_weather tool call, saw: {tool_names_seen}"
    )
    assert any("Foggy" in r for r in tool_results_seen), (
        f"Expected 'Foggy' in results, saw: {tool_results_seen}"
    )
    assert len(_active_tool_runs) == 0

    # @traceable inner_helper should nest under the tool run
    assert captured_parent_run_id is not None, (
        "inner_helper's parent_run_id was None — "
        "@traceable did not find a parent context"
    )
