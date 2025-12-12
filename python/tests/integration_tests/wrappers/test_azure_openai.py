# mypy: disable-error-code="attr-defined, union-attr, arg-type, call-overload"
import json
import os
import time
from unittest import mock

import pytest

import langsmith
from langsmith.wrappers import wrap_openai


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.skipif(
    os.getenv("AZURE_OPENAI_API_KEY") is None, reason="AZURE_OPENAI_API_KEY is not set"
)
def test_chat_sync_api(stream: bool):
    from openai import AzureOpenAI  # noqa

    mock_session = mock.MagicMock()
    client = langsmith.Client(session=mock_session)
    original_client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    )
    patched_client = wrap_openai(
        AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        ),
        tracing_extra={"client": client},
    )
    messages = [{"role": "user", "content": "Say 'foo'"}]
    original = original_client.chat.completions.create(
        messages=messages,
        stream=stream,
        temperature=0,
        seed=42,
        model="gpt-4o-mini",
    )
    patched = patched_client.chat.completions.create(
        messages=messages,
        stream=stream,
        temperature=0,
        seed=42,
        model="gpt-4o-mini",
    )
    if stream:
        # We currently return a generator, so
        # the types aren't the same.
        original_chunks = list(original)
        patched_chunks = list(patched)
        assert len(original_chunks) == len(patched_chunks)
        assert [o.choices == p.choices for o, p in zip(original_chunks, patched_chunks)]
    else:
        assert type(original) is type(patched)
        assert original.choices == patched.choices
    # Give the thread a chance.
    time.sleep(0.01)
    for call in mock_session.request.call_args_list[1:]:
        assert call[0][0].upper() == "POST"
        data = json.loads(call.kwargs["data"].decode("utf-8"))
        assert data["post"][0]["extra"]["metadata"]["ls_provider"] == "azure"


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.skipif(
    os.getenv("AZURE_OPENAI_API_KEY") is None, reason="AZURE_OPENAI_API_KEY is not set"
)
async def test_chat_async_api(stream: bool):
    from openai import AsyncAzureOpenAI  # noqa

    mock_session = mock.MagicMock()
    client = langsmith.Client(session=mock_session)
    original_client = AsyncAzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    )
    patched_client = wrap_openai(
        AsyncAzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        ),
        tracing_extra={"client": client},
    )
    messages = [{"role": "user", "content": "Say 'foo'"}]
    original = await original_client.chat.completions.create(
        messages=messages, stream=stream, temperature=0, seed=42, model="gpt-4o-mini"
    )
    patched = await patched_client.chat.completions.create(
        messages=messages, stream=stream, temperature=0, seed=42, model="gpt-4o-mini"
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
        assert type(original) is type(patched)
        assert original.choices == patched.choices
    # Give the thread a chance.
    time.sleep(0.1)
    for call in mock_session.request.call_args_list[1:]:
        assert call[0][0].upper() == "POST"
        data = json.loads(call.kwargs["data"].decode("utf-8"))
        # Handle both "post" and "patch" operations
        if "post" in data and data["post"]:
            assert data["post"][0]["extra"]["metadata"]["ls_provider"] == "azure"
        elif "patch" in data and data["patch"]:
            assert data["patch"][0]["extra"]["metadata"]["ls_provider"] == "azure"
