"""Async SandboxClient class for interacting with the sandbox server API."""

from __future__ import annotations

import asyncio
import os
import posixpath
import uuid
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, Optional, Union

import httpx

from langsmith._openapi_client._base_client import make_request_options
from langsmith._openapi_client._exceptions import APIConnectionError, APIStatusError
from langsmith.sandbox._async_sandbox import AsyncSandbox
from langsmith.sandbox._client import (
    SandboxClient,
    _get_langsmith_api_url,
    _get_sandbox_api_endpoint,
    _get_sandbox_request_headers,
    _make_docker_context_tar,
    _make_dockerfile_build_command,
    _quote_path_segment,
    _resolve_dockerfile_context,
)
from langsmith.sandbox._exceptions import (
    ResourceCreationError,
    ResourceNameConflictError,
    ResourceNotFoundError,
    ResourceTimeoutError,
    SandboxAPIError,
    SandboxConnectionError,
)
from langsmith.sandbox._helpers import (
    handle_client_http_error,
    handle_sandbox_creation_error,
    merge_headers,
    validate_service_params,
    validate_ttl,
)
from langsmith.sandbox._models import (
    AsyncServiceURL,
    ResourceStatus,
    Snapshot,
)
from langsmith.sandbox._mounts import (
    SandboxMountConfig,
    validate_mount_config_proxy_config,
)
from langsmith.sandbox._proxy_config import SandboxProxyConfig

if TYPE_CHECKING:
    from langsmith._openapi_client.resources.sandboxes.registries import (
        AsyncRegistriesResource,
    )
    from langsmith.async_client import AsyncClient


RequestHeaders = Optional[Mapping[str, str]]


class AsyncSandboxClient:
    """Async client for interacting with the Sandbox Server API.

    This client provides an async interface for managing sandboxes and snapshots.

    Example:
        # Uses LANGSMITH_ENDPOINT and LANGSMITH_API_KEY from environment
        async with AsyncSandboxClient() as client:
            # Create a sandbox with the default runtime and run commands
            async with await client.sandbox() as sandbox:
                result = await sandbox.run("python --version")
                print(result.stdout)
    """

    def __init__(
        self,
        *,
        client: Optional[AsyncClient] = None,
        api_endpoint: Optional[str] = None,
        timeout: float = 10.0,
        api_key: Optional[str] = None,
        max_retries: int = 3,
        headers: Optional[Mapping[str, str]] = None,
    ):
        """Initialize the AsyncSandboxClient.

        Args:
            client: Main async LangSmith client whose resolved endpoint,
                    authentication, workspace, headers, and HTTP transport should
                    be reused. When provided, ``timeout``, ``api_key``,
                    ``max_retries``, and ``headers`` are ignored.
            api_endpoint: Full URL of the sandbox API endpoint. If not provided,
                          derived from the main client's API endpoint.
            timeout: Default HTTP timeout in seconds when constructing a client.
            api_key: API key used when constructing a client.
            max_retries: Maximum retries for control-plane requests when
                         constructing a client. Set to 0 to disable retries.
            headers: Optional default headers attached to every request on this
                     facade when constructing a client, including direct dataplane
                     HTTP and WebSocket requests.
        """
        if client is None:
            from langsmith.async_client import AsyncClient

            client = AsyncClient(
                api_url=(
                    _get_langsmith_api_url(api_endpoint)
                    if api_endpoint is not None
                    else None
                ),
                api_key=api_key,
                timeout_ms=int(timeout * 1000),
                retry_config={"max_retries": max_retries},
                headers=dict(headers) if headers else None,
            )
            self._owns_langsmith_client = True
        else:
            self._owns_langsmith_client = False

        self._langsmith_client: AsyncClient = client
        self._base_url = (
            api_endpoint.rstrip("/")
            if api_endpoint is not None
            else _get_sandbox_api_endpoint(client._api_url)
        )
        self._api_key = client.api_key
        self._timeout = timeout
        self._max_retries = max_retries
        self._default_headers = dict(client.headers)
        if self._owns_langsmith_client:
            client._langsmith_api.max_retries = max_retries
        self._http = client._langsmith_api._client

    @property
    def registries(self) -> AsyncRegistriesResource:
        """Manage sandbox image registries: create, list, retrieve, update, delete.

        A registry stores credentials for pulling private images. Create one,
        then pass its ``id`` as ``registry_id`` when building a snapshot.

        Example:
            registry = await client.registries.create(
                name="internal",
                url="registry.example.com",
                username="robot",
                password=os.environ["REGISTRY_PASSWORD"],
            )
            snapshot = await client.create_snapshot(
                "internal-python",
                docker_image="registry.example.com/internal/python:3.12",
                fs_capacity_bytes=2 * 1024**3,
                registry_id=registry.id,
            )
        """
        return self._langsmith_client.sandboxes.registries

    def _request_headers(self, headers: RequestHeaders) -> dict[str, str]:
        """Build full headers for requests sent directly to a dataplane URL."""
        client_headers = {
            name: value
            for name, value in self._langsmith_client._compute_headers().items()
            if name.lower() != "content-type"
        }
        return merge_headers(client_headers, headers)

    async def _dataplane_request(
        self,
        method: str,
        url: str,
        *,
        headers: RequestHeaders = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Send a direct dataplane request on the main client's HTTP pool."""
        await self._langsmith_client._ensure_profile_auth()
        try:
            return await self._http.request(
                method,
                url,
                headers=self._request_headers(headers),
                **kwargs,
            )
        except httpx.RequestError as exc:
            raise SandboxConnectionError(f"Failed to connect to server: {exc}") from exc

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json: Optional[dict[str, Any]] = None,
        params: Optional[Mapping[str, Any]] = None,
        headers: RequestHeaders = None,
        timeout: Optional[float] = None,
    ) -> httpx.Response:
        """Send a sandbox REST request through the main client's pipeline."""
        await self._langsmith_client._ensure_profile_auth()
        headers = _get_sandbox_request_headers(
            self._langsmith_client._compute_headers(), headers
        )
        api = self._langsmith_client._langsmith_api
        options = make_request_options(
            extra_headers=headers,
            extra_query=params,
            timeout=timeout,
        )
        try:
            if method == "GET":
                return await api.get(url, cast_to=httpx.Response, options=options)
            if method == "POST":
                return await api.post(
                    url, cast_to=httpx.Response, body=json, options=options
                )
            if method == "PATCH":
                return await api.patch(
                    url, cast_to=httpx.Response, body=json, options=options
                )
            if method == "DELETE":
                return await api.delete(url, cast_to=httpx.Response, options=options)
            raise ValueError(f"Unsupported HTTP method: {method}")
        except APIStatusError as exc:
            raise httpx.HTTPStatusError(
                str(exc), request=exc.request, response=exc.response
            ) from exc
        except APIConnectionError as exc:
            raise SandboxConnectionError(f"Failed to connect to server: {exc}") from exc

    def _ws_default_headers(self, headers: RequestHeaders) -> Optional[dict[str, str]]:
        """Merge constructor-supplied default headers with per-request overrides.

        Used by the WebSocket exec path so headers like ``X-Service-Key``
        set on the client are attached to the WS upgrade request.
        """
        return self._request_headers(headers)

    def to_sync(self) -> SandboxClient:
        """Create a SandboxClient with the same configuration.

        The returned client has its own HTTP connection pool; close it
        independently (``client.close()`` or ``with``).

        Returns:
            SandboxClient with the same endpoint, credentials, timeout,
            retry, and header configuration.
        """
        return SandboxClient(
            api_endpoint=self._base_url,
            timeout=self._timeout,
            api_key=self._api_key,
            max_retries=self._max_retries,
            headers=self._default_headers or None,
        )

    async def aclose(self) -> None:
        """Close the async HTTP client."""
        if self._owns_langsmith_client:
            await self._langsmith_client.aclose()

    def __del__(self) -> None:
        """Best-effort cleanup of the async HTTP client on garbage collection.

        If an event loop is running, schedules ``aclose()`` as a task.
        Otherwise the underlying sockets will be closed by the GC.
        For deterministic cleanup, use ``async with`` or ``await aclose()``.
        """
        try:
            if self._owns_langsmith_client and not self._http.is_closed:
                try:
                    loop = asyncio.get_running_loop()
                    if not loop.is_closed():
                        loop.create_task(self.aclose())
                except RuntimeError:
                    pass
        except Exception:
            pass

    async def __aenter__(self) -> AsyncSandboxClient:
        """Enter async context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Exit async context manager."""
        await self.aclose()

    def __repr__(self) -> str:
        """Return a string representation of the instance.

        Returns:
            The string representation of the instance.
        """
        return f"AsyncSandboxClient (API URL: {self._base_url})"

    # ========================================================================
    # Sandbox Operations
    # ========================================================================

    async def sandbox(
        self,
        snapshot_id: Optional[str] = None,
        *,
        snapshot_name: Optional[str] = None,
        name: Optional[str] = None,
        timeout: int = 30,
        idle_ttl_seconds: Optional[int] = None,
        delete_after_stop_seconds: Optional[int] = None,
        vcpus: Optional[int] = None,
        mem_bytes: Optional[int] = None,
        fs_capacity_bytes: Optional[int] = None,
        mount_config: Optional[SandboxMountConfig] = None,
        proxy_config: Optional[SandboxProxyConfig] = None,
        headers: RequestHeaders = None,
    ) -> AsyncSandbox:
        """Create a sandbox and return an AsyncSandbox instance.

        This is the primary method for creating sandboxes. Use it as an
        async context manager for automatic cleanup:

            async with await client.sandbox(snapshot_id="<uuid>") as sandbox:
                result = await sandbox.run("echo hello")

            # Resolve by snapshot name instead of ID:
            async with await client.sandbox(snapshot_name="my-snap") as sandbox:
                result = await sandbox.run("echo hello")

        The sandbox is automatically deleted when exiting the context manager.
        For sandboxes with manual lifecycle management, use create_sandbox().

        Args:
            snapshot_id: Optional snapshot ID to boot from. Mutually exclusive
                with ``snapshot_name``.
            snapshot_name: Snapshot name to boot from. Resolved server-side to a
                snapshot owned by the caller's tenant. Mutually exclusive with
                ``snapshot_id``.
            name: Optional sandbox name (auto-generated if not provided).
            timeout: Timeout in seconds when waiting for ready.
            idle_ttl_seconds: Idle timeout in seconds. The launcher
                automatically stops the sandbox after this duration of
                inactivity. Must be a multiple of 60. ``0`` explicitly
                disables the idle stop. When omitted (``None``), the server
                applies a default of ``600`` seconds (10 minutes).
            delete_after_stop_seconds: Seconds after the sandbox enters the
                ``stopped`` state before it (and its filesystem clone) are
                permanently deleted. Must be a multiple of 60. ``0`` disables
                stop-anchored deletion (manual cleanup required). When
                omitted (``None``), the server applies its configured default.
            vcpus: Number of vCPUs.
            mem_bytes: Memory in bytes.
            fs_capacity_bytes: Root filesystem capacity in bytes.
            mount_config: Mount configuration forwarded to the server as
                ``mount_config``. The backend expands mount auth into runtime
                proxy rules. Explicit AWS/GCP proxy rules in ``proxy_config``
                conflict with mount auth for the same provider.
            proxy_config: Per-sandbox proxy configuration forwarded to the
                server as-is. Shape matches the backend `proxy_config` field:
                ``{"rules": [...], "no_proxy": [...], "access_control":
                {"allow_list": [...]}}`` or ``{"access_control":
                {"deny_list": [...]}}``. Use ``access_control.allow_list`` to
                restrict outbound HTTPS to a set of host patterns (exact
                domains, globs like ``*.example.com``, IPs, CIDRs, or
                ``~regex``). Use ``proxy_config`` with provider rule helpers
                such as ``aws_auth`` to let the proxy sign supported
                AWS HTTPS requests on the sandbox's behalf.

        Returns:
            AsyncSandbox instance.

        Raises:
            ResourceTimeoutError: If timeout waiting for sandbox to be ready.
            ResourceCreationError: If sandbox creation fails.
            SandboxClientError: For other errors.
            ValueError: If TTL values are invalid, or if both ``snapshot_id`` and
                ``snapshot_name`` are provided.
        """
        sb = await self.create_sandbox(
            snapshot_id,
            snapshot_name=snapshot_name,
            name=name,
            timeout=timeout,
            idle_ttl_seconds=idle_ttl_seconds,
            delete_after_stop_seconds=delete_after_stop_seconds,
            vcpus=vcpus,
            mem_bytes=mem_bytes,
            fs_capacity_bytes=fs_capacity_bytes,
            mount_config=mount_config,
            proxy_config=proxy_config,
            headers=headers,
        )
        sb._auto_delete = True
        return sb

    async def create_sandbox(
        self,
        snapshot_id: Optional[str] = None,
        *,
        snapshot_name: Optional[str] = None,
        name: Optional[str] = None,
        timeout: int = 30,
        wait_for_ready: bool = True,
        idle_ttl_seconds: Optional[int] = None,
        delete_after_stop_seconds: Optional[int] = None,
        vcpus: Optional[int] = None,
        mem_bytes: Optional[int] = None,
        fs_capacity_bytes: Optional[int] = None,
        mount_config: Optional[SandboxMountConfig] = None,
        proxy_config: Optional[SandboxProxyConfig] = None,
        headers: RequestHeaders = None,
    ) -> AsyncSandbox:
        """Create a new Sandbox.

        The sandbox is NOT automatically deleted. Use delete_sandbox() for cleanup,
        or use sandbox() for automatic cleanup with a context manager.

        Args:
            snapshot_id: Optional snapshot ID to boot from. Mutually exclusive
                with ``snapshot_name``.
            snapshot_name: Snapshot name to boot from. Resolved server-side to a
                snapshot owned by the caller's tenant. Mutually exclusive with
                ``snapshot_id``.
            name: Optional sandbox name (auto-generated if not provided).
            timeout: Timeout in seconds when waiting for ready (only used when
                wait_for_ready=True).
            wait_for_ready: If True (default), block until sandbox is ready.
                If False, return immediately with status "provisioning". Use
                get_sandbox_status() or wait_for_sandbox() to poll for readiness.
            idle_ttl_seconds: Idle timeout in seconds. The launcher
                automatically stops the sandbox after this duration of
                inactivity. Must be a multiple of 60. ``0`` explicitly
                disables the idle stop. When omitted (``None``), the server
                applies a default of ``600`` seconds (10 minutes).
            delete_after_stop_seconds: Seconds after the sandbox enters the
                ``stopped`` state before it (and its filesystem clone) are
                permanently deleted. Must be a multiple of 60. ``0`` disables
                stop-anchored deletion (manual cleanup required). When
                omitted (``None``), the server applies its configured default.
            vcpus: Number of vCPUs.
            mem_bytes: Memory in bytes.
            fs_capacity_bytes: Root filesystem capacity in bytes.
            mount_config: Mount configuration forwarded to the server as
                ``mount_config``. The backend expands mount auth into runtime
                proxy rules. Explicit AWS/GCP proxy rules in ``proxy_config``
                conflict with mount auth for the same provider.
            proxy_config: Per-sandbox proxy configuration forwarded to the
                server as-is. Shape matches the backend `proxy_config` field:
                ``{"rules": [...], "no_proxy": [...], "access_control":
                {"allow_list": [...]}}`` or ``{"access_control":
                {"deny_list": [...]}}``. Use ``access_control.allow_list`` to
                restrict outbound HTTPS to a set of host patterns (exact
                domains, globs like ``*.example.com``, IPs, CIDRs, or
                ``~regex``). Use ``proxy_config`` with provider rule helpers
                such as ``aws_auth`` to let the proxy sign supported
                AWS HTTPS requests on the sandbox's behalf.

        Returns:
            Created AsyncSandbox. When wait_for_ready=False, the sandbox will have
            status="provisioning" and cannot be used for operations until ready.

        Raises:
            ResourceTimeoutError: If timeout waiting for sandbox to be ready.
            ResourceCreationError: If sandbox creation fails.
            SandboxClientError: For other errors.
            ValueError: If TTL values are invalid, or if both ``snapshot_id`` and
                ``snapshot_name`` are provided.
        """
        if snapshot_id and snapshot_name:
            raise ValueError("At most one of snapshot_id or snapshot_name may be set")
        validate_ttl(idle_ttl_seconds, "idle_ttl_seconds")
        validate_ttl(delete_after_stop_seconds, "delete_after_stop_seconds")

        url = f"{self._base_url}/boxes"

        payload: dict[str, Any] = {
            "wait_for_ready": wait_for_ready,
        }
        if snapshot_id:
            payload["snapshot_id"] = snapshot_id
        if snapshot_name:
            payload["snapshot_name"] = snapshot_name
        if wait_for_ready:
            payload["timeout"] = timeout
        if name:
            payload["name"] = name
        if idle_ttl_seconds is not None:
            payload["idle_ttl_seconds"] = idle_ttl_seconds
        if delete_after_stop_seconds is not None:
            payload["delete_after_stop_seconds"] = delete_after_stop_seconds
        if vcpus is not None:
            payload["vcpus"] = vcpus
        if mem_bytes is not None:
            payload["mem_bytes"] = mem_bytes
        if fs_capacity_bytes is not None:
            payload["fs_capacity_bytes"] = fs_capacity_bytes
        if mount_config is not None:
            validate_mount_config_proxy_config(mount_config, proxy_config)
            payload["mount_config"] = mount_config
        if proxy_config is not None:
            payload["proxy_config"] = proxy_config

        http_timeout = (timeout + 30) if wait_for_ready else 30

        try:
            response = await self._request(
                "POST",
                url,
                json=payload,
                timeout=http_timeout,
                headers=headers,
            )
            response.raise_for_status()
            return AsyncSandbox.from_dict(
                response.json(), client=self, auto_delete=False
            )
        except httpx.HTTPStatusError as e:
            handle_sandbox_creation_error(e)
            raise  # pragma: no cover

    async def get_sandbox(
        self, name: str, *, headers: RequestHeaders = None
    ) -> AsyncSandbox:
        """Get a Sandbox by name.

        The sandbox is NOT automatically deleted. Use delete_sandbox() for cleanup.

        Args:
            name: Sandbox name.

        Returns:
            AsyncSandbox.

        Raises:
            ResourceNotFoundError: If sandbox not found.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/boxes/{_quote_path_segment(name)}"

        try:
            response = await self._request("GET", url, headers=headers)
            response.raise_for_status()
            return AsyncSandbox.from_dict(
                response.json(), client=self, auto_delete=False
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Sandbox '{name}' not found", resource_type="sandbox"
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

    async def list_sandboxes(
        self, *, headers: RequestHeaders = None
    ) -> list[AsyncSandbox]:
        """List all Sandboxes.

        Returns:
            List of AsyncSandboxes.
        """
        url = f"{self._base_url}/boxes"

        try:
            response = await self._request("GET", url, headers=headers)
            response.raise_for_status()
            data = response.json()
            return [
                AsyncSandbox.from_dict(c, client=self, auto_delete=False)
                for c in data.get("sandboxes", [])
            ]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise SandboxAPIError(
                    f"API endpoint not found: {url}. "
                    f"Check that api_endpoint is correct."
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

    async def update_sandbox(
        self,
        name: str,
        *,
        new_name: Optional[str] = None,
        idle_ttl_seconds: Optional[int] = None,
        delete_after_stop_seconds: Optional[int] = None,
        headers: RequestHeaders = None,
    ) -> AsyncSandbox:
        """Update a sandbox's properties.

        Args:
            name: Current sandbox name.
            new_name: New display name.
            idle_ttl_seconds: Idle timeout in seconds. Must be a multiple of
                60. ``0`` disables idle-stop. ``None`` leaves the existing
                value unchanged.
            delete_after_stop_seconds: Seconds after entering ``stopped``
                before deletion. Must be a multiple of 60. ``0`` disables
                stop-anchored deletion. ``None`` leaves the existing value
                unchanged.

        Returns:
            Updated AsyncSandbox.

        Raises:
            ResourceNotFoundError: If sandbox not found.
            ResourceNameConflictError: If new_name is already in use.
            SandboxClientError: For other errors.
            ValueError: If TTL values are invalid.
        """
        validate_ttl(idle_ttl_seconds, "idle_ttl_seconds")
        validate_ttl(delete_after_stop_seconds, "delete_after_stop_seconds")

        url = f"{self._base_url}/boxes/{_quote_path_segment(name)}"
        payload: dict[str, Any] = {}
        if new_name is not None:
            payload["name"] = new_name
        if idle_ttl_seconds is not None:
            payload["idle_ttl_seconds"] = idle_ttl_seconds
        if delete_after_stop_seconds is not None:
            payload["delete_after_stop_seconds"] = delete_after_stop_seconds

        try:
            response = await self._request("PATCH", url, json=payload, headers=headers)
            response.raise_for_status()
            return AsyncSandbox.from_dict(
                response.json(), client=self, auto_delete=False
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Sandbox '{name}' not found", resource_type="sandbox"
                ) from e
            if e.response.status_code == 409:
                raise ResourceNameConflictError(
                    f"Sandbox name '{new_name}' already in use",
                    resource_type="sandbox",
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

    async def delete_sandbox(
        self, name: str, *, headers: RequestHeaders = None
    ) -> None:
        """Delete a Sandbox.

        Args:
            name: Sandbox name.

        Raises:
            ResourceNotFoundError: If sandbox not found.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/boxes/{_quote_path_segment(name)}"

        try:
            response = await self._request("DELETE", url, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Sandbox '{name}' not found", resource_type="sandbox"
                ) from e
            handle_client_http_error(e)

    async def get_sandbox_status(
        self, name: str, *, headers: RequestHeaders = None
    ) -> ResourceStatus:
        """Get the provisioning status of a sandbox.

        This is a lightweight endpoint designed for high-frequency polling
        during sandbox provisioning. It returns only the status fields
        without full sandbox data.

        Args:
            name: Sandbox name.

        Returns:
            ResourceStatus with status and status_message.

        Raises:
            ResourceNotFoundError: If sandbox not found.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/boxes/{_quote_path_segment(name)}/status"

        try:
            response = await self._request("GET", url, headers=headers)
            response.raise_for_status()
            return ResourceStatus.from_dict(response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Sandbox '{name}' not found", resource_type="sandbox"
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

    async def service(
        self,
        name: str,
        port: int,
        *,
        expires_in_seconds: int = 600,
        headers: RequestHeaders = None,
    ) -> AsyncServiceURL:
        """Get an authenticated URL for a service running inside a sandbox.

        Returns an :class:`AsyncServiceURL` whose async accessors
        auto-refresh the token transparently before it expires.  The
        object also provides async HTTP helper methods (``.get``,
        ``.post``, etc.) that inject the authentication header
        automatically.

        Args:
            name: Sandbox name.
            port: Port the service is listening on inside the sandbox.
            expires_in_seconds: Token TTL in seconds (1--86400, default 600).
            headers: Optional per-request header overrides.

        Returns:
            AsyncServiceURL with auto-refreshing token and HTTP helpers.

        Raises:
            ResourceNotFoundError: If sandbox not found.
            ValueError: If port or expires_in_seconds is out of range.
            SandboxClientError: For other errors.
        """
        validate_service_params(port, expires_in_seconds)
        url = f"{self._base_url}/boxes/{_quote_path_segment(name)}/service-url"
        payload = {"port": port, "expires_in_seconds": expires_in_seconds}

        async def _refresher() -> AsyncServiceURL:
            return await self.service(
                name,
                port,
                expires_in_seconds=expires_in_seconds,
                headers=headers,
            )

        try:
            response = await self._request("POST", url, json=payload, headers=headers)
            response.raise_for_status()
            return AsyncServiceURL.from_dict(response.json(), _refresher=_refresher)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Sandbox '{name}' not found", resource_type="sandbox"
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

    async def wait_for_sandbox(
        self,
        name: str,
        *,
        timeout: int = 120,
        poll_interval: float = 1.0,
        headers: RequestHeaders = None,
    ) -> AsyncSandbox:
        """Poll until a sandbox reaches "ready" or "failed" status.

        Uses the lightweight status endpoint for polling, then fetches the
        full sandbox data once ready.

        Args:
            name: Sandbox name.
            timeout: Maximum time to wait in seconds.
            poll_interval: Time between status checks in seconds.

        Returns:
            AsyncSandbox in "ready" status.

        Raises:
            ResourceCreationError: If sandbox status becomes "failed".
            ResourceTimeoutError: If timeout expires while still "provisioning".
            ResourceNotFoundError: If sandbox not found.
            SandboxClientError: For other errors.
        """
        import time

        deadline = time.monotonic() + timeout
        while True:
            status = await self.get_sandbox_status(name, headers=headers)
            if status.status == "ready":
                return await self.get_sandbox(name, headers=headers)
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
            await asyncio.sleep(min(poll_interval, remaining))

    async def start_sandbox(
        self,
        name: str,
        *,
        timeout: int = 120,
        headers: RequestHeaders = None,
    ) -> AsyncSandbox:
        """Start a stopped sandbox and wait until ready.

        Args:
            name: Sandbox name.
            timeout: Timeout in seconds when waiting for ready.

        Returns:
            AsyncSandbox in "ready" status.

        Raises:
            ResourceNotFoundError: If sandbox not found.
            ResourceCreationError: If sandbox fails during startup.
            ResourceTimeoutError: If sandbox doesn't become ready within timeout.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/boxes/{_quote_path_segment(name)}/start"

        try:
            response = await self._request("POST", url, json={}, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Sandbox '{name}' not found", resource_type="sandbox"
                ) from e
            handle_client_http_error(e)

        return await self.wait_for_sandbox(name, timeout=timeout, headers=headers)

    async def stop_sandbox(self, name: str, *, headers: RequestHeaders = None) -> None:
        """Stop a running sandbox (preserves sandbox files for later restart).

        Args:
            name: Sandbox name.

        Raises:
            ResourceNotFoundError: If sandbox not found.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/boxes/{_quote_path_segment(name)}/stop"

        try:
            response = await self._request("POST", url, json={}, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Sandbox '{name}' not found", resource_type="sandbox"
                ) from e
            handle_client_http_error(e)

    # ========================================================================
    # Snapshot Operations
    # ========================================================================

    async def create_snapshot(
        self,
        name: str,
        docker_image: str,
        fs_capacity_bytes: int,
        *,
        registry_id: Optional[str] = None,
        timeout: int = 60,
        headers: RequestHeaders = None,
    ) -> Snapshot:
        """Build a snapshot from a Docker image.

        Blocks until the snapshot is ready (polls with 2s interval).

        Args:
            name: Snapshot name.
            docker_image: Docker image to build from (e.g., "python:3.12-slim").
            fs_capacity_bytes: Filesystem capacity in bytes.
            registry_id: Private registry ID.
            timeout: Timeout in seconds when waiting for ready.

        Returns:
            Snapshot in "ready" status.

        Raises:
            ResourceTimeoutError: If snapshot doesn't become ready within timeout.
            ResourceCreationError: If snapshot build fails.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/snapshots"

        payload: dict[str, Any] = {
            "name": name,
            "docker_image": docker_image,
            "fs_capacity_bytes": fs_capacity_bytes,
        }
        if registry_id is not None:
            payload["registry_id"] = registry_id

        try:
            response = await self._request("POST", url, json=payload, headers=headers)
            response.raise_for_status()
            snapshot = Snapshot.from_dict(response.json())
        except httpx.HTTPStatusError as e:
            handle_client_http_error(e)
            raise  # pragma: no cover

        return await self.wait_for_snapshot(
            snapshot.id, timeout=timeout, headers=headers
        )

    async def create_snapshot_from_dockerfile(
        self,
        name: str,
        dockerfile: Union[str, os.PathLike[str]],
        fs_capacity_bytes: Optional[int] = None,
        *,
        context: Union[str, os.PathLike[str]] = ".",
        build_args: Optional[Mapping[str, str]] = None,
        target: Optional[str] = None,
        on_build_log: Optional[Callable[[str], Any]] = None,
        vcpus: Optional[int] = None,
        mem_bytes: Optional[int] = None,
        timeout: int = 60,
        headers: RequestHeaders = None,
    ) -> Snapshot:
        """Build a snapshot from a local Dockerfile context.

        When ``fs_capacity_bytes`` is omitted, the server applies its default.
        ``vcpus`` and ``mem_bytes`` size the temporary builder sandbox. The
        build runs BuildKit plus the native snapshotter's layer copies inside
        it, which contend for a single core by default, so giving the builder
        an extra vCPU can cut a cold build's wall time substantially.
        """
        context_path, dockerfile_rel = _resolve_dockerfile_context(dockerfile, context)

        builder_name = f"snapshot-builder-{uuid.uuid4().hex[:12]}"
        # Stage the build on the capacity-backed root filesystem, not /tmp.
        # Inside the sandbox /tmp is a RAM-backed tmpfs that fs_capacity_bytes
        # does not size, and BuildKit's native snapshotter writes a full copy
        # of every layer under its root, so a /tmp build exhausts guest RAM and
        # fails with "No space left on device".
        build_root = f"/var/lib/langsmith-build/{uuid.uuid4().hex[:12]}"
        remote_context = posixpath.join(build_root, "context")
        remote_tar = posixpath.join(build_root, "context.tar")
        image_ref = f"langsmith-snapshot-build:{uuid.uuid4().hex}"
        buildkit_root = posixpath.join(build_root, "buildkit-root")
        buildkit_run = posixpath.join(build_root, "buildkit-run")

        async with await self.sandbox(
            name=builder_name,
            timeout=timeout,
            vcpus=vcpus,
            mem_bytes=mem_bytes,
            fs_capacity_bytes=fs_capacity_bytes,
            headers=headers,
        ) as sandbox:
            await sandbox.write(
                remote_tar,
                await asyncio.to_thread(_make_docker_context_tar, context_path),
                timeout=timeout,
                headers=headers,
            )
            await sandbox.run(
                "rm -rf "
                + remote_context
                + " && mkdir -p "
                + remote_context
                + " && tar -xf "
                + remote_tar
                + " -C "
                + remote_context,
                timeout=timeout,
                headers=headers,
            )

            result = await sandbox.run(
                _make_dockerfile_build_command(
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
            if result.exit_code != 0:
                raise ResourceCreationError(
                    "Dockerfile snapshot build failed",
                    resource_type="snapshot",
                )
            return await self.capture_snapshot(
                sandbox.name,
                name,
                docker_image=image_ref,
                fs_capacity_bytes=fs_capacity_bytes,
                timeout=timeout,
                headers=headers,
            )

    async def capture_snapshot(
        self,
        sandbox_name: str,
        name: str,
        *,
        docker_image: Optional[str] = None,
        fs_capacity_bytes: Optional[int] = None,
        timeout: int = 60,
        headers: RequestHeaders = None,
    ) -> Snapshot:
        """Capture a snapshot from a running sandbox.

        Blocks until the snapshot is ready (polls with 2s interval).

        Args:
            sandbox_name: Name of the sandbox to capture from.
            name: Snapshot name.
            timeout: Timeout in seconds when waiting for ready.

        Returns:
            Snapshot in "ready" status.

        Raises:
            ResourceNotFoundError: If sandbox not found.
            ResourceTimeoutError: If snapshot doesn't become ready within timeout.
            ResourceCreationError: If snapshot capture fails.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/boxes/{_quote_path_segment(sandbox_name)}/snapshot"

        payload: dict[str, Any] = {"name": name}
        if docker_image is not None:
            payload["docker_image"] = docker_image
        if fs_capacity_bytes is not None:
            payload["fs_capacity_bytes"] = fs_capacity_bytes

        try:
            response = await self._request("POST", url, json=payload, headers=headers)
            response.raise_for_status()
            snapshot = Snapshot.from_dict(response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Sandbox '{sandbox_name}' not found", resource_type="sandbox"
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

        return await self.wait_for_snapshot(
            snapshot.id, timeout=timeout, headers=headers
        )

    async def get_snapshot(
        self, snapshot_id: str, *, headers: RequestHeaders = None
    ) -> Snapshot:
        """Get a snapshot by ID.

        Args:
            snapshot_id: Snapshot UUID.

        Returns:
            Snapshot.

        Raises:
            ResourceNotFoundError: If snapshot not found.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/snapshots/{_quote_path_segment(snapshot_id)}"

        try:
            response = await self._request("GET", url, headers=headers)
            response.raise_for_status()
            return Snapshot.from_dict(response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Snapshot '{snapshot_id}' not found", resource_type="snapshot"
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

    async def list_snapshots(
        self,
        *,
        name_contains: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        headers: RequestHeaders = None,
    ) -> list[Snapshot]:
        """List snapshots.

        The backend always paginates this endpoint. When ``limit`` is omitted
        the server applies a default page size (currently 50), so a single
        call is not guaranteed to return every snapshot. To iterate through
        all results, repeat the call with increasing ``offset`` values (or an
        explicit ``limit``) until fewer than ``limit`` snapshots come back.

        Args:
            name_contains: Optional case-insensitive substring filter applied
                to snapshot names server-side.
            limit: Optional maximum number of snapshots to return for a single
                request. Must be between 1 and 500 (inclusive); the server
                rejects values outside that range. Defaults to 50 server-side
                when omitted.
            offset: Optional number of snapshots to skip before returning
                results. Must be ``>= 0``. Useful for paginating through
                large result sets in combination with ``limit``.

        Returns:
            A single page of Snapshots matching the provided filters.
        """
        url = f"{self._base_url}/snapshots"

        params: dict[str, Any] = {}
        if name_contains is not None:
            params["name_contains"] = name_contains
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        try:
            response = await self._request(
                "GET",
                url,
                params=params or None,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return [Snapshot.from_dict(s) for s in data.get("snapshots", [])]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise SandboxAPIError(
                    f"API endpoint not found: {url}. "
                    f"Check that api_endpoint is correct."
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

    async def delete_snapshot(
        self, snapshot_id: str, *, headers: RequestHeaders = None
    ) -> None:
        """Delete a snapshot.

        Args:
            snapshot_id: Snapshot UUID.

        Raises:
            ResourceNotFoundError: If snapshot not found.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/snapshots/{_quote_path_segment(snapshot_id)}"

        try:
            response = await self._request("DELETE", url, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Snapshot '{snapshot_id}' not found", resource_type="snapshot"
                ) from e
            handle_client_http_error(e)

    async def wait_for_snapshot(
        self,
        snapshot_id: str,
        *,
        timeout: int = 300,
        poll_interval: float = 2.0,
        headers: RequestHeaders = None,
    ) -> Snapshot:
        """Poll until a snapshot reaches "ready" or "failed" status.

        Args:
            snapshot_id: Snapshot UUID.
            timeout: Maximum time to wait in seconds.
            poll_interval: Time between status checks in seconds.

        Returns:
            Snapshot in "ready" status.

        Raises:
            ResourceCreationError: If snapshot status becomes "failed".
            ResourceTimeoutError: If timeout expires.
            ResourceNotFoundError: If snapshot not found.
            SandboxClientError: For other errors.
        """
        import time

        deadline = time.monotonic() + timeout
        while True:
            snapshot = await self.get_snapshot(snapshot_id, headers=headers)
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
            await asyncio.sleep(min(poll_interval, remaining))
