"""Shared effect programs for synchronous and asynchronous sandboxes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional, Protocol, Union

from langsmith._openapi_client._httpx import httpx
from langsmith.sandbox._effects import Call, Program
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


def _request(
    sandbox: SandboxLike,
    method: str,
    endpoint: str,
    *,
    headers: RequestHeaders,
    file_path: Optional[str] = None,
    range_errors: bool = True,
    allow_not_modified: bool = False,
    **kwargs: Any,
) -> Program[httpx.Response]:
    url = f"{sandbox._require_dataplane_url()}/{endpoint}"
    try:
        response = yield from Call(
            lambda: sandbox._client._http.request(
                method, url, headers=sandbox._client._request_headers(headers), **kwargs
            )
        )
        if not (allow_not_modified and response.status_code == 304):
            response.raise_for_status()
        return response
    except httpx.HTTPStatusError as error:
        if file_path is not None:
            if range_errors:
                raise_file_http_error(error, path=file_path, sandbox_name=sandbox.name)
            elif error.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"File '{file_path}' not found in sandbox '{sandbox.name}'",
                    resource_type="file",
                ) from error
        handle_sandbox_http_error(error)
        raise


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
) -> Program[ExecutionResult]:
    """Execute a command through the blocking HTTP endpoint."""
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
    response = yield from _request(
        sandbox, "POST", "execute", json=payload, timeout=timeout + 10, headers=headers
    )
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
) -> Program[None]:
    """Write content to a sandbox file."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    yield from _request(
        sandbox,
        "POST",
        "upload",
        params={"path": path},
        files={"file": ("file", content)},
        timeout=timeout,
        headers=headers,
    )


def read(
    sandbox: SandboxLike,
    path: str,
    *,
    timeout: int,
    headers: RequestHeaders,
) -> Program[bytes]:
    """Read a sandbox file."""
    response = yield from _request(
        sandbox,
        "GET",
        "download",
        params={"path": path},
        timeout=timeout,
        headers=headers,
        file_path=path,
        range_errors=False,
    )
    return response.content


def stat(
    sandbox: SandboxLike,
    path: str,
    *,
    timeout: int,
    headers: RequestHeaders,
) -> Program[FileStat]:
    """Read sandbox file metadata."""
    response = yield from _request(
        sandbox,
        "HEAD",
        "download",
        params={"path": path},
        timeout=timeout,
        headers=headers,
        file_path=path,
    )
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
) -> Program[FileChunk]:
    """Read a range from a sandbox file."""
    request_headers = dict(headers or {})
    request_headers["Range"] = build_range_header(
        start=start, end=end, suffix_bytes=suffix_bytes
    )
    if if_range:
        request_headers["If-Range"] = if_range
    if if_none_match:
        request_headers["If-None-Match"] = if_none_match
    response = yield from _request(
        sandbox,
        "GET",
        "download",
        params={"path": path},
        timeout=timeout,
        headers=request_headers,
        file_path=path,
        allow_not_modified=True,
    )
    return file_chunk_from_response(response)


def glob(
    sandbox: SandboxLike,
    pattern: str,
    path: str,
    *,
    limit: Optional[int],
    timeout: int,
    headers: RequestHeaders,
) -> Program[GlobResult]:
    """Find sandbox files and directories matching a pattern."""
    payload: dict[str, Any] = {"pattern": pattern, "path": path}
    if limit is not None:
        payload["limit"] = limit
    response = yield from _request(
        sandbox,
        "POST",
        "glob",
        json=payload,
        timeout=timeout,
        headers=headers,
        file_path=path,
    )
    return GlobResult.from_dict(response.json())


def ls(
    sandbox: SandboxLike,
    path: str,
    *,
    limit: Optional[int],
    timeout: int,
    headers: RequestHeaders,
) -> Program[GlobResult]:
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
) -> Program[GrepResult]:
    """Search sandbox file contents for a literal string."""
    payload: dict[str, Any] = {"pattern": pattern, "path": path}
    if glob is not None:
        payload["glob"] = glob
    if limit is not None:
        payload["limit"] = limit
    response = yield from _request(
        sandbox,
        "POST",
        "grep",
        json=payload,
        timeout=timeout,
        headers=headers,
        file_path=path,
    )
    return GrepResult.from_dict(response.json())
