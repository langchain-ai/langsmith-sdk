"""Unit tests for Google ADK wrapper tracing with dummy agents."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest import mock

import pytest
from pydantic import Field

from langsmith import Client
from langsmith.integrations.google_adk import configure_google_adk
from langsmith.run_helpers import trace, tracing_context
from tests.unit_tests.test_run_helpers import _get_calls

APP_NAME = "test_app"
USER_ID = "test_user"
SESSION_ID = "test_session_123"
ROOT_TRACE_NAME = "unit_root"
PROJECT_NAME = "test_project"

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


class EchoAgent:
    """Emit one final text event."""

    pass


class PipelineAgent:
    """Run sub agents sequentially."""

    pass


class ErrorAgent:
    """Raise an error from async generator body."""

    pass


def _build_dummy_agents():
    from google.adk.agents.base_agent import BaseAgent
    from google.adk.events.event import Event
    from google.genai import types

    class _EchoAgent(BaseAgent):
        output_text: str = Field(default="echo")

        async def _run_async_impl(self, ctx):
            yield Event(
                invocation_id=ctx.invocation_id,
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=self.output_text)],
                ),
            )

    class _PipelineAgent(BaseAgent):
        async def _run_async_impl(self, ctx):
            for child in self.sub_agents:
                async for event in child.run_async(ctx):
                    yield event

    class _ErrorAgent(BaseAgent):
        async def _run_async_impl(self, ctx):
            if False:
                yield None
            raise RuntimeError("boom")

    return _EchoAgent, _PipelineAgent, _ErrorAgent


@pytest.fixture
def mock_ls_client() -> Client:
    mock_session = mock.MagicMock()
    return Client(session=mock_session, info=LS_TEST_CLIENT_INFO)


def _build_runner_sync(agent):
    from google.adk import runners, sessions

    session_service = sessions.InMemorySessionService()
    session_service.create_session_sync(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    return runners.Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=session_service,
    )


async def _build_runner_async(agent):
    from google.adk import runners, sessions

    session_service = sessions.InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    return runners.Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=session_service,
    )


def _collect_runs(mock_ls_client: Client) -> list[dict[str, Any]]:
    runs_by_id: dict[str, dict[str, Any]] = {}
    for call in _get_calls(mock_ls_client, minimum=0):
        data = call.kwargs.get("data")
        if not isinstance(data, (bytes, bytearray)):
            continue
        try:
            payload = json.loads(data.decode("utf-8"))
        except Exception:
            continue
        for run in [*(payload.get("post") or []), *(payload.get("patch") or [])]:
            run_id = run.get("id")
            if run_id and run_id in runs_by_id:
                runs_by_id[run_id].update(
                    {k: v for k, v in run.items() if v is not None}
                )
            elif run_id:
                runs_by_id[run_id] = run
    return list(runs_by_id.values())


def _find_run(runs: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for run in runs:
        if run.get("name") == name:
            return run
    raise AssertionError(
        f"Run '{name}' not found. Present: {[r.get('name') for r in runs]}"
    )


def _extract_response(events) -> str | None:
    for event in reversed(list(events)):
        if getattr(event, "is_final_response", lambda: False)():
            content = getattr(event, "content", None)
            if content and getattr(content, "parts", None):
                for part in content.parts:
                    if text := getattr(part, "text", None):
                        return text
    return None


async def _extract_response_async(events) -> str | None:
    all_events = [event async for event in events]
    for event in reversed(all_events):
        if getattr(event, "is_final_response", lambda: False)():
            content = getattr(event, "content", None)
            if content and getattr(content, "parts", None):
                for part in content.parts:
                    if text := getattr(part, "text", None):
                        return text
    return None


def _assert_required_ls_fields(run: dict[str, Any]) -> None:
    assert run.get("id"), run
    assert run.get("name"), run
    assert run.get("run_type"), run
    assert run.get("trace_id"), run
    assert run.get("dotted_order"), run
    assert run.get("start_time"), run
    assert run.get("end_time"), run
    metadata = (run.get("extra") or {}).get("metadata") or {}
    for key in ("ls_provider", "app_name", "user_id", "session_id"):
        assert metadata.get(key), (key, run)
    assert metadata.get("ls_integration") == "google-adk", run
    assert "ls_integration_version" in metadata, run


def _run_agent(mode: str, agent, mock_ls_client: Client, input_text: str = "hello"):
    from google.genai import types

    configure_google_adk(name=ROOT_TRACE_NAME, project_name=PROJECT_NAME)

    with tracing_context(client=mock_ls_client, enabled=True):
        if mode == "sync":
            runner = _build_runner_sync(agent)
            events = runner.run(
                user_id=USER_ID,
                session_id=SESSION_ID,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part(text=input_text)],
                ),
            )
            response_text = _extract_response(events)
        else:

            async def _run():
                runner = await _build_runner_async(agent)
                events = runner.run_async(
                    user_id=USER_ID,
                    session_id=SESSION_ID,
                    new_message=types.Content(
                        role="user",
                        parts=[types.Part(text=input_text)],
                    ),
                )
                return await _extract_response_async(events)

            response_text = asyncio.run(_run())

    mock_ls_client.flush()
    return response_text, _collect_runs(mock_ls_client)


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_simple_agent_sync_async_inputs_outputs_and_ls_fields(
    mode: str, mock_ls_client: Client
):
    EchoCls, _, _ = _build_dummy_agents()
    response, runs = _run_agent(
        mode,
        EchoCls(name="echo_agent", description="Echo agent", output_text="echo-out"),
        mock_ls_client,
        input_text="hello",
    )

    root_run = _find_run(runs, ROOT_TRACE_NAME)
    child_run = _find_run(runs, "echo_agent")

    assert response == "echo-out"
    assert child_run.get("inputs", {}).get("input") == "hello"
    assert child_run.get("outputs", {}).get("output") == "echo-out"
    assert not root_run.get("error")
    assert not child_run.get("error")
    _assert_required_ls_fields(root_run)


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_sequential_agent_sync_async_inputs_outputs_no_errors(
    mode: str, mock_ls_client: Client
):
    EchoCls, PipelineCls, _ = _build_dummy_agents()
    pipeline = PipelineCls(
        name="pipeline",
        description="pipeline",
        sub_agents=[
            EchoCls(
                name="translator",
                description="translator",
                output_text="hello-en",
            ),
            EchoCls(
                name="summarizer",
                description="summarizer",
                output_text="summary",
            ),
        ],
    )

    _, runs = _run_agent(mode, pipeline, mock_ls_client, input_text="bonjour")

    root_run = _find_run(runs, ROOT_TRACE_NAME)
    pipeline_run = _find_run(runs, "pipeline")
    translator_run = _find_run(runs, "translator")
    summarizer_run = _find_run(runs, "summarizer")

    assert pipeline_run.get("parent_run_id") == root_run.get("id")
    assert translator_run.get("parent_run_id") == pipeline_run.get("id")
    assert summarizer_run.get("parent_run_id") == pipeline_run.get("id")

    assert translator_run.get("inputs", {}).get("input") == "bonjour"
    assert translator_run.get("outputs", {}).get("output") == "hello-en"
    assert summarizer_run.get("inputs", {}).get("input") == "hello-en"
    assert summarizer_run.get("outputs", {}).get("output") == "summary"

    for run in (root_run, pipeline_run, translator_run, summarizer_run):
        assert not run.get("error"), run


def _build_llm_agent_with_before_callback(injected_instruction: str):
    """Build an LlmAgent backed by a fake model with a before_model_callback.

    The callback mutates ``llm_request`` in place (as real ADK plugins do via
    ``llm_request.append_instructions(...)``) inside ``_call_llm_async``, after
    the LangSmith wrapper has already created the LLM run.
    """
    from google.adk.agents import LlmAgent
    from google.adk.models.base_llm import BaseLlm
    from google.adk.models.llm_response import LlmResponse
    from google.genai import types

    class _FakeLlm(BaseLlm):
        model: str = "fake-model"

        async def generate_content_async(self, llm_request, stream=False):
            # Echo the system instruction so we can confirm the model received it.
            sys_inst = ""
            if getattr(llm_request, "config", None):
                sys_inst = str(llm_request.config.system_instruction or "")
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=f"ok::{sys_inst}")],
                )
            )

    def _before_model(callback_context, llm_request):
        llm_request.append_instructions([injected_instruction])
        return None

    return LlmAgent(
        name="haiku_agent",
        model=_FakeLlm(),
        description="agent with before_model_callback",
        before_model_callback=_before_model,
    )


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_before_model_callback_mutations_reflected_in_llm_inputs(
    mode: str, mock_ls_client: Client
):
    """LLM run inputs must reflect before_model_callback mutations (LSDK-279).

    ADK runs before_model_callback inside ``_call_llm_async`` and lets it mutate
    ``llm_request`` in place. The wrapper must capture inputs *after* those
    callbacks run, otherwise injected instructions never appear in the trace.
    """
    injected = "Always respond in Haiku."
    agent = _build_llm_agent_with_before_callback(injected)

    response, runs = _run_agent(mode, agent, mock_ls_client, input_text="hi")

    # Sanity check: the model actually received the injected instruction.
    assert response is not None and injected in response

    llm_run = next((r for r in runs if r.get("run_type") == "llm"), None)
    assert llm_run is not None, (
        f"No LLM run found. Present: {[r.get('name') for r in runs]}"
    )

    messages = (llm_run.get("inputs") or {}).get("messages") or []
    system_text = " ".join(
        str(m.get("content") or "") for m in messages if m.get("role") == "system"
    )
    assert injected in system_text, (
        f"Injected instruction missing from LLM inputs. messages={messages}"
    )


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_error_agent_sync_async_records_errors(mode: str, mock_ls_client: Client):
    _, _, ErrorCls = _build_dummy_agents()

    if mode == "async":
        with pytest.raises(RuntimeError, match="boom"):
            _run_agent(
                mode,
                ErrorCls(name="error_agent", description="error agent"),
                mock_ls_client,
                input_text="hello",
            )
    else:
        _run_agent(
            mode,
            ErrorCls(name="error_agent", description="error agent"),
            mock_ls_client,
            input_text="hello",
        )

    runs = _collect_runs(mock_ls_client)
    assert any(run.get("error") for run in runs), runs
    assert any("boom" in (run.get("error") or "") for run in runs), runs


def test_wrap_tool_run_async_sets_tool_as_active_context(mock_ls_client: Client):
    """get_current_run_tree() inside a tool body must return the tool span."""
    from langsmith.integrations.google_adk._client import wrap_tool_run_async
    from langsmith.run_helpers import get_current_run_tree

    captured_run_id = None

    async def _fake_body(*args, **kwargs):
        nonlocal captured_run_id
        run = get_current_run_tree()
        if run:
            captured_run_id = str(run.id)
        return {"output": "ok"}

    class _FakeTool:
        name = "test_tool"

    async def _run():
        with tracing_context(client=mock_ls_client, enabled=True):
            with trace("parent", run_type="chain"):
                await wrap_tool_run_async(
                    wrapped=_fake_body,
                    instance=_FakeTool(),
                    args=({"query": "hello"},),
                    kwargs={},
                )

    asyncio.run(_run())
    mock_ls_client.flush()

    runs = _collect_runs(mock_ls_client)
    tool_run = _find_run(runs, "test_tool")

    assert captured_run_id is not None, (
        "get_current_run_tree() returned None inside tool body"
    )
    assert captured_run_id == tool_run["id"], (
        f"Expected active context inside tool to be the tool span "
        f"({tool_run['id']}), got {captured_run_id}"
    )


def _tool_call_request(*calls: tuple[str | None, str | None], name: str = "weather"):
    """Build an LlmRequest of one tool call and its response per (call, result) id."""
    from google.adk.models.llm_request import LlmRequest
    from google.genai import types

    contents = []
    for call_id, result_id in calls:
        contents.append(
            types.Content(
                role="model",
                parts=[
                    types.Part(
                        function_call=types.FunctionCall(
                            id=call_id, name=name, args={"city": "Haifa"}
                        )
                    )
                ],
            )
        )
        contents.append(
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        function_response=types.FunctionResponse(
                            id=result_id, name=name, response={"c": 29}
                        )
                    )
                ],
            )
        )
    return LlmRequest(contents=contents)


def _call_and_result_ids(llm_request):
    from langsmith.integrations.google_adk._messages import (
        convert_llm_request_to_messages,
    )

    messages = convert_llm_request_to_messages(llm_request)
    return (
        [m["tool_calls"][0]["id"] for m in messages if m.get("tool_calls")],
        [m.get("tool_call_id") for m in messages if m["role"] == "tool"],
    )


def test_tool_messages_pair_with_the_ids_adk_assigned():
    """When ADK keeps its ids, a tool message carries the id of the call it answers."""
    calls, results = _call_and_result_ids(
        _tool_call_request(("adk-1111", "adk-1111"), ("adk-2222", "adk-2222"))
    )

    assert calls == ["adk-1111", "adk-2222"]
    assert results == calls


def test_tool_messages_pair_when_adk_strips_its_ids():
    """The default Gemini path: ADK strips every ``adk-`` id before the request.

    Pinned to ADK's own stripping rather than a hand-built request, because this,
    not the branch above, is what a plain ``Gemini`` agent produces.
    """
    from google.adk.flows.llm_flows.functions import (
        generate_client_function_call_id,
        remove_client_function_call_id,
    )

    minted = [generate_client_function_call_id() for _ in range(2)]
    llm_request = _tool_call_request(*((call_id, call_id) for call_id in minted))
    for content in llm_request.contents:
        remove_client_function_call_id(content)

    calls, results = _call_and_result_ids(llm_request)

    assert all(call_id is None for call_id in _raw_part_ids(llm_request)), (
        "ADK no longer strips its ids; the fallback is no longer the primary path"
    )
    assert len(set(calls)) == 2, calls
    assert results == calls


def _raw_part_ids(llm_request):
    ids = []
    for content in llm_request.contents:
        for part in content.parts:
            fc, fr = part.function_call, part.function_response
            ids.append(fc.id if fc else fr.id)
    return ids


@pytest.mark.parametrize(
    "ids, expected_calls, expected_results",
    [
        # A provider id on one side is carried over to the other.
        ([("call_abc", None)], ["call_abc"], ["call_abc"]),
        # Except the other way round: nothing links the two, so they stay apart.
        ([(None, "call_abc")], ["ls-adk-0"], ["call_abc"]),
        # A synthesised id must not collide with a real one.
        (
            [(None, None), ("call_0", "call_0")],
            ["ls-adk-0", "call_0"],
            ["ls-adk-0", "call_0"],
        ),
    ],
    ids=["call-id-only", "result-id-only", "no-collision"],
)
def test_partial_tool_call_ids(ids, expected_calls, expected_results):
    """An id present on one side only must not mis-pair the other."""
    calls, results = _call_and_result_ids(_tool_call_request(*ids))

    assert calls == expected_calls
    assert results == expected_results


def test_orphan_tool_result_gets_no_id():
    """A result with no call to answer gets no id rather than an invented one."""
    llm_request = _tool_call_request((None, None))
    llm_request.contents = [c for c in llm_request.contents if c.role != "model"]

    calls, results = _call_and_result_ids(llm_request)

    assert calls == []
    assert results == [None]
