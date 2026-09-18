"""Shared effect programs for synchronous and asynchronous sandboxes."""

from __future__ import annotations

from collections.abc import Generator, Mapping
from typing import Any, Optional, Protocol, Union

from langsmith._openapi_client._httpx import httpx
from langsmith.sandbox._effects import Call
from langsmith.sandbox._exceptions import ResourceNotFoundError
from langsmith.sandbox._helpers import (
    build_range_header,
    file_chunk_from_response,
    file_stat_from_response,
    handle_sandbox_http_error,
    raise_file_http_error,
)
from langsmith.sandbox._models import (
    ExecutionResult,
    FileChunk,
    FileStat,
    GlobResult,
    GrepResult,
)

RequestHeaders = Optional[Mapping[str, str]]


class SandboxLike(Protocol):
    """The sandbox state used by shared effect programs."""

    name: str
    status: str
    dataplane_url: Optional[str]
    _client: Any

    def _require_dataplane_url(self) -> str:
        """Return the configured dataplane URL."""
        ...


def run_http(
    sandbox: SandboxLike,
    command: str,
    *,
    timeout: int,
    env: Optional[dict[str, str]],
    cwd: Optional[str],
    run_config: Optional[dict[str, Any]],
    shell: str,
    headers: RequestHeaders,
) -> Generator[Call[Any], Any, ExecutionResult]:
    """Execute a command through the blocking HTTP endpoint."""
    dataplane_url = sandbox._require_dataplane_url()
    payload: dict[str, Any] = {
        "command": command,
        "timeout": timeout,
        "shell": shell,
    }
    if env is not None:
        payload["env"] = env
    if cwd is not None:
        payload["cwd"] = cwd
    if run_config is not None:
        payload["run_config"] = run_config
    try:
        response = yield from Call(
            lambda: sandbox._client._http.post(
                f"{dataplane_url}/execute",
                json=payload,
                timeout=timeout + 10,
                headers=sandbox._client._request_headers(headers),
            )
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        handle_sandbox_http_error(error)
        raise
    data = response.json()
    return ExecutionResult(
        stdout=data.get("stdout", ""),
        stderr=data.get("stderr", ""),
        exit_code=data.get("exit_code", -1),
    )


def write(
    sandbox: SandboxLike,
    path: str,
    content: Union[str, bytes],
    *,
    timeout: int,
    headers: RequestHeaders,
) -> Generator[Call[Any], Any, None]:
    """Write content to a sandbox file."""
    dataplane_url = sandbox._require_dataplane_url()
    if isinstance(content, str):
        content = content.encode("utf-8")
    try:
        response = yield from Call(
            lambda: sandbox._client._http.post(
                f"{dataplane_url}/upload",
                params={"path": path},
                files={"file": ("file", content)},
                timeout=timeout,
                headers=sandbox._client._request_headers(headers),
            )
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        handle_sandbox_http_error(error)


def read(
    sandbox: SandboxLike,
    path: str,
    *,
    timeout: int,
    headers: RequestHeaders,
) -> Generator[Call[Any], Any, bytes]:
    """Read a sandbox file."""
    dataplane_url = sandbox._require_dataplane_url()
    try:
        response = yield from Call(
            lambda: sandbox._client._http.get(
                f"{dataplane_url}/download",
                params={"path": path},
                timeout=timeout,
                headers=sandbox._client._request_headers(headers),
            )
        )
        response.raise_for_status()
        return response.content
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            raise ResourceNotFoundError(
                f"File '{path}' not found in sandbox '{sandbox.name}'",
                resource_type="file",
            ) from error
        handle_sandbox_http_error(error)
        raise


def stat(
    sandbox: SandboxLike,
    path: str,
    *,
    timeout: int,
    headers: RequestHeaders,
) -> Generator[Call[Any], Any, FileStat]:
    """Read sandbox file metadata."""
    dataplane_url = sandbox._require_dataplane_url()
    try:
        response = yield from Call(
            lambda: sandbox._client._http.request(
                "HEAD",
                f"{dataplane_url}/download",
                params={"path": path},
                timeout=timeout,
                headers=sandbox._client._request_headers(headers),
            )
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        raise_file_http_error(error, path=path, sandbox_name=sandbox.name)
        raise
    return file_stat_from_response(response)


def read_range(
    sandbox: SandboxLike,
    path: str,
    *,
    start: Optional[int],
    end: Optional[int],
    suffix_bytes: Optional[int],
    if_range: Optional[str],
    if_none_match: Optional[str],
    timeout: int,
    headers: RequestHeaders,
) -> Generator[Call[Any], Any, FileChunk]:
    """Read a range from a sandbox file."""
    request_headers = dict(sandbox._client._request_headers(headers) or {})
    request_headers["Range"] = build_range_header(
        start=start, end=end, suffix_bytes=suffix_bytes
    )
    if if_range:
        request_headers["If-Range"] = if_range
    if if_none_match:
        request_headers["If-None-Match"] = if_none_match
    dataplane_url = sandbox._require_dataplane_url()
    try:
        response = yield from Call(
            lambda: sandbox._client._http.get(
                f"{dataplane_url}/download",
                params={"path": path},
                timeout=timeout,
                headers=request_headers,
            )
        )
        if response.status_code != 304:
            response.raise_for_status()
    except httpx.HTTPStatusError as error:
        raise_file_http_error(error, path=path, sandbox_name=sandbox.name)
        raise
    return file_chunk_from_response(response)


def glob(
    sandbox: SandboxLike,
    pattern: str,
    path: str,
    *,
    limit: Optional[int],
    timeout: int,
    headers: RequestHeaders,
) -> Generator[Call[Any], Any, GlobResult]:
    """Find sandbox files and directories matching a pattern."""
    payload: dict[str, Any] = {"pattern": pattern, "path": path}
    if limit is not None:
        payload["limit"] = limit
    data = yield from _file_search(
        sandbox, "glob", payload, timeout=timeout, headers=headers
    )
    return GlobResult.from_dict(data)


def ls(
    sandbox: SandboxLike,
    path: str,
    *,
    limit: Optional[int],
    timeout: int,
    headers: RequestHeaders,
) -> Generator[Call[Any], Any, GlobResult]:
    """List a sandbox directory's immediate entries."""
    return (
        yield from glob(
            sandbox, "*", path, limit=limit, timeout=timeout, headers=headers
        )
    )


def grep(
    sandbox: SandboxLike,
    pattern: str,
    path: str,
    *,
    glob: Optional[str],
    limit: Optional[int],
    timeout: int,
    headers: RequestHeaders,
) -> Generator[Call[Any], Any, GrepResult]:
    """Search sandbox file contents for a literal string."""
    payload: dict[str, Any] = {"pattern": pattern, "path": path}
    if glob is not None:
        payload["glob"] = glob
    if limit is not None:
        payload["limit"] = limit
    data = yield from _file_search(
        sandbox, "grep", payload, timeout=timeout, headers=headers
    )
    return GrepResult.from_dict(data)


def _file_search(
    sandbox: SandboxLike,
    operation: str,
    payload: dict[str, Any],
    *,
    timeout: int,
    headers: RequestHeaders,
) -> Generator[Call[Any], Any, dict[str, Any]]:
    """Run a read-only filesystem search."""
    dataplane_url = sandbox._require_dataplane_url()
    try:
        response = yield from Call(
            lambda: sandbox._client._http.post(
                f"{dataplane_url}/{operation}",
                json=payload,
                timeout=timeout,
                headers=sandbox._client._request_headers(headers),
            )
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        raise_file_http_error(error, path=payload["path"], sandbox_name=sandbox.name)
        raise
    return response.json()
