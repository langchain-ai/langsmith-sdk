# mypy: disable-error-code="attr-defined, union-attr, arg-type, call-overload"
import time
from unittest import mock

import pytest

from langsmith.wrappers import wrap_anthropic

model_name = "claude-3-haiku-20240307"


@mock.patch("langsmith.client.requests.Session")
@pytest.mark.parametrize("stream", [False, True])
def test_chat_sync_api(mock_session: mock.MagicMock, stream: bool):
    import anthropic  # noqa

    original_client = anthropic.Anthropic()
    patched_client = wrap_anthropic(anthropic.Anthropic())
    messages = [{"role": "user", "content": "Say 'foo'"}]

    if stream:
        original = original_client.messages.stream(
            messages=messages,  # noqa: [arg-type]
            temperature=0,
            model=model_name,
            max_tokens=3,
        )
        patched = patched_client.messages.stream(
            messages=messages,  # noqa: [arg-type]
            temperature=0,
            model=model_name,
            max_tokens=3,
        )
        # We currently return a generator, so
        # the types aren't the same.
        patched_chunks = list(patched)
        original_chunks = list(original)
        assert len(original_chunks) == len(patched_chunks)
        assert "".join([c.text for c in original.content]) == "".join(
            c.text for c in patched.content
        )
    else:
        original = original_client.messages.create(
            messages=messages,  # noqa: [arg-type]
            temperature=0,
            model=model_name,
            max_tokens=3,
        )
        patched = patched_client.messages.create(
            messages=messages,  # noqa: [arg-type]
            temperature=0,
            model=model_name,
            max_tokens=3,
        )
        assert type(original) == type(patched)
        assert "".join([c.text for c in original.content]) == "".join(
            c.text for c in patched.content
        )
    # Give the thread a chance.
    time.sleep(0.01)
    for call in mock_session.return_value.request.call_args_list:
        assert call[0][0].upper() == "POST"


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
        assert original.choices == patched.choices
    # Give the thread a chance.
    time.sleep(0.1)
    for call in mock_session.return_value.request.call_args_list:
        assert call[0][0].upper() == "POST"


@mock.patch("langsmith.client.requests.Session")
def test_completions_sync_api(mock_session: mock.MagicMock, stream: bool):
    import anthropic

    original_client = anthropic.Anthropic()
    patched_client = wrap_anthropic(anthropic.Anthropic())
    prompt = ("Say 'Foo' then stop.",)
    original = original_client.completions.create(
        model="gpt-3.5-turbo-instruct",
        prompt=prompt,
        temperature=0,
        stream=stream,
        max_tokens_to_sample=3,
    )
    patched = patched_client.completions.create(
        model="gpt-3.5-turbo-instruct",
        prompt=prompt,
        temperature=0,
        stream=stream,
        max_tokens_to_sample=3,
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
    import anthropic

    original_client = anthropic.AsyncAnthropic()
    patched_client = wrap_anthropic(anthropic.AsyncAnthropic())
    prompt = ("Say 'Hi i'm ChatGPT' then stop.",)
    original = await original_client.completions.create(
        model="gpt-3.5-turbo-instruct",
        prompt=prompt,
        temperature=0,
        stream=stream,
        max_tokens_to_sample=3,
    )
    patched = await patched_client.completions.create(
        model="gpt-3.5-turbo-instruct",
        prompt=prompt,
        temperature=0,
        stream=stream,
        max_tokens_to_sample=3,
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
