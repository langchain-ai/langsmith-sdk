"""Integration tests for Claude Agent SDK tracing."""

import pytest

try:
    import claude_agent_sdk

    CLAUDE_SDK_AVAILABLE = True
except ImportError:
    CLAUDE_SDK_AVAILABLE = False

from langsmith.integrations.claude_agent_sdk._hooks import _active_tool_runs

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
            "Run this exact bash command: "
            "cat /tmp/__langsmith_test_nonexistent.txt"
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
