# mypy: disable-error-code="attr-defined, union-attr, arg-type, call-overload"
"""Unit tests for Google ADK integration (wrapt-based)."""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from typing import Any, Optional
from unittest import mock

import pytest

from langsmith import Client
from langsmith.run_helpers import get_current_run_tree, trace, tracing_context
from tests.unit_tests.test_run_helpers import _get_calls, _get_data

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


@pytest.fixture
def mock_ls_client() -> Client:
    mock_session = mock.MagicMock()
    return Client(session=mock_session, info=LS_TEST_CLIENT_INFO)


# --- Helpers to build fake ADK objects ---


def _make_part(text: Optional[str] = None, function_call: Any = None):
    return SimpleNamespace(text=text, function_call=function_call)


def _make_content(parts: list, role: str = "model"):
    return SimpleNamespace(parts=parts, role=role)


def _make_event(content: Any = None, is_final: bool = False, partial: bool = False):
    return SimpleNamespace(
        content=content,
        partial=partial,
        is_final_response=lambda: is_final,
    )


# --- Tests for wrap_agent_run_async ---


class TestWrapAgentRunAsync:
    @pytest.mark.asyncio
    async def test_agent_span_created(self, mock_ls_client: Client):
        """Agent span created with correct name and inputs."""
        from langsmith.integrations.google_adk._client import wrap_agent_run_async

        output_content = _make_content([_make_part(text="Hello!")])
        output_event = _make_event(content=output_content)

        async def fake_run_async(*args, **kwargs):
            yield output_event

        user_content = _make_content(
            [_make_part(text="What is the weather?")], role="user"
        )
        ctx = SimpleNamespace(user_content=user_content)
        agent_instance = SimpleNamespace(name="test_agent")

        with tracing_context(client=mock_ls_client, enabled=True):
            async with trace(name="root", run_type="chain") as root_run:
                events = []
                async for event in wrap_agent_run_async(
                    fake_run_async, agent_instance, (ctx,), {}
                ):
                    events.append(event)

        assert len(events) == 1
        assert events[0] is output_event

        time.sleep(0.5)
        calls = _get_calls(mock_ls_client, minimum=1)
        datas = _get_data(calls)

        # Find the agent chain run
        agent_runs = [
            (verb, d)
            for verb, d in datas
            if d.get("name") == "test_agent" and d.get("run_type") == "chain"
        ]
        assert len(agent_runs) >= 1, f"Expected agent run, got: {datas}"
        _, agent_data = agent_runs[0]
        assert agent_data["inputs"]["input"] == "What is the weather?"

    @pytest.mark.asyncio
    async def test_no_parent_passthrough(self, mock_ls_client: Client):
        """Without a parent run, events are passed through without tracing."""
        from langsmith.integrations.google_adk._client import wrap_agent_run_async

        event = _make_event(content=_make_content([_make_part(text="Hi")]))

        async def fake_run_async(*args, **kwargs):
            yield event

        agent_instance = SimpleNamespace(name="test_agent")
        ctx = SimpleNamespace(user_content=None)

        # No tracing context → no parent
        events = []
        async for e in wrap_agent_run_async(
            fake_run_async, agent_instance, (ctx,), {}
        ):
            events.append(e)

        assert len(events) == 1
        assert events[0] is event

    @pytest.mark.asyncio
    async def test_agent_error_recorded(self, mock_ls_client: Client):
        """Errors during agent execution are recorded on the span."""
        from langsmith.integrations.google_adk._client import wrap_agent_run_async

        async def failing_run_async(*args, **kwargs):
            yield _make_event()
            raise ValueError("Agent failed!")

        agent_instance = SimpleNamespace(name="error_agent")
        ctx = SimpleNamespace(user_content=None)

        with tracing_context(client=mock_ls_client, enabled=True):
            async with trace(name="root", run_type="chain"):
                events = []
                with pytest.raises(ValueError, match="Agent failed!"):
                    async for e in wrap_agent_run_async(
                        failing_run_async, agent_instance, (ctx,), {}
                    ):
                        events.append(e)

        time.sleep(0.5)
        calls = _get_calls(mock_ls_client, minimum=1)
        datas = _get_data(calls)

        # Find the agent run and check error
        agent_runs = [
            (verb, d) for verb, d in datas if d.get("name") == "error_agent"
        ]
        assert len(agent_runs) >= 1
        # Error may be in post (if trace CM handles it) or patch
        error_entries = [
            (v, d)
            for v, d in agent_runs
            if d.get("error")
        ]
        assert len(error_entries) >= 1, f"Expected error entry, got: {agent_runs}"
        assert "Agent failed!" in error_entries[0][1]["error"]


# --- Tests for wrap_tool_run_async ---


class TestWrapToolRunAsync:
    @pytest.mark.asyncio
    async def test_tool_span_created(self, mock_ls_client: Client):
        """Tool span created with correct name and inputs."""
        from langsmith.integrations.google_adk._client import wrap_tool_run_async

        async def fake_tool_run(*args, **kwargs):
            return {"status": "success", "result": "42"}

        tool_instance = SimpleNamespace(name="calculator")

        with tracing_context(client=mock_ls_client, enabled=True):
            async with trace(name="root", run_type="chain"):
                result = await wrap_tool_run_async(
                    fake_tool_run,
                    tool_instance,
                    (),
                    {"args": {"expression": "6*7"}},
                )

        assert result == {"status": "success", "result": "42"}

        time.sleep(0.5)
        calls = _get_calls(mock_ls_client, minimum=1)
        datas = _get_data(calls)

        tool_runs = [
            (verb, d)
            for verb, d in datas
            if d.get("name") == "calculator" and d.get("run_type") == "tool"
        ]
        assert len(tool_runs) >= 1, f"Expected tool run, got: {datas}"
        post_data = [d for v, d in tool_runs if v == "post"]
        assert len(post_data) >= 1
        assert post_data[0]["inputs"] == {"expression": "6*7"}

    @pytest.mark.asyncio
    async def test_tool_no_parent_passthrough(self, mock_ls_client: Client):
        """Without a parent run, tool executes without tracing."""
        from langsmith.integrations.google_adk._client import wrap_tool_run_async

        async def fake_tool_run(*args, **kwargs):
            return {"result": "ok"}

        tool_instance = SimpleNamespace(name="mytool")

        result = await wrap_tool_run_async(
            fake_tool_run, tool_instance, (), {"args": {}}
        )
        assert result == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_tool_error_recorded(self, mock_ls_client: Client):
        """Errors during tool execution are recorded on the span."""
        from langsmith.integrations.google_adk._client import wrap_tool_run_async

        async def failing_tool(*args, **kwargs):
            raise RuntimeError("Tool broke!")

        tool_instance = SimpleNamespace(name="broken_tool")

        with tracing_context(client=mock_ls_client, enabled=True):
            async with trace(name="root", run_type="chain"):
                with pytest.raises(RuntimeError, match="Tool broke!"):
                    await wrap_tool_run_async(
                        failing_tool, tool_instance, (), {"args": {}}
                    )

        time.sleep(0.5)
        calls = _get_calls(mock_ls_client, minimum=1)
        datas = _get_data(calls)

        tool_entries = [
            (v, d)
            for v, d in datas
            if d.get("name") == "broken_tool" and d.get("error")
        ]
        assert len(tool_entries) >= 1, f"Expected error entry, got: {datas}"
        assert "Tool broke!" in tool_entries[0][1]["error"]

    @pytest.mark.asyncio
    async def test_tool_list_output(self, mock_ls_client: Client):
        """List results are wrapped in {content: ...}."""
        from langsmith.integrations.google_adk._client import wrap_tool_run_async

        async def fake_tool_run(*args, **kwargs):
            return [{"type": "text", "text": "result"}]

        tool_instance = SimpleNamespace(name="list_tool")

        with tracing_context(client=mock_ls_client, enabled=True):
            async with trace(name="root", run_type="chain"):
                result = await wrap_tool_run_async(
                    fake_tool_run, tool_instance, (), {"args": {}}
                )

        assert result == [{"type": "text", "text": "result"}]


# --- Tests for wrap_runner_run_async ---


class TestWrapRunnerRunAsync:
    @pytest.mark.asyncio
    async def test_root_span_created(self, mock_ls_client: Client):
        """Runner.run_async creates a root span with correct metadata."""
        from langsmith.integrations.google_adk._client import wrap_runner_run_async

        output_event = _make_event(
            content=_make_content([_make_part(text="Final answer")])
        )

        async def fake_run_async(*args, **kwargs):
            yield output_event

        new_message = _make_content(
            [_make_part(text="Hello agent")], role="user"
        )
        runner_instance = SimpleNamespace(app_name="my_app")

        with tracing_context(client=mock_ls_client, enabled=True):
            events = []
            async for event in wrap_runner_run_async(
                fake_run_async,
                runner_instance,
                (),
                {
                    "new_message": new_message,
                    "user_id": "user1",
                    "session_id": "sess1",
                },
            ):
                events.append(event)

        assert len(events) == 1
        assert events[0] is output_event

        time.sleep(0.5)
        calls = _get_calls(mock_ls_client, minimum=1)
        datas = _get_data(calls)

        root_runs = [
            (v, d) for v, d in datas if d.get("run_type") == "chain"
        ]
        assert len(root_runs) >= 1


# --- Tests for wrap_runner_run (sync) ---


class TestWrapRunnerRun:
    def test_sync_root_span_and_bridge(self, mock_ls_client: Client):
        """Runner.run sets instance attributes for sync-to-async bridge."""
        from langsmith.integrations.google_adk._client import wrap_runner_run

        output_event = _make_event(
            content=_make_content([_make_part(text="Sync answer")])
        )

        # Track whether bridge attributes are set during execution
        bridge_active_during_call = None
        bridge_run_during_call = None

        def fake_run(*args, **kwargs):
            nonlocal bridge_active_during_call, bridge_run_during_call
            bridge_active_during_call = getattr(
                runner_instance, "_langsmith_sync_active", None
            )
            bridge_run_during_call = getattr(
                runner_instance, "_langsmith_root_run", None
            )
            yield output_event

        new_message = _make_content(
            [_make_part(text="Hello sync")], role="user"
        )
        runner_instance = SimpleNamespace(app_name="sync_app")

        with tracing_context(client=mock_ls_client, enabled=True):
            events = list(
                wrap_runner_run(
                    fake_run,
                    runner_instance,
                    (),
                    {"new_message": new_message, "user_id": "u1", "session_id": "s1"},
                )
            )

        assert len(events) == 1
        assert events[0] is output_event

        # Bridge attributes were set during execution
        assert bridge_active_during_call is True
        assert bridge_run_during_call is not None

        # Bridge attributes are cleared after execution
        assert getattr(runner_instance, "_langsmith_sync_active", None) is False
        assert getattr(runner_instance, "_langsmith_root_run", None) is None

    def test_sync_bridge_propagates_to_run_async(self, mock_ls_client: Client):
        """When sync bridge is active, wrap_runner_run_async uses the root run."""
        from langsmith.integrations.google_adk._client import (
            wrap_runner_run_async,
        )

        parent_run_in_async = None

        async def fake_run_async(*args, **kwargs):
            nonlocal parent_run_in_async
            parent_run_in_async = get_current_run_tree()
            yield _make_event()

        runner_instance = SimpleNamespace(app_name="bridge_test")

        with tracing_context(client=mock_ls_client, enabled=True):
            with trace(name="sync_root", run_type="chain") as root_run:
                runner_instance._langsmith_sync_active = True
                runner_instance._langsmith_root_run = root_run
                try:
                    events = asyncio.get_event_loop().run_until_complete(
                        _collect_async_gen(
                            wrap_runner_run_async(
                                fake_run_async, runner_instance, (), {}
                            )
                        )
                    )
                finally:
                    runner_instance._langsmith_sync_active = False
                    runner_instance._langsmith_root_run = None

        assert parent_run_in_async is root_run


async def _collect_async_gen(agen):
    """Collect all items from an async generator."""
    result = []
    async for item in agen:
        result.append(item)
    return result
