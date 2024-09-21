# mypy: disable-error-code="attr-defined, union-attr, arg-type, call-overload"
import json
import time
from unittest import mock

import pytest

from langsmith import Client
from langsmith.wrappers import wrap_anthropic

model_name = "claude-3-haiku-20240307"


@mock.patch("langsmith.client.requests.Session")
@pytest.mark.parametrize("stream", [False, True])
def test_chat_sync_api(mock_session: mock.MagicMock, stream: bool):
    import anthropic  # noqa
    from tests.unit_tests.test_run_helpers import _get_calls

    mock_client = Client(session=mock_session)
    original_client = anthropic.Anthropic()
    patched_client = wrap_anthropic(
        anthropic.Anthropic(), tracing_extra={"client": mock_client}
    )
    messages = [{"role": "user", "content": "Say 'foo'"}]

    if stream:
        original = original_client.messages.stream(
            messages=messages,
            temperature=0,
            model=model_name,
            max_tokens=3,
        )
        patched = patched_client.messages.stream(
            messages=messages,
            temperature=0,
            model=model_name,
            max_tokens=3,
        )
        with original as om:
            original_chunks = list(om.text_stream)
        with patched as pm:
            patched_chunks = list(pm.text_stream)
        assert len(original_chunks) == len(patched_chunks)
        assert "".join(original_chunks) == "".join(patched_chunks)
    else:
        original = original_client.messages.create(
            messages=messages,
            temperature=0,
            model=model_name,
            max_tokens=3,
        )
        patched = patched_client.messages.create(
            messages=messages,
            temperature=0,
            model=model_name,
            max_tokens=3,
        )
        assert type(original) == type(patched)
        assert "".join([c.text for c in original.content]) == "".join(
            [c.text for c in patched.content]
        )

    calls = _get_calls(mock_client, minimum=1)
    assert calls
    datas = [json.loads(call.kwargs["data"]) for call in calls]
    outputs = None
    for data in datas:
        if outputs := data["post"][0]["outputs"]:
            break
        if data.get("patch"):
            outputs = data["patch"][0]["outputs"]
            break


@mock.patch("langsmith.client.requests.Session")
@pytest.mark.parametrize("stream", [False, True])
async def test_chat_async_api(mock_session: mock.MagicMock, stream: bool):
    import anthropic  # noqa

    original_client = anthropic.AsyncAnthropic()
    patched_client = wrap_anthropic(anthropic.AsyncAnthropic())
    messages = [{"role": "user", "content": "Say 'foo'"}]

    if stream:
        original = await original_client.messages.stream(
            messages=messages,
            temperature=0,
            model=model_name,
            max_tokens=3,
        )
        patched = await patched_client.messages.stream(
            messages=messages,
            temperature=0,
            model=model_name,
            max_tokens=3,
        )
        original_chunks = [chunk async for chunk in original]
        patched_chunks = [chunk async for chunk in patched]
        assert len(original_chunks) == len(patched_chunks)
        assert "".join([c.content[0].text for c in original_chunks]) == "".join(
            [c.content[0].text for c in patched_chunks]
        )
    else:
        original = await original_client.messages.create(
            messages=messages,
            temperature=0,
            model=model_name,
            max_tokens=3,
        )
        patched = await patched_client.messages.create(
            messages=messages,
            temperature=0,
            model=model_name,
            max_tokens=3,
        )
        assert type(original) == type(patched)
        assert "".join([c.text for c in original.content]) == "".join(
            [c.text for c in patched.content]
        )

    time.sleep(0.1)
    assert mock_session.return_value.request.call_count > 0
    for call in mock_session.return_value.request.call_args_list:
        assert call[0][0].upper() == "POST"


@mock.patch("langsmith.client.requests.Session")
@pytest.mark.parametrize("stream", [False, True])
def test_completions_sync_api(mock_session: mock.MagicMock, stream: bool):
    import anthropic

    original_client = anthropic.Anthropic()
    patched_client = wrap_anthropic(anthropic.Anthropic())
    prompt = "Human: Say 'Hi i'm Claude' then stop.\n\nAssistant:"
    original = original_client.completions.create(
        model="claude-2.1",
        prompt=prompt,
        temperature=0,
        stream=stream,
        max_tokens_to_sample=3,
    )
    patched = patched_client.completions.create(
        model="claude-2.1",
        prompt=prompt,
        temperature=0,
        stream=stream,
        max_tokens_to_sample=3,
    )
    if stream:
        original_chunks = list(original)
        patched_chunks = list(patched)
        assert len(original_chunks) == len(patched_chunks)
        assert "".join([c.completion for c in original_chunks]) == "".join(
            [c.completion for c in patched_chunks]
        )
    else:
        assert type(original) == type(patched)
        assert original.completion == patched.completion

    time.sleep(0.1)
    assert mock_session.return_value.request.call_count > 0
    for call in mock_session.return_value.request.call_args_list:
        assert call[0][0].upper() == "POST"


@mock.patch("langsmith.client.requests.Session")
@pytest.mark.parametrize("stream", [False, True])
async def test_completions_async_api(mock_session: mock.MagicMock, stream: bool):
    import anthropic

    original_client = anthropic.AsyncAnthropic()
    patched_client = wrap_anthropic(anthropic.AsyncAnthropic())
    prompt = "Human: Say 'Hi i'm Claude' then stop.\n\nAssistant:"
    original = await original_client.completions.create(
        model="claude-2.1",
        prompt=prompt,
        temperature=0,
        stream=stream,
        max_tokens_to_sample=3,
    )
    patched = await patched_client.completions.create(
        model="claude-2.1",
        prompt=prompt,
        temperature=0,
        stream=stream,
        max_tokens_to_sample=3,
    )
    if stream:
        original_chunks = [chunk async for chunk in original]
        patched_chunks = [chunk async for chunk in patched]
        assert len(original_chunks) == len(patched_chunks)
        assert "".join([c.completion for c in original_chunks]) == "".join(
            [c.completion for c in patched_chunks]
        )
    else:
        assert type(original) == type(patched)
        assert original.completion == patched.completion

    time.sleep(0.1)
    assert mock_session.return_value.request.call_count > 0
    for call in mock_session.return_value.request.call_args_list:
        assert call[0][0].upper() == "POST"
