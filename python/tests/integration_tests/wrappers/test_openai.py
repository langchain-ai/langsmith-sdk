# mypy: disable-error-code="attr-defined, union-attr, arg-type, call-overload"
import time
from typing import Optional
from unittest import mock

import pytest
from pydantic import BaseModel, Field

import langsmith
from langsmith.run_trees import RunTree
from langsmith.wrappers import wrap_openai


class InputTokenDetails(BaseModel):
    audio: Optional[int] = None
    cache_read: Optional[int] = None
    cache_creation: Optional[int] = None

    class Config:
        extra = "allow"


class OutputTokenDetails(BaseModel):
    audio: Optional[int] = None
    reasoning: Optional[int] = None

    class Config:
        extra = "allow"


class UsageMetadata(BaseModel):
    input_tokens: int = Field(..., description="sum of all input tokens")
    output_tokens: int = Field(..., description="sum of all output tokens")
    total_tokens: int = Field(..., description="sum of all input and output tokens")
    input_tokens_details: Optional[InputTokenDetails] = None
    output_tokens_details: Optional[OutputTokenDetails] = None


class Collect:
    def __init__(self):
        self.run: Optional[RunTree] = None

    def __call__(self, run):
        self.run = run

    def validate(self):
        assert self.run is not None
        try:
            UsageMetadata.model_validate(self.run.outputs["usage_metadata"])
        except:
            raise


@mock.patch("langsmith.client.requests.Session")
@pytest.mark.parametrize("stream", [False, True])
def test_chat_sync_api(mock_session: mock.MagicMock, stream: bool):
    import openai  # noqa

    client = langsmith.Client(session=mock_session())
    original_client = openai.Client()
    patched_client = wrap_openai(openai.Client(), tracing_extra={"client": client})
    messages = [{"role": "user", "content": "Say 'foo'"}]
    original = original_client.chat.completions.create(
        messages=messages,  # noqa: [arg-type]
        stream=stream,
        temperature=0,
        seed=42,
        model="gpt-3.5-turbo",
    )
    collect = Collect()
    patched = patched_client.chat.completions.create(
        messages=messages,  # noqa: [arg-type]
        stream=stream,
        temperature=0,
        seed=42,
        model="gpt-3.5-turbo",
        langsmith_extra={"on_end": collect},
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
        collect.validate()

    # Give the thread a chance.
    time.sleep(0.01)
    for call in mock_session.return_value.request.call_args_list[1:]:
        assert call[0][0].upper() == "POST"


@mock.patch("langsmith.client.requests.Session")
@pytest.mark.parametrize("stream", [False, True])
async def test_chat_async_api(mock_session: mock.MagicMock, stream: bool):
    import openai  # noqa

    client = langsmith.Client(session=mock_session())
    original_client = openai.AsyncClient()
    patched_client = wrap_openai(openai.AsyncClient(), tracing_extra={"client": client})
    messages = [{"role": "user", "content": "Say 'foo'"}]
    original = await original_client.chat.completions.create(
        messages=messages, stream=stream, temperature=0, seed=42, model="gpt-3.5-turbo"
    )
    collect = Collect()
    patched = await patched_client.chat.completions.create(
        messages=messages,
        stream=stream,
        temperature=0,
        seed=42,
        model="gpt-3.5-turbo",
        langsmith_extra={"on_end": collect},
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
        collect.validate()
    # Give the thread a chance.
    time.sleep(0.1)
    for call in mock_session.return_value.request.call_args_list[1:]:
        assert call[0][0].upper() == "POST"


@mock.patch("langsmith.client.requests.Session")
@pytest.mark.parametrize("stream", [False, True])
def test_completions_sync_api(mock_session: mock.MagicMock, stream: bool):
    import openai

    client = langsmith.Client(session=mock_session())
    original_client = openai.Client()
    patched_client = wrap_openai(openai.Client(), tracing_extra={"client": client})
    prompt = ("Say 'Foo' then stop.",)
    original = original_client.completions.create(
        model="gpt-3.5-turbo-instruct",
        prompt=prompt,
        max_tokens=3,
        temperature=0,
        seed=42,
        stream=stream,
    )
    collect = Collect()
    patched = patched_client.completions.create(
        model="gpt-3.5-turbo-instruct",
        prompt=prompt,
        max_tokens=3,
        temperature=0,
        seed=42,
        stream=stream,
        langsmith_extra={"on_end": collect},
    )
    if stream:
        # We currently return a generator, so
        # the types aren't the same.
        original_chunks = list(original)
        patched_chunks = list(patched)
        assert len(original_chunks) == len(patched_chunks)
        assert [o.choices == p.choices for o, p in zip(original_chunks, patched_chunks)]
        assert original.response
        assert patched.response
    else:
        assert type(original) == type(patched)
        assert original.choices == patched.choices
        collect.validate()
    # Give the thread a chance.
    time.sleep(0.1)
    for call in mock_session.return_value.request.call_args_list[1:]:
        assert call[0][0].upper() == "POST"


@mock.patch("langsmith.client.requests.Session")
@pytest.mark.parametrize("stream", [False, True])
async def test_completions_async_api(mock_session: mock.MagicMock, stream: bool):
    import openai

    client = langsmith.Client(session=mock_session())

    original_client = openai.AsyncClient()
    patched_client = wrap_openai(
        openai.AsyncClient(),
        tracing_extra={"client": client},
        chat_name="chattychat",
        completions_name="incompletions",
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
    collect = Collect()
    patched = await patched_client.completions.create(
        model="gpt-3.5-turbo-instruct",
        prompt=prompt,
        max_tokens=5,
        temperature=0,
        seed=42,
        stream=stream,
        langsmith_extra={"on_end": collect},
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
        assert original.response
        assert patched.response
    else:
        assert type(original) == type(patched)
        assert original.choices == patched.choices
        collect.validate()
    # Give the thread a chance.
    for _ in range(10):
        time.sleep(0.1)
        if mock_session.return_value.request.call_count >= 1:
            break
    assert mock_session.return_value.request.call_count >= 1
    for call in mock_session.return_value.request.call_args_list[1:]:
        assert call[0][0].upper() == "POST"
