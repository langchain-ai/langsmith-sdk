import asyncio
import json
from unittest import mock

import pytest
from agents import Agent, Runner, set_trace_processors

import langsmith
from langsmith.wrappers import OpenAIAgentsTracingProcessor


def _collect_trace_requests(mock_session: mock.MagicMock):
    """Collect and parse trace data from mock session requests."""
    collected_requests = {}
    mock_requests = mock_session.request.call_args_list

    for call in mock_requests:
        if json_bytes := call.kwargs.get("data"):
            json_str = json_bytes.decode("utf-8")
            collected_requests.update(json.loads(json_str))

    return collected_requests


@pytest.mark.asyncio
async def test_openai_agents_tracing_processor():
    """Test that OpenAIAgentsTracingProcessor correctly traces agent runs."""
    mock_session = mock.MagicMock()
    client = langsmith.Client(session=mock_session)

    processor = OpenAIAgentsTracingProcessor(client=client)
    set_trace_processors([processor])

    agent = Agent(
        name="Captain Obvious",
        instructions="You are Captain Obvious, the world's"
        + " most literal technical support agent.",
    )

    question = (
        "Why is my code failing when I try to divide by zero?"
        " I keep getting this error message."
    )

    result = await Runner.run(agent, question)

    # Verify we got a result
    assert result is not None
    assert hasattr(result, "final_output")
    assert result.final_output is not None

    # Give the background thread time to process traces
    await asyncio.sleep(0.5)

    # Verify that trace calls were made to the mock session
    assert mock_session.request.call_count > 0

    # Collect and verify trace data was sent
    collected_requests = _collect_trace_requests(mock_session)

    # Verify we have trace events
    all_events = [
        *collected_requests.get("post", []),
        *collected_requests.get("patch", []),
    ]

    assert len(all_events) > 0, "No trace events were recorded"

    # Verify that we have both start and end events (at least one should have end_time)
    has_start_event = any(event.get("start_time") for event in all_events)
    has_end_event = any(event.get("end_time") for event in all_events)

    assert has_start_event, "No trace start events found"
    assert has_end_event, "No trace end events found"

    # Verify trace contains expected agent information
    agent_runs = [
        event for event in all_events if event.get("name") == "Agent workflow"
    ]
    assert len(agent_runs) > 0, "No agent workflow runs found in trace"
