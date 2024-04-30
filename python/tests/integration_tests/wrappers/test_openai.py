# mypy: disable-error-code="attr-defined, union-attr, arg-type, call-overload"
import time
from unittest import mock

import pytest

from langsmith.wrappers import wrap_openai


@mock.patch("langsmith.client.requests.Session")
@pytest.mark.parametrize("stream", [False, True])
def test_chat_sync_api(mock_session: mock.MagicMock, stream: bool):
    import openai  # noqa

    original_client = openai.Client()
    patched_client = wrap_openai(
        openai.Client(), tracing_extra={"name": "sync chat completions"}
    )
    messages = [{"role": "user", "content": "Say 'foo'"}]
    original = original_client.chat.completions.create(
        messages=messages,  # noqa: [arg-type]
        stream=stream,
        temperature=0,
        seed=42,
        model="gpt-3.5-turbo",
    )
    patched = patched_client.chat.completions.create(
        messages=messages,  # noqa: [arg-type]
        stream=stream,
        temperature=0,
        seed=42,
        model="gpt-3.5-turbo",
    )
    if stream:
        # We currently return a generator, so
        # the types aren't the same.
        original_chunks = list(original)
        patched_chunks = list(patched)
        assert len(original_chunks) == len(patched_chunks)
        assert [o.choices == p.choices for o, p in zip(original_chunks, patched_chunks)]
    else:
        assert type(original) == type(patched)
        assert original.choices == patched.choices
    # Give the thread a chance.
    time.sleep(0.01)
    for call in mock_session.return_value.request.call_args_list:
        assert call[0][0].upper() == "POST"


@mock.patch("langsmith.client.requests.Session")
@pytest.mark.parametrize("stream", [False, True])
async def test_chat_async_api(mock_session: mock.MagicMock, stream: bool):
    import openai  # noqa

    original_client = openai.AsyncClient()
    patched_client = wrap_openai(
        openai.AsyncClient(), tracing_extra={"name": "some chat completions"}
    )
    messages = [{"role": "user", "content": "Say 'foo'"}]
    original = await original_client.chat.completions.create(
        messages=messages, stream=stream, temperature=0, seed=42, model="gpt-3.5-turbo"
    )
    patched = await patched_client.chat.completions.create(
        messages=messages, stream=stream, temperature=0, seed=42, model="gpt-3.5-turbo"
    )
    if stream:
        # We currently return a generator, so
        # the types aren't the same.
        original_chunks = []
        async for chunk in original:
            original_chunks.append(chunk)
        patched_chunks = []
        async for chunk in patched:
            patched_chunks.append(chunk)
        assert len(original_chunks) == len(patched_chunks)
        assert [o.choices == p.choices for o, p in zip(original_chunks, patched_chunks)]
    else:
        assert type(original) == type(patched)
        assert original.choices == patched.choices
    # Give the thread a chance.
    time.sleep(0.1)
    for call in mock_session.return_value.request.call_args_list:
        assert call[0][0].upper() == "POST"


@mock.patch("langsmith.client.requests.Session")
@pytest.mark.parametrize("stream", [False, True])
def test_completions_sync_api(mock_session: mock.MagicMock, stream: bool):
    import openai

    original_client = openai.Client()
    patched_client = wrap_openai(
        openai.Client(), tracing_extra={"name": "the completions"}
    )
    prompt = ("Say 'Foo' then stop.",)
    original = original_client.completions.create(
        model="gpt-3.5-turbo-instruct",
        prompt=prompt,
        max_tokens=3,
        temperature=0,
        seed=42,
        stream=stream,
    )
    patched = patched_client.completions.create(
        model="gpt-3.5-turbo-instruct",
        prompt=prompt,
        max_tokens=3,
        temperature=0,
        seed=42,
        stream=stream,
    )
    if stream:
        # We currently return a generator, so
        # the types aren't the same.
        original_chunks = list(original)
        patched_chunks = list(patched)
        assert len(original_chunks) == len(patched_chunks)
        assert [o.choices == p.choices for o, p in zip(original_chunks, patched_chunks)]
    else:
        assert type(original) == type(patched)
        assert original.choices == patched.choices
    # Give the thread a chance.
    time.sleep(0.1)
    for call in mock_session.return_value.request.call_args_list:
        assert call[0][0].upper() == "POST"


@mock.patch("langsmith.client.requests.Session")
@pytest.mark.parametrize("stream", [False, True])
async def test_completions_async_api(mock_session: mock.MagicMock, stream: bool):
    import openai

    original_client = openai.AsyncClient()
    patched_client = wrap_openai(
        openai.AsyncClient(), tracing_extra={"name": "completions"}
    )
    prompt = ("Say 'Hi i'm ChatGPT' then stop.",)
    original = await original_client.completions.create(
        model="gpt-3.5-turbo-instruct",
        prompt=prompt,
        max_tokens=5,
        temperature=0,
        seed=42,
        stream=stream,
    )
    patched = await patched_client.completions.create(
        model="gpt-3.5-turbo-instruct",
        prompt=prompt,
        max_tokens=5,
        temperature=0,
        seed=42,
        stream=stream,
    )
    if stream:
        # We currently return a generator, so
        # the types aren't the same.
        original_chunks = []
        async for chunk in original:
            original_chunks.append(chunk)
        patched_chunks = []
        async for chunk in patched:
            patched_chunks.append(chunk)
        assert len(original_chunks) == len(patched_chunks)
        assert [o.choices == p.choices for o, p in zip(original_chunks, patched_chunks)]
    else:
        assert type(original) == type(patched)
        assert original.choices == patched.choices
    # Give the thread a chance.
    time.sleep(0.1)
    assert mock_session.return_value.request.call_count >= 1
    for call in mock_session.return_value.request.call_args_list:
        assert call[0][0].upper() == "POST"
