"""Integration tests for Claude Agent SDK tracing."""

import asyncio

import pytest

try:
    import claude_agent_sdk

    CLAUDE_SDK_AVAILABLE = True
except ImportError:
    CLAUDE_SDK_AVAILABLE = False

from langsmith.integrations.claude_agent_sdk._hooks import (
    _active_tool_runs,
    _agent_to_tool_mapping,
    _subagent_runs,
)

pytestmark = pytest.mark.skipif(
    not CLAUDE_SDK_AVAILABLE, reason="Claude Agent SDK not installed"
)


@pytest.mark.asyncio
async def test_tool_failure_creates_error_trace():
    """A failing Bash command produces an errored tool run via PostToolUseFailure."""
    from langsmith.integrations.claude_agent_sdk import configure_claude_agent_sdk

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

    # PostToolUseFailure hook should have consumed the run — no orphans
    assert len(_active_tool_runs) == 0


@pytest.mark.asyncio
async def test_subagent():
    """Subagent chain is nested under Agent tool, transcript LLM turns are traced."""
    from langsmith.integrations.claude_agent_sdk import configure_claude_agent_sdk
    from langsmith.integrations.claude_agent_sdk._transcript import (
        TextBlock,
        group_into_turns,
        read_transcript,
    )

    configure_claude_agent_sdk()

    agent_transcript_path = None

    async def capture_transcript(input_data, tool_use_id, context):
        nonlocal agent_transcript_path
        agent_transcript_path = input_data.get("agent_transcript_path")
        return {}

    options = claude_agent_sdk.ClaudeAgentOptions(
        model="claude-haiku-4-5",
        system_prompt="You must always call the foo subagent.",
        allowed_tools=["Agent"],
        agents={
            "foo": claude_agent_sdk.AgentDefinition(
                description="Does foo things.",
                prompt="You must always respond with exactly: 'bar'",
                model="haiku",
                tools=[],
            ),
        },
        hooks={
            "SubagentStop": [
                claude_agent_sdk.HookMatcher(matcher=None, hooks=[capture_transcript])
            ],
        },
    )

    async with claude_agent_sdk.ClaudeSDKClient(options=options) as client:
        await client.query("Call foo.")
        async for message in client.receive_response():
            pass

    # All hook state should be cleaned up
    assert len(_active_tool_runs) == 0
    assert len(_subagent_runs) == 0
    assert len(_agent_to_tool_mapping) == 0

    # Transcript should have been captured and contain the subagent's LLM turn
    assert agent_transcript_path is not None, "SubagentStop hook did not fire"

    await asyncio.sleep(0.3)  # wait for transcript flush

    messages = read_transcript(agent_transcript_path)
    assert len(messages) >= 2, f"Expected >= 2 messages, got {len(messages)}"

    turns = group_into_turns(messages)
    assert len(turns) >= 1, f"Expected >= 1 turn, got {len(turns)}"
    assert len(turns[0].llm_calls) >= 1, "Expected >= 1 LLM call"

    llm_call = turns[0].llm_calls[0]
    assert llm_call.model == "claude-haiku-4-5"

    text_blocks = [b for b in llm_call.content if isinstance(b, TextBlock)]
    assert len(text_blocks) >= 1, "Expected >= 1 text block"


def _make_weather_server():
    """Create a reusable weather tool + MCP server for tests."""

    @claude_agent_sdk.tool(
        "get_weather",
        "Gets the current weather for a given city.",
        {"city": str},
    )
    async def get_weather(args):
        city = args["city"]
        weather = {
            "San Francisco": "Foggy, 62°F",
            "New York": "Sunny, 75°F",
        }.get(city, "Unknown")
        return {"content": [{"type": "text", "text": f"Weather in {city}: {weather}"}]}

    return claude_agent_sdk.create_sdk_mcp_server("weather", tools=[get_weather])


@pytest.mark.asyncio
async def test_custom_tool_permission_denied():
    """MCP tool denied by default permissions is closed from the stream result."""
    from langsmith.integrations.claude_agent_sdk import configure_claude_agent_sdk

    configure_claude_agent_sdk(name="test.custom_tool_denied")

    server = _make_weather_server()

    options = claude_agent_sdk.ClaudeAgentOptions(
        model="claude-haiku-4-5",
        system_prompt=(
            "You have a get_weather tool. "
            "When the user asks about weather, call it. "
            "Only call the tool once."
        ),
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

    assert any("get_weather" in name for name in tool_names_seen), (
        f"Expected get_weather tool call, saw: {tool_names_seen}"
    )
    # Run should still be cleaned up (closed from stream, not orphaned)
    assert len(_active_tool_runs) == 0


@pytest.mark.asyncio
async def test_custom_tool_permission_granted():
    """MCP tool granted via can_use_tool is traced end-to-end."""
    from langsmith.integrations.claude_agent_sdk import configure_claude_agent_sdk

    configure_claude_agent_sdk(name="test.custom_tool_granted")

    server = _make_weather_server()

    async def allow_all(tool_name, tool_input, context):
        return claude_agent_sdk.PermissionResultAllow(
            behavior="allow", updated_input=None, updated_permissions=None
        )

    options = claude_agent_sdk.ClaudeAgentOptions(
        model="claude-haiku-4-5",
        system_prompt=(
            "You have a get_weather tool. "
            "When the user asks about weather, call it. "
            "Only call the tool once."
        ),
        mcp_servers={"weather": server},
        max_turns=3,
        can_use_tool=allow_all,
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

    assert any("get_weather" in name for name in tool_names_seen), (
        f"Expected get_weather tool call, saw: {tool_names_seen}"
    )
    # Tool should have actually executed and returned a result
    assert any("Foggy" in r for r in tool_results_seen), (
        f"Expected weather result with 'Foggy', saw: {tool_results_seen}"
    )
    assert len(_active_tool_runs) == 0
