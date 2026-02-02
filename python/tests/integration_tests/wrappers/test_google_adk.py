# mypy: disable-error-code="attr-defined, union-attr, arg-type, call-overload"
"""Integration tests for Google ADK wrapper."""

from __future__ import annotations

import time
from typing import Dict, Optional
from unittest import mock

import pytest

from langsmith import Client
from langsmith.integrations.google_adk import configure_google_adk
from langsmith.run_helpers import tracing_context
from tests.unit_tests.test_run_helpers import _get_calls

pytest.importorskip("google.adk", reason="google-adk not installed")

MODEL_NAME = "gemini-2.0-flash"
APP_NAME = "test_app"
USER_ID = "test_user"
SESSION_ID = "test_session_123"

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


def get_weather(city: str) -> Dict[str, str]:
    """Get weather for a city. Only supports New York."""
    if city.lower() == "new york":
        return {"status": "success", "report": "Sunny, 25C in New York."}
    return {"status": "error", "error_message": f"Weather for '{city}' unavailable."}


@pytest.fixture
def mock_ls_client() -> Client:
    """Create a mock LangSmith client."""
    mock_session = mock.MagicMock()
    return Client(session=mock_session, info=LS_TEST_CLIENT_INFO)


def _build_runner(agent, sync: bool = True):
    """Build a runner with in-memory session."""
    from google.adk import runners, sessions

    session_service = sessions.InMemorySessionService()
    if sync:
        session_service.create_session_sync(
            app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
        )
    return runners.Runner(
        agent=agent, app_name=APP_NAME, session_service=session_service
    )


async def _build_runner_async(agent):
    """Build an async runner with in-memory session."""
    from google.adk import runners, sessions

    session_service = sessions.InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    return runners.Runner(
        agent=agent, app_name=APP_NAME, session_service=session_service
    )


def _extract_response(events) -> Optional[str]:
    """Extract final response text from events."""
    for event in reversed(list(events)):
        if getattr(event, "is_final_response", lambda: False)():
            content = getattr(event, "content", None)
            if content and getattr(content, "parts", None):
                for part in content.parts:
                    if text := getattr(part, "text", None):
                        return text
    return None


async def _extract_response_async(events) -> Optional[str]:
    """Extract final response text from async events."""
    events_list = [e async for e in events]
    for event in reversed(events_list):
        if getattr(event, "is_final_response", lambda: False)():
            content = getattr(event, "content", None)
            if content and getattr(content, "parts", None):
                for part in content.parts:
                    if text := getattr(part, "text", None):
                        return text
    return None


def test_runner_run_sync_with_tool(mock_ls_client: Client):
    """Test that Runner.run creates traces for sync execution with tool calls."""
    from google.adk import agents
    from google.genai import types

    configure_google_adk(
        name="test_sync",
        project_name="test_project",
        metadata={"env": "test"},
        tags=["integration"],
    )

    with tracing_context(client=mock_ls_client, enabled=True):
        agent = agents.Agent(
            name="weather_agent",
            model=MODEL_NAME,
            description="Provides weather info.",
            instruction="Use get_weather tool. Only New York is supported.",
            tools=[get_weather],
        )

        runner = _build_runner(agent)
        events = runner.run(
            user_id=USER_ID,
            session_id=SESSION_ID,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text="What is the weather in New York?")],
            ),
        )

        response = _extract_response(events)
        assert response is not None

    time.sleep(0.2)
    calls = _get_calls(mock_ls_client, minimum=1)
    assert len(calls) > 0, "Expected trace calls to be made"


@pytest.mark.asyncio
async def test_runner_run_async(mock_ls_client: Client):
    """Test that Runner.run_async creates traces for async execution."""
    from google.adk import agents
    from google.genai import types

    configure_google_adk(name="test_async", tags=["async"])

    with tracing_context(client=mock_ls_client, enabled=True):
        agent = agents.Agent(
            name="async_agent",
            model=MODEL_NAME,
            description="Async weather agent.",
            tools=[get_weather],
        )

        runner = await _build_runner_async(agent)
        events = runner.run_async(
            user_id=USER_ID,
            session_id=SESSION_ID,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text="What is the weather in New York?")],
            ),
        )

        response = await _extract_response_async(events)
        assert response is not None

    time.sleep(0.2)
    calls = _get_calls(mock_ls_client, minimum=1)
    assert len(calls) > 0, "Expected trace calls for async execution"


def test_sequential_agent(mock_ls_client: Client):
    """Test that sequential agents with sub-agents are traced."""
    from google.adk import agents
    from google.genai import types

    configure_google_adk(name="sequential_test")

    with tracing_context(client=mock_ls_client, enabled=True):
        translator = agents.Agent(
            name="Translator", model=MODEL_NAME, description="Translates to English."
        )
        summarizer = agents.Agent(
            name="Summarizer", model=MODEL_NAME, description="Summarizes text."
        )
        root = agents.SequentialAgent(
            name="TextProcessor",
            sub_agents=[translator, summarizer],
            description="Translates then summarizes.",
        )

        runner = _build_runner(root)
        events = runner.run(
            user_id=USER_ID,
            session_id=SESSION_ID,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text="Hallo, wie geht es dir?")],
            ),
        )

        response = _extract_response(events)
        assert response is not None

    time.sleep(0.2)
    calls = _get_calls(mock_ls_client, minimum=1)
    assert len(calls) > 0
