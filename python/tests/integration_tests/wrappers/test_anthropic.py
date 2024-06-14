# mypy: disable-error-code="attr-defined, union-attr, arg-type, call-overload"
import json
from unittest import mock

import pytest

import langsmith
from langsmith.run_helpers import _TRACING_ENABLED
from langsmith.wrappers import wrap_anthropic


@pytest.fixture(autouse=True)
def enable_tracing():
    value_before = _TRACING_ENABLED.get()
    _TRACING_ENABLED.set(True)
    yield
    _TRACING_ENABLED.set(value_before)


@mock.patch("langsmith.client.requests.Session")
def test_chat_sync_api(mock_session: mock.MagicMock):
    import anthropic  # noqa
    from anthropic.types import MessageParam

    client = langsmith.Client(session=mock_session(), auto_batch_tracing=False)
    original_client = anthropic.Client()
    patched_client = wrap_anthropic(
        anthropic.Client(), tracing_extra={"client": client}
    )

    messages = [MessageParam(role="user", content="Say 'foo'")]

    original = original_client.messages.create(
        messages=messages,
        max_tokens=100,
        temperature=0,
        model="claude-3-haiku-20240307",
    )
    patched = patched_client.messages.create(
        messages=messages,
        max_tokens=100,
        temperature=0,
        model="claude-3-haiku-20240307",
    )

    assert type(original) == type(patched)
    assert original.content == patched.content

    data = _get_create_run_data(mock_session)
    assert data["name"] == "ChatAnthropic"

    metadata = data.get("extra", {}).get("metadata", {})
    assert metadata["ls_provider"] == "anthropic"
    assert metadata["ls_model_type"] == "chat"
    assert metadata["ls_temperature"] == 0
    assert metadata["ls_max_tokens"] == 100

    patch_data = _get_patch_run_data(mock_session)
    patch_output = patch_data.get("outputs", {}).get("output", {})
    assert patch_output, f"Expected 'outputs.output' in {patch_data.keys()}"

    assert patch_output["content"] == [{"type": "text", "text": "foo"}]
    assert patch_output["role"] == "assistant"
    assert patch_output["type"] == "message"
    assert patch_output["stop_reason"] == "end_turn"


@mock.patch("langsmith.client.requests.Session")
async def test_chat_async_api(mock_session: mock.MagicMock):
    from anthropic import AsyncAnthropic
    from anthropic.types import MessageParam

    client = langsmith.Client(session=mock_session(), auto_batch_tracing=False)
    original_client = AsyncAnthropic()
    patched_client = wrap_anthropic(AsyncAnthropic(), tracing_extra={"client": client})

    messages = [MessageParam(role="user", content="Say 'foo'")]

    original = await original_client.messages.create(
        messages=messages,
        max_tokens=100,
        temperature=0,
        model="claude-3-haiku-20240307",
    )
    patched = await patched_client.messages.create(
        messages=messages,
        max_tokens=100,
        temperature=0,
        model="claude-3-haiku-20240307",
    )

    assert type(original) == type(patched)
    assert original.content == patched.content

    data = _get_create_run_data(mock_session)
    assert data["name"] == "ChatAnthropic"

    metadata = data.get("extra", {}).get("metadata", {})
    assert metadata["ls_provider"] == "anthropic"
    assert metadata["ls_model_type"] == "chat"
    assert metadata["ls_temperature"] == 0
    assert metadata["ls_max_tokens"] == 100


@mock.patch("langsmith.client.requests.Session")
async def test_chat_async_stream_api(mock_session: mock.MagicMock):
    from anthropic import AsyncAnthropic
    from anthropic.types import MessageParam

    client = langsmith.Client(session=mock_session(), auto_batch_tracing=False)
    original_client = AsyncAnthropic()
    patched_client = wrap_anthropic(AsyncAnthropic(), tracing_extra={"client": client})

    messages = [MessageParam(role="user", content="Say 'foo'")]

    original = await original_client.messages.create(
        messages=messages,
        max_tokens=100,
        temperature=0,
        model="claude-3-haiku-20240307",
        stream=True,
    )
    patched = await patched_client.messages.create(
        messages=messages,
        max_tokens=100,
        temperature=0,
        model="claude-3-haiku-20240307",
        stream=True,
    )

    original_events = [event.__dict__ async for event in original]
    patched_events = [event.__dict__ async for event in patched]
    assert len(original_events) == len(patched_events)
    assert [o == p for o, p in zip(original_events, patched_events)]

    data = _get_create_run_data(mock_session)
    assert data["name"] == "ChatAnthropic"

    metadata = data.get("extra", {}).get("metadata", {})
    assert metadata["ls_provider"] == "anthropic"
    assert metadata["ls_model_type"] == "chat"
    assert metadata["ls_temperature"] == 0
    assert metadata["ls_max_tokens"] == 100

    patch_data = _get_patch_run_data(mock_session)
    patch_outputs = patch_data.get("outputs", {})
    assert patch_outputs, f"Expected 'outputs' in {patch_data.keys()}"
    assert patch_outputs["text"] == "foo"


def _get_patch_run_data(mock_session: mock.MagicMock) -> dict:
    call_args_list = mock_session.return_value.request.call_args_list
    [kwargs] = [kwargs for args, kwargs in call_args_list if args[0] == "PATCH"]

    data = json.loads(kwargs.get("data", "{}"))
    assert data, f"Expected 'data' in {kwargs.keys()}"

    return data


def _get_create_run_data(mock_session: mock.MagicMock) -> dict:
    kwargs_by_method = {
        (args[0], args[1]): kwargs
        for args, kwargs in mock_session.return_value.request.call_args_list
    }

    kwargs = kwargs_by_method.get(("POST", "https://api.smith.langchain.com/runs"), {})
    assert kwargs, f"expected POST to /runs in {list(kwargs_by_method.keys())}"

    data = json.loads(kwargs.get("data", "{}"))
    assert data, f"Expected 'data' in {kwargs.keys()}"

    return data
