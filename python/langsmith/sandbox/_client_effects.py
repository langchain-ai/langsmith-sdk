"""Shared effect programs for synchronous and asynchronous sandbox clients."""

from __future__ import annotations

import posixpath
import shlex
import time
import uuid
from collections.abc import Callable, Generator, Mapping
from functools import partial
from pathlib import Path
from typing import Any, Optional, cast
from urllib.parse import quote

from langsmith._openapi_client._httpx import httpx
from langsmith.sandbox._effects import Call
from langsmith.sandbox._exceptions import (
    ResourceCreationError,
    ResourceNotFoundError,
    ResourceTimeoutError,
    SandboxAPIError,
)
from langsmith.sandbox._helpers import handle_client_http_error
from langsmith.sandbox._models import (
    ResourceStatus,
    Snapshot,
    SnapshotTag,
    _run_config_payload,
)

RequestHeaders = Optional[Mapping[str, str]]


def _quote_path_segment(value: str) -> str:
    if not value:
        raise ValueError("URL path segment must be a non-empty string")
    return quote(value, safe="")


def _quote_reference_segment(value: str) -> str:
    if not value:
        raise ValueError("URL path segment must be a non-empty string")
    return quote(value, safe=":")


def _box_url(base_url: str, name: str, *segments: str) -> str:
    suffix = "/" + "/".join(segments) if segments else ""
    return f"{base_url}/boxes/{_quote_path_segment(name)}{suffix}"


def get_sandbox_status(
    client: Any, name: str, *, headers: RequestHeaders
) -> Generator[Call[Any], Any, ResourceStatus]:
    """Get the provisioning status of a sandbox."""
    url = _box_url(client._base_url, name, "status")
    try:
        response = yield from Call(
            lambda: client._http.get(url, headers=client._request_headers(headers))
        )
        response.raise_for_status()
        return ResourceStatus.from_dict(response.json())
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            raise ResourceNotFoundError(
                f"Sandbox '{name}' not found", resource_type="sandbox"
            ) from error
        handle_client_http_error(error)
        raise


def wait_for_sandbox(
    client: Any,
    name: str,
    *,
    timeout: int,
    poll_interval: float,
    headers: RequestHeaders,
    sleep: Callable[[float], Any],
) -> Generator[Call[Any], Any, Any]:
    """Poll until a sandbox reaches a terminal status."""
    deadline = time.monotonic() + timeout
    while True:
        status = yield from Call(
            lambda: client.get_sandbox_status(name, headers=headers)
        )
        if status.status == "ready":
            return (yield from Call(lambda: client.get_sandbox(name, headers=headers)))
        if status.status == "failed":
            raise ResourceCreationError(
                status.status_message or "Sandbox provisioning failed",
                resource_type="sandbox",
            )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ResourceTimeoutError(
                f"Sandbox '{name}' not ready after {timeout}s",
                resource_type="sandbox",
                last_status=status.status,
            )
        yield from Call(lambda: sleep(min(poll_interval, remaining)))


def start_sandbox(
    client: Any,
    name: str,
    *,
    timeout: int,
    headers: RequestHeaders,
) -> Generator[Call[Any], Any, Any]:
    """Start a stopped sandbox and wait until ready."""
    url = _box_url(client._base_url, name, "start")
    try:
        response = yield from Call(
            lambda: client._http.post(
                url, json={}, headers=client._request_headers(headers)
            )
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            raise ResourceNotFoundError(
                f"Sandbox '{name}' not found", resource_type="sandbox"
            ) from error
        handle_client_http_error(error)
    return (
        yield from Call(
            lambda: client.wait_for_sandbox(name, timeout=timeout, headers=headers)
        )
    )


def stop_sandbox(
    client: Any, name: str, *, headers: RequestHeaders
) -> Generator[Call[Any], Any, None]:
    """Stop a running sandbox."""
    url = _box_url(client._base_url, name, "stop")
    try:
        response = yield from Call(
            lambda: client._http.post(
                url, json={}, headers=client._request_headers(headers)
            )
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            raise ResourceNotFoundError(
                f"Sandbox '{name}' not found", resource_type="sandbox"
            ) from error
        handle_client_http_error(error)


def create_snapshot(
    client: Any,
    name: str,
    docker_image: str,
    fs_capacity_bytes: int,
    *,
    tag: Optional[str],
    registry_id: Optional[str],
    run_config: Any,
    timeout: int,
    headers: RequestHeaders,
) -> Generator[Call[Any], Any, Snapshot]:
    """Build a snapshot from a Docker image."""
    payload: dict[str, Any] = {
        "name": name,
        "docker_image": docker_image,
        "fs_capacity_bytes": fs_capacity_bytes,
    }
    if tag is not None:
        payload["tag"] = tag
    if registry_id is not None:
        payload["registry_id"] = registry_id
    if run_config is not None:
        payload["run_config"] = _run_config_payload(run_config)
    try:
        response = yield from Call(
            lambda: client._http.post(
                f"{client._base_url}/snapshots",
                json=payload,
                headers=client._request_headers(headers),
            )
        )
        response.raise_for_status()
        snapshot = Snapshot.from_dict(response.json())
    except httpx.HTTPStatusError as error:
        handle_client_http_error(error)
        raise
    return (
        yield from Call(
            lambda: client.wait_for_snapshot(
                snapshot.id, timeout=timeout, headers=headers
            )
        )
    )


def _enter_sandbox(sandbox: Any) -> Any:
    enter = getattr(sandbox, "__aenter__", None) or sandbox.__enter__
    return enter()


def _exit_sandbox(
    sandbox: Any,
    exc_type: Optional[type],
    exc_value: Optional[BaseException],
    exc_tb: Any,
) -> Any:
    exit_method = getattr(sandbox, "__aexit__", None) or sandbox.__exit__
    return exit_method(exc_type, exc_value, exc_tb)


def create_snapshot_from_dockerfile(
    client: Any,
    name: str,
    dockerfile: Any,
    fs_capacity_bytes: Optional[int],
    *,
    context: Any,
    build_args: Optional[Mapping[str, str]],
    target: Optional[str],
    on_build_log: Optional[Callable[[str], Any]],
    vcpus: Optional[int],
    mem_bytes: Optional[int],
    timeout: int,
    headers: RequestHeaders,
    resolve_context: Callable[[Any, Any], tuple[Path, str]],
    make_context_tar: Callable[[Path], Any],
    make_build_command: Callable[..., str],
) -> Generator[Call[Any], Any, Snapshot]:
    """Build a snapshot from a local Dockerfile context."""
    context_path, dockerfile_rel = resolve_context(dockerfile, context)
    builder_name = f"snapshot-builder-{uuid.uuid4().hex[:12]}"
    build_root = f"/var/lib/langsmith-build/{uuid.uuid4().hex[:12]}"
    remote_context = posixpath.join(build_root, "context")
    remote_tar = posixpath.join(build_root, "context.tar")
    image_ref = f"langsmith-snapshot-build:{uuid.uuid4().hex}"
    buildkit_root = posixpath.join(build_root, "buildkit-root")
    buildkit_run = posixpath.join(build_root, "buildkit-run")
    sandbox_context = yield from Call(
        lambda: client.sandbox(
            name=builder_name,
            timeout=timeout,
            vcpus=vcpus,
            mem_bytes=mem_bytes,
            fs_capacity_bytes=fs_capacity_bytes,
            headers=headers,
        )
    )
    sandbox = yield from Call(lambda: _enter_sandbox(sandbox_context))
    try:
        content = yield from Call(lambda: make_context_tar(context_path))
        yield from Call(
            lambda: sandbox.write(remote_tar, content, timeout=timeout, headers=headers)
        )
        yield from Call(
            lambda: sandbox.run(
                "rm -rf "
                + shlex.quote(remote_context)
                + " && mkdir -p "
                + shlex.quote(remote_context)
                + " && tar -xf "
                + shlex.quote(remote_tar)
                + " -C "
                + shlex.quote(remote_context),
                timeout=timeout,
                headers=headers,
            )
        )
        result = yield from Call(
            lambda: sandbox.run(
                make_build_command(
                    remote_context=remote_context,
                    dockerfile_rel=dockerfile_rel,
                    image_ref=image_ref,
                    buildkit_root=buildkit_root,
                    buildkit_run=buildkit_run,
                    build_args=build_args,
                    target=target,
                ),
                timeout=timeout,
                on_stdout=on_build_log,
                on_stderr=on_build_log,
                headers=headers,
            )
        )
        if result.exit_code != 0:
            raise ResourceCreationError(
                "Dockerfile snapshot build failed", resource_type="snapshot"
            )
        snapshot = yield from Call(
            lambda: client.capture_snapshot(
                sandbox.name,
                name,
                docker_image=image_ref,
                fs_capacity_bytes=fs_capacity_bytes,
                timeout=timeout,
                headers=headers,
            )
        )
    except BaseException as error:
        suppressed = yield from Call(
            partial(
                _exit_sandbox,
                sandbox_context,
                type(error),
                error,
                error.__traceback__,
            )
        )
        if not suppressed:
            raise
        return cast(Snapshot, None)
    yield from Call(lambda: _exit_sandbox(sandbox_context, None, None, None))
    return snapshot


def capture_snapshot(
    client: Any,
    sandbox_name: str,
    name: str,
    *,
    tag: Optional[str],
    docker_image: Optional[str],
    fs_capacity_bytes: Optional[int],
    run_config: Any,
    timeout: int,
    headers: RequestHeaders,
) -> Generator[Call[Any], Any, Snapshot]:
    """Capture a snapshot from a running sandbox."""
    payload: dict[str, Any] = {"name": name}
    if tag is not None:
        payload["tag"] = tag
    if docker_image is not None:
        payload["docker_image"] = docker_image
    if fs_capacity_bytes is not None:
        payload["fs_capacity_bytes"] = fs_capacity_bytes
    if run_config is not None:
        payload["run_config"] = _run_config_payload(run_config)
    try:
        response = yield from Call(
            lambda: client._http.post(
                f"{client._base_url}/boxes/{_quote_path_segment(sandbox_name)}/snapshot",
                json=payload,
                headers=client._request_headers(headers),
            )
        )
        response.raise_for_status()
        snapshot = Snapshot.from_dict(response.json())
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            raise ResourceNotFoundError(
                f"Sandbox '{sandbox_name}' not found", resource_type="sandbox"
            ) from error
        handle_client_http_error(error)
        raise
    return (
        yield from Call(
            lambda: client.wait_for_snapshot(
                snapshot.id, timeout=timeout, headers=headers
            )
        )
    )


def get_snapshot(
    client: Any, snapshot_id: str, *, headers: RequestHeaders
) -> Generator[Call[Any], Any, Snapshot]:
    """Get a snapshot by ID or Docker-style reference."""
    url = f"{client._base_url}/snapshots/{_quote_reference_segment(snapshot_id)}"
    try:
        response = yield from Call(
            lambda: client._http.get(url, headers=client._request_headers(headers))
        )
        response.raise_for_status()
        return Snapshot.from_dict(response.json())
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            raise ResourceNotFoundError(
                f"Snapshot '{snapshot_id}' not found", resource_type="snapshot"
            ) from error
        handle_client_http_error(error)
        raise


def list_snapshot_tags(
    client: Any, name: str, *, headers: RequestHeaders
) -> Generator[Call[Any], Any, list[SnapshotTag]]:
    """List every tag published under a snapshot name."""
    url = f"{client._base_url}/snapshots-by-name/{_quote_path_segment(name)}"
    try:
        response = yield from Call(
            lambda: client._http.get(url, headers=client._request_headers(headers))
        )
        response.raise_for_status()
        return [SnapshotTag.from_dict(tag) for tag in response.json().get("tags") or []]
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            raise ResourceNotFoundError(
                f"Snapshot name '{name}' not found", resource_type="snapshot"
            ) from error
        handle_client_http_error(error)
        raise


def list_snapshots(
    client: Any,
    *,
    name_contains: Optional[str],
    limit: Optional[int],
    offset: Optional[int],
    headers: RequestHeaders,
) -> Generator[Call[Any], Any, list[Snapshot]]:
    """List one page of snapshots."""
    url = f"{client._base_url}/snapshots"
    params: dict[str, Any] = {}
    if name_contains is not None:
        params["name_contains"] = name_contains
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    try:
        response = yield from Call(
            lambda: client._http.get(
                url,
                params=params or None,
                headers=client._request_headers(headers),
            )
        )
        response.raise_for_status()
        return [
            Snapshot.from_dict(item) for item in response.json().get("snapshots", [])
        ]
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            raise SandboxAPIError(
                f"API endpoint not found: {url}. Check that api_endpoint is correct."
            ) from error
        handle_client_http_error(error)
        raise


def delete_snapshot(
    client: Any, snapshot_id: str, *, headers: RequestHeaders
) -> Generator[Call[Any], Any, None]:
    """Delete a snapshot."""
    url = f"{client._base_url}/snapshots/{_quote_path_segment(snapshot_id)}"
    try:
        response = yield from Call(
            lambda: client._http.delete(url, headers=client._request_headers(headers))
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            raise ResourceNotFoundError(
                f"Snapshot '{snapshot_id}' not found", resource_type="snapshot"
            ) from error
        handle_client_http_error(error)


def wait_for_snapshot(
    client: Any,
    snapshot_id: str,
    *,
    timeout: int,
    poll_interval: float,
    headers: RequestHeaders,
    sleep: Callable[[float], Any],
) -> Generator[Call[Any], Any, Snapshot]:
    """Poll until a snapshot reaches a terminal status."""
    deadline = time.monotonic() + timeout
    while True:
        snapshot = yield from Call(
            lambda: client.get_snapshot(snapshot_id, headers=headers)
        )
        if snapshot.status == "ready":
            return snapshot
        if snapshot.status == "failed":
            raise ResourceCreationError(
                snapshot.status_message or "Snapshot build failed",
                resource_type="snapshot",
            )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ResourceTimeoutError(
                f"Snapshot '{snapshot_id}' not ready after {timeout}s",
                resource_type="snapshot",
                last_status=snapshot.status,
            )
        yield from Call(lambda: sleep(min(poll_interval, remaining)))
