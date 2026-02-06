# mypy: disable-error-code="attr-defined, union-attr, arg-type, call-overload"
from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from langsmith import Client
from langsmith.run_helpers import tracing_context
from langsmith.wrappers import wrap_anthropic
from tests.unit_tests.test_run_helpers import _get_calls

if TYPE_CHECKING:
    import anthropic

model_name = "claude-3-5-haiku-latest"
messages = [{"role": "user", "content": "Say 'foo'"}]


@pytest.fixture
def original_client() -> anthropic.Anthropic:
    import anthropic  # noqa

    return anthropic.Anthropic()


@pytest.fixture
def original_async_client() -> anthropic.AsyncAnthropic:
    import anthropic  # noqa

    return anthropic.AsyncAnthropic()


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


@pytest.fixture
def patched_client(mock_ls_client: Client) -> anthropic.Anthropic:
    import anthropic  # noqa

    return wrap_anthropic(
        anthropic.Anthropic(), tracing_extra={"client": mock_ls_client}
    )


@pytest.fixture
def patched_async_client(mock_ls_client: Client) -> anthropic.AsyncAnthropic:
    import anthropic  # noqa

    return wrap_anthropic(
        anthropic.AsyncAnthropic(), tracing_extra={"client": mock_ls_client}
    )


def test_chat_sync_api_stream(
    original_client: anthropic.Anthropic,
    patched_client: anthropic.Anthropic,
    mock_ls_client: Client,
):
    with tracing_context(enabled=True):
        original_chunks, patched_chunks = [], []
        with original_client.messages.stream(
            messages=messages,
            temperature=0,
            model=model_name,
            max_tokens=3,
        ) as stream:
            for chunk in stream:
                original_chunks.append(chunk)
        with patched_client.messages.stream(
            messages=messages,
            temperature=0,
            model=model_name,
            max_tokens=3,
        ) as stream:
            for chunk in stream:
                patched_chunks.append(chunk)
        assert len(original_chunks) == len(patched_chunks)
        assert "".join(
            [
                c.delta.text
                for c in original_chunks
                if hasattr(c, "delta") and c.type == "content_block_delta"
            ]
        ) == "".join(
            [
                c.delta.text
                for c in patched_chunks
                if hasattr(c, "delta") and c.type == "content_block_delta"
            ]
        )

        calls = _get_calls(mock_ls_client, minimum=1)
        assert calls
        datas = [json.loads(call.kwargs["data"]) for call in calls]
        outputs = None
        for data in datas:
            if data.get("post"):
                if outputs := data["post"][0]["outputs"]:
                    break
            if data.get("patch"):
                outputs = data["patch"][0]["outputs"]
                break
        assert outputs

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


def test_chat_sync_api(
    original_client: anthropic.Anthropic,
    patched_client: anthropic.Anthropic,
    mock_ls_client: Client,
):
    with tracing_context(enabled=True):
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
        assert isinstance(patched, type(original))
        assert "".join([c.text for c in original.content]) == "".join(
            [c.text for c in patched.content]
        )

        calls = _get_calls(mock_ls_client, minimum=1)
        assert calls
        datas = [json.loads(call.kwargs["data"]) for call in calls]
        outputs = None
        for data in datas:
            if data.get("post"):
                if outputs := data["post"][0]["outputs"]:
                    break
            if data.get("patch"):
                outputs = data["patch"][0]["outputs"]
                break

        assert outputs


async def test_chat_async_api_stream(
    original_async_client: anthropic.AsyncAnthropic,
    patched_async_client: anthropic.AsyncAnthropic,
    mock_ls_client: Client,
) -> None:
    original_chunks, patched_chunks = [], []
    with tracing_context(enabled=True):
        async with original_async_client.messages.stream(
            messages=messages,
            temperature=0,
            model=model_name,
            max_tokens=3,
        ) as stream:
            async for chunk in stream:
                original_chunks.append(chunk)
        async with patched_async_client.messages.stream(
            messages=messages,
            temperature=0,
            model=model_name,
            max_tokens=3,
        ) as stream:
            async for chunk in stream:
                patched_chunks.append(chunk)
        assert len(original_chunks) == len(patched_chunks)
        assert "".join(
            [
                c.delta.text
                for c in original_chunks
                if hasattr(c, "delta") and c.type == "content_block_delta"
            ]
        ) == "".join(
            [
                c.delta.text
                for c in patched_chunks
                if hasattr(c, "delta") and c.type == "content_block_delta"
            ]
        )
        time.sleep(0.1)
        for call in mock_ls_client.session.request.call_args_list:
            assert call[0][0].upper() == "POST"

        original_text_chunks = []
        patched_text_chunks = []
        async with original_async_client.messages.stream(
            messages=messages,
            temperature=0,
            model=model_name,
            max_tokens=3,
        ) as stream:
            async for chunk in stream.text_stream:
                original_text_chunks.append(chunk)
        async with patched_async_client.messages.stream(
            messages=messages,
            temperature=0,
            model=model_name,
            max_tokens=3,
        ) as stream:
            async for chunk in stream.text_stream:
                patched_text_chunks.append(chunk)
        assert len(original_chunks) == len(patched_chunks)
        assert "".join(original_text_chunks) == "".join(patched_text_chunks)


async def test_chat_async_api(
    original_async_client: anthropic.AsyncAnthropic,
    patched_async_client: anthropic.AsyncAnthropic,
    mock_ls_client: Client,
) -> None:
    with tracing_context(enabled=True):
        original = await original_async_client.messages.create(
            messages=messages,
            temperature=0,
            model=model_name,
            max_tokens=3,
        )
        patched = await patched_async_client.messages.create(
            messages=messages,
            temperature=0,
            model=model_name,
            max_tokens=3,
        )
        assert isinstance(patched, type(original))
        assert "".join([c.text for c in original.content]) == "".join(
            [c.text for c in patched.content]
        )

        time.sleep(0.1)
        for call in mock_ls_client.session.request.call_args_list:
            assert call[0][0].upper() == "POST"


def test_beta_chat_sync_api():
    import anthropic  # noqa
    from tests.unit_tests.test_run_helpers import _get_calls

    with tracing_context(enabled=True):
        mock_session = mock.MagicMock()
        mock_client = Client(session=mock_session, info=LS_TEST_CLIENT_INFO)
        original_client = anthropic.Anthropic()
        patched_client = wrap_anthropic(
            anthropic.Anthropic(), tracing_extra={"client": mock_client}
        )

        original = original_client.beta.messages.create(
            messages=messages,
            temperature=0,
            model=model_name,
            max_tokens=3,
        )
        patched = patched_client.beta.messages.create(
            messages=messages,
            temperature=0,
            model=model_name,
            max_tokens=3,
        )
        assert isinstance(patched, type(original))
        assert "".join([c.text for c in original.content]) == "".join(
            [c.text for c in patched.content]
        )

        calls = _get_calls(mock_client, minimum=1)
        assert calls
        datas = [json.loads(call.kwargs["data"]) for call in calls]
        outputs = None
        for data in datas:
            if data.get("post"):
                if outputs := data["post"][0]["outputs"]:
                    break
            if data.get("patch"):
                outputs = data["patch"][0]["outputs"]
                break

        assert outputs


async def test_beta_chat_async_api():
    import anthropic  # noqa

    mock_session = mock.MagicMock()
    mock_client = Client(session=mock_session)
    original_client = anthropic.AsyncAnthropic()
    patched_client = wrap_anthropic(
        anthropic.AsyncAnthropic(), tracing_extra={"client": mock_client}
    )
    with tracing_context(enabled=True):
        original = await original_client.beta.messages.create(
            messages=messages,
            temperature=0,
            model=model_name,
            max_tokens=3,
        )
        patched = await patched_client.beta.messages.create(
            messages=messages,
            temperature=0,
            model=model_name,
            max_tokens=3,
        )
        assert isinstance(patched, type(original))
        assert "".join([c.text for c in original.content]) == "".join(
            [c.text for c in patched.content]
        )

        time.sleep(1)
        assert mock_session.request.call_count > 1
        # This is the info call
        assert mock_session.request.call_args_list[0][0][0].upper() == "GET"
        for call in mock_session.request.call_args_list[1:]:
            assert call[0][0].upper() == "POST"


def test_prepopulated_invocation_params():
    """Test that prepopulated invocation params are merged
    and runtime params override."""
    import anthropic

    mock_session = mock.MagicMock()
    client = Client(session=mock_session, info=LS_TEST_CLIENT_INFO)

    # Wrap client with prepopulated params including top_k
    patched_client = wrap_anthropic(
        anthropic.Anthropic(),
        tracing_extra={
            "client": client,
            "metadata": {
                "ls_invocation_params": {"top_k": 100, "env": "test", "team": "qa"},
                "custom_key": "custom_value",
                "version": "1.0.0",
            },
        },
    )

    messages = [{"role": "user", "content": "Say 'hello'"}]

    with tracing_context(enabled=True):
        patched_client.messages.create(
            messages=messages,
            top_k=40,  # Should override prepopulated top_k=100
            model=model_name,
            max_tokens=10,
        )

    # Give the thread a chance
    time.sleep(0.5)

    # Get the run data using the _get_calls helper
    calls = _get_calls(client, minimum=1)
    assert calls

    # Parse the run data from the calls
    run_data = None
    for call in calls:
        if json_bytes := call.kwargs.get("data"):
            json_str = (
                json_bytes.decode("utf-8")
                if isinstance(json_bytes, bytes)
                else json_bytes
            )
            data = json.loads(json_str)
            # Look in both post and patch arrays
            for event in data.get("post", []) + data.get("patch", []):
                if event.get("extra"):
                    run_data = event
                    break
            if run_data:
                break

    assert run_data is not None

    # Check invocation params - they are in metadata, not extra.invocation_params
    extra = run_data.get("extra", {})
    metadata = extra.get("metadata", {})
    ls_invocation_params = metadata.get("ls_invocation_params", {})

    # Runtime top_k should override prepopulated top_k
    assert ls_invocation_params.get("top_k") == 40
    # Prepopulated params without conflicts should still be there
    assert ls_invocation_params.get("env") == "test"
    assert ls_invocation_params.get("team") == "qa"

    # Check that other metadata keys are preserved
    assert metadata.get("custom_key") == "custom_value"
    assert metadata.get("version") == "1.0.0"
