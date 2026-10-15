"""Sandbox operations enrich the current run without creating child spans."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_httpx import HTTPXMock

from langsmith import trace, tracing_context
from langsmith.run_helpers import get_current_run_tree
from langsmith.sandbox import (
    AsyncSandboxClient,
    ResourceNotFoundError,
    SandboxClient,
)
from langsmith.sandbox._async_sandbox import AsyncSandbox
from langsmith.sandbox._models import AsyncCommandHandle, CommandHandle
from langsmith.sandbox._sandbox import Sandbox
from langsmith.sandbox._tracing import add_sandbox_metadata

from ._sse_fixtures import SSE_HEADERS, exited, sse_bytes, started

SANDBOX_ID = "11111111-1111-4111-8111-111111111111"
DATA = {
    "id": SANDBOX_ID,
    "name": "display-name",
    "dataplane_url": "https://router.example.com/sandbox",
}
SERVICE = {
    "browser_url": "https://service.example.com/auth",
    "service_url": "https://service.example.com",
    "token": "test-token",
    "expires_at": "2099-01-01T00:00:00Z",
}


def test_metadata_only_updates_current_run():
    with tracing_context(enabled="local"), trace("parent") as parent:
        with trace("operation", metadata={"existing": True}) as run:
            add_sandbox_metadata(SANDBOX_ID)
            add_sandbox_metadata(None)
            add_sandbox_metadata("")
            assert run.metadata["sandbox_id"] == SANDBOX_ID
            assert run.metadata["existing"] is True
            assert run.child_runs == []
        assert "sandbox_id" not in parent.metadata
    add_sandbox_metadata(SANDBOX_ID)
    assert get_current_run_tree() is None


@pytest.mark.parametrize("operation", ["run", "read", "write", "glob"])
@pytest.mark.parametrize("is_async", [False, True])
async def test_dataplane_calls(operation, is_async, httpx_mock, monkeypatch):
    monkeypatch.setenv("LANGSMITH_EXPERIMENTAL_FEATURES", "sandbox_sse_exec")
    if operation == "run":
        httpx_mock.add_response(
            headers=SSE_HEADERS,
            content=sse_bytes(started(), exited()),
        )
    elif operation == "glob":
        httpx_mock.add_response(json={"paths": []})
    else:
        httpx_mock.add_response(content=b"file contents")
    client = (
        AsyncSandboxClient(max_retries=0) if is_async else SandboxClient(max_retries=0)
    )
    cls = AsyncSandbox if is_async else Sandbox
    sandbox = cls.from_dict(DATA, client=client, auto_delete=False)
    args = {
        "write": ("/file.txt", "contents"),
        "read": ("/file.txt",),
        "run": ("echo hello",),
        "glob": ("*.txt", "/"),
    }[operation]
    try:
        with tracing_context(enabled="local"), trace("operation") as run:
            result = getattr(sandbox, operation)(*args)
            if is_async:
                await result
            assert run.metadata["sandbox_id"] == SANDBOX_ID
            assert run.child_runs == []
    finally:
        if is_async:
            await client.aclose()
        else:
            client.close()


@pytest.mark.parametrize("is_async", [False, True])
@pytest.mark.parametrize(
    "operation", ["create_sandbox", "get_sandbox", "update_sandbox"]
)
async def test_client_response_metadata(operation, is_async, httpx_mock: HTTPXMock):
    httpx_mock.add_response(json=DATA)
    client = (
        AsyncSandboxClient(max_retries=0) if is_async else SandboxClient(max_retries=0)
    )
    try:
        with tracing_context(enabled="local"), trace("operation") as run:
            kwargs = {"name": "display-name"}
            result = getattr(client, operation)(**kwargs)
            if is_async:
                await result
            assert run.metadata["sandbox_id"] == SANDBOX_ID
            assert run.child_runs == []
        httpx_mock.add_response()
        with tracing_context(enabled="local"), trace("stop") as run:
            result = client.stop_sandbox("display-name")
            if is_async:
                await result
            assert run.metadata["sandbox_id"] == SANDBOX_ID
    finally:
        if is_async:
            await client.aclose()
        else:
            client.close()


@pytest.mark.parametrize("is_async", [False, True])
async def test_service_requests_after_handle_creation(is_async, httpx_mock):
    httpx_mock.add_response(json=SERVICE)
    httpx_mock.add_response(json={"ok": True})
    client = (
        AsyncSandboxClient(max_retries=0) if is_async else SandboxClient(max_retries=0)
    )
    cls = AsyncSandbox if is_async else Sandbox
    sandbox = cls.from_dict(DATA, client=client, auto_delete=False)
    try:
        service = sandbox.service(3000)
        if is_async:
            service = await service
        with tracing_context(enabled="local"), trace("request") as run:
            response = service.get("/health")
            if is_async:
                response = await response
            assert response.json() == {"ok": True}
            assert run.metadata["sandbox_id"] == SANDBOX_ID
    finally:
        if is_async:
            await client.aclose()
        else:
            client.close()


@pytest.mark.parametrize("is_async", [False, True])
@pytest.mark.parametrize(
    "operation",
    ["start", "stop", "delete", "capture_snapshot", "generate_download_url"],
)
async def test_handle_lifecycle_metadata(operation, is_async):
    client = AsyncMock() if is_async else MagicMock()
    cls = AsyncSandbox if is_async else Sandbox
    sandbox = cls.from_dict(DATA, client=client, auto_delete=False)
    args = (
        ("snapshot",)
        if operation in ("capture_snapshot", "generate_download_url")
        else ()
    )
    with tracing_context(enabled="local"), trace("operation") as run:
        result = getattr(sandbox, operation)(*args)
        if is_async:
            await result
        assert run.metadata["sandbox_id"] == SANDBOX_ID


@pytest.mark.parametrize("is_async", [False, True])
async def test_unknown_id_and_list_do_not_annotate(is_async, httpx_mock):
    httpx_mock.add_response(json={"sandboxes": [DATA]})
    httpx_mock.add_response()
    client = (
        AsyncSandboxClient(max_retries=0) if is_async else SandboxClient(max_retries=0)
    )
    try:
        with tracing_context(enabled="local"), trace("operation") as run:
            result = client.list_sandboxes()
            if is_async:
                await result
            result = client.stop_sandbox("unknown-name")
            if is_async:
                await result
            assert "sandbox_id" not in run.metadata
    finally:
        if is_async:
            await client.aclose()
        else:
            client.close()


@pytest.mark.parametrize("is_async", [False, True])
@pytest.mark.parametrize("operation", ["kill", "send_input", "close_input"])
async def test_command_control_metadata(operation, is_async):
    sandbox = MagicMock(id=SANDBOX_ID)
    cls = AsyncCommandHandle if is_async else CommandHandle
    control = AsyncMock() if is_async else MagicMock()
    handle = cls(iter(()), control, sandbox, command_id="command")
    with tracing_context(enabled="local"), trace("control") as run:
        result = getattr(handle, operation)(
            *("input",) if operation == "send_input" else ()
        )
        if is_async:
            await result
        assert run.metadata["sandbox_id"] == SANDBOX_ID


@pytest.mark.parametrize("is_async", [False, True])
async def test_failed_operation_keeps_metadata(is_async, httpx_mock):
    httpx_mock.add_response(status_code=404, json={"detail": "File not found"})
    client = (
        AsyncSandboxClient(max_retries=0) if is_async else SandboxClient(max_retries=0)
    )
    cls = AsyncSandbox if is_async else Sandbox
    sandbox = cls.from_dict(DATA, client=client, auto_delete=False)
    try:
        with tracing_context(enabled="local"), trace("operation") as run:
            with pytest.raises(ResourceNotFoundError):
                result = sandbox.read("/missing")
                if is_async:
                    await result
            assert run.metadata["sandbox_id"] == SANDBOX_ID
    finally:
        if is_async:
            await client.aclose()
        else:
            client.close()


@pytest.mark.parametrize("is_async", [False, True])
@pytest.mark.parametrize("reference", ["display-name", SANDBOX_ID])
@pytest.mark.parametrize("operation", ["delete", "rename"])
async def test_changed_name_does_not_reuse_cached_id(
    is_async, reference, operation, httpx_mock
):
    httpx_mock.add_response(json=DATA)
    httpx_mock.add_response(json={**DATA, "name": "new-name"})
    httpx_mock.add_response()
    client = (
        AsyncSandboxClient(max_retries=0) if is_async else SandboxClient(max_retries=0)
    )
    client._sandbox_ids["unrelated"] = "another-id"
    try:
        result = client.get_sandbox("display-name")
        if is_async:
            await result
        result = (
            client.delete_sandbox(reference)
            if operation == "delete"
            else client.update_sandbox(reference, new_name="new-name")
        )
        if is_async:
            await result
        assert client._sandbox_ids["unrelated"] == "another-id"
        with tracing_context(enabled="local"), trace("operation") as run:
            result = client.stop_sandbox("display-name")
            if is_async:
                await result
            assert "sandbox_id" not in run.metadata
        if operation == "rename":
            httpx_mock.add_response()
            with tracing_context(enabled="local"), trace("renamed") as run:
                result = client.stop_sandbox("new-name")
                if is_async:
                    await result
                assert run.metadata["sandbox_id"] == SANDBOX_ID
    finally:
        if is_async:
            await client.aclose()
        else:
            client.close()


@pytest.mark.parametrize("is_async", [False, True])
async def test_client_accepts_uuid_without_lookup(is_async, httpx_mock):
    httpx_mock.add_response()
    client = (
        AsyncSandboxClient(max_retries=0) if is_async else SandboxClient(max_retries=0)
    )
    try:
        with tracing_context(enabled="local"), trace("operation") as run:
            result = client.stop_sandbox(SANDBOX_ID)
            if is_async:
                await result
            assert run.metadata["sandbox_id"] == SANDBOX_ID
        assert len(httpx_mock.get_requests()) == 1
    finally:
        if is_async:
            await client.aclose()
        else:
            client.close()


async def test_async_context_isolation():
    async def operation(sandbox_id):
        with tracing_context(enabled="local"), trace("operation") as run:
            await asyncio.sleep(0)
            add_sandbox_metadata(sandbox_id)
            await asyncio.sleep(0)
            return run.metadata["sandbox_id"]

    assert await asyncio.gather(operation("first"), operation("second")) == [
        "first",
        "second",
    ]


def _two_chunk_messages():
    return [
        {"type": "stdout", "data": "a", "offset": 0},
        {"type": "stdout", "data": "b", "offset": 1},
        {"type": "exit", "exit_code": 0},
    ]


async def _aiter(messages):
    for message in messages:
        yield message


@pytest.mark.parametrize("is_async", [False, True])
async def test_command_stream_annotates_each_resumption(is_async):
    sandbox = MagicMock(id=SANDBOX_ID)
    other_id = "22222222-2222-4222-8222-222222222222"

    def make_handle():
        messages = _two_chunk_messages()
        if is_async:
            return AsyncCommandHandle(
                _aiter(messages), None, sandbox, command_id="command"
            )
        return CommandHandle(iter(messages), None, sandbox, command_id="command")

    async def next_chunk(iterator):
        return await iterator.__anext__() if is_async else next(iterator)

    def iterate(handle):
        return handle.__aiter__() if is_async else iter(handle)

    # First chunk consumed outside tracing, the next inside a traced run.
    chunks = iterate(make_handle())
    await next_chunk(chunks)
    with tracing_context(enabled="local"), trace("later") as run:
        await next_chunk(chunks)
        assert run.metadata["sandbox_id"] == SANDBOX_ID

    # Using another sandbox mid-stream, then resuming, records this sandbox.
    chunks = iterate(make_handle())
    with tracing_context(enabled="local"), trace("interleaved") as run:
        await next_chunk(chunks)
        add_sandbox_metadata(other_id)
        assert run.metadata["sandbox_id"] == other_id
        await next_chunk(chunks)
        assert run.metadata["sandbox_id"] == SANDBOX_ID
