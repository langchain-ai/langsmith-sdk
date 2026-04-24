"""Main SandboxClient class for interacting with the sandbox server API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

import httpx

from langsmith import utils as ls_utils
from langsmith.sandbox._exceptions import (
    ResourceCreationError,
    ResourceNameConflictError,
    ResourceNotFoundError,
    ResourceTimeoutError,
    SandboxAPIError,
)
from langsmith.sandbox._helpers import (
    handle_client_http_error,
    handle_sandbox_creation_error,
    merge_headers,
    validate_service_params,
    validate_ttl,
)
from langsmith.sandbox._models import (
    ResourceStatus,
    ServiceURL,
    Snapshot,
)
from langsmith.sandbox._sandbox import Sandbox
from langsmith.sandbox._transport import RetryTransport


def _get_default_api_endpoint() -> str:
    """Get the default sandbox API endpoint from environment.

    Derives the endpoint from LANGSMITH_ENDPOINT (or LANGCHAIN_ENDPOINT).
    """
    base = ls_utils.get_env_var("ENDPOINT", default="https://api.smith.langchain.com")
    return f"{base.rstrip('/')}/v2/sandboxes"


def _get_default_api_key() -> Optional[str]:
    """Get the default API key from environment."""
    return ls_utils.get_env_var("API_KEY")


RequestHeaders = Optional[Mapping[str, str]]


class SandboxClient:
    """Client for interacting with the Sandbox Server API.

    This client provides a simple interface for managing sandboxes and snapshots.

    Example:
        # Uses LANGSMITH_ENDPOINT and LANGSMITH_API_KEY from environment
        client = SandboxClient()

        # Or with explicit configuration
        client = SandboxClient(
            api_endpoint="https://api.smith.langchain.com/v2/sandboxes",
            api_key="your-api-key",
        )

        # Create a sandbox from a snapshot and run commands
        with client.sandbox(snapshot_id="<snapshot-uuid>") as sandbox:
            result = sandbox.run("python --version")
            print(result.stdout)
    """

    def __init__(
        self,
        *,
        api_endpoint: Optional[str] = None,
        timeout: float = 10.0,
        api_key: Optional[str] = None,
        max_retries: int = 3,
        headers: Optional[RequestHeaders] = None,
    ):
        """Initialize the SandboxClient.

        Args:
            api_endpoint: Full URL of the sandbox API endpoint. If not provided,
                          derived from LANGSMITH_ENDPOINT environment variable.
            timeout: Default HTTP timeout in seconds.
            api_key: API key for authentication. If not provided, uses
                     LANGSMITH_API_KEY environment variable.
            max_retries: Maximum number of retries for transient errors (502, 503,
                         504), rate limits (429), and connection failures. Set to 0
                         to disable retries. Default: 3.
        """
        self._base_url = (api_endpoint or _get_default_api_endpoint()).rstrip("/")
        resolved_api_key = api_key or _get_default_api_key()
        self._api_key = resolved_api_key
        client_headers: dict[str, str] = {}
        if resolved_api_key:
            client_headers["X-Api-Key"] = resolved_api_key
        if headers:
            client_headers = merge_headers(client_headers, headers)
        transport = RetryTransport(max_retries=max_retries)
        self._http = httpx.Client(
            transport=transport, timeout=timeout, headers=client_headers
        )

    def _request_headers(self, headers: RequestHeaders) -> Optional[dict[str, str]]:
        """Merge default client headers with per-request overrides."""
        if headers is None:
            return None
        return merge_headers(self._http.headers, headers)

    def close(self) -> None:
        """Close the HTTP client."""
        self._http.close()

    def __del__(self) -> None:
        """Close the HTTP client on garbage collection."""
        try:
            if not self._http.is_closed:
                self._http.close()
        except Exception:
            pass

    def __enter__(self) -> SandboxClient:
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Exit context manager."""
        self.close()

    def __repr__(self) -> str:
        """Return a string representation of the instance.

        Returns:
            The string representation of the instance.
        """
        return f"SandboxClient (API URL: {self._base_url})"

    # ========================================================================
    # Sandbox Operations
    # ========================================================================

    def sandbox(
        self,
        snapshot_id: Optional[str] = None,
        *,
        snapshot_name: Optional[str] = None,
        name: Optional[str] = None,
        timeout: int = 30,
        ttl_seconds: Optional[int] = None,
        idle_ttl_seconds: Optional[int] = None,
        vcpus: Optional[int] = None,
        mem_bytes: Optional[int] = None,
        fs_capacity_bytes: Optional[int] = None,
        proxy_config: Optional[dict[str, Any]] = None,
        headers: RequestHeaders = None,
    ) -> Sandbox:
        """Create a sandbox and return a Sandbox instance.

        This is the primary method for creating sandboxes. Use it as a
        context manager for automatic cleanup:

            with client.sandbox(snapshot_id="<uuid>") as sandbox:
                result = sandbox.run("echo hello")

            # Resolve by snapshot name instead of ID:
            with client.sandbox(snapshot_name="my-snap") as sandbox:
                result = sandbox.run("echo hello")

        The sandbox is automatically deleted when exiting the context manager.
        For sandboxes with manual lifecycle management, use create_sandbox().

        Args:
            snapshot_id: Snapshot ID to boot from. Mutually exclusive with
                ``snapshot_name``; exactly one must be provided.
            snapshot_name: Snapshot name to boot from. Resolved server-side to a
                snapshot owned by the caller's tenant. Mutually exclusive with
                ``snapshot_id``; exactly one must be provided.
            name: Optional sandbox name (auto-generated if not provided).
            timeout: Timeout in seconds when waiting for ready.
            ttl_seconds: Maximum lifetime in seconds from creation. The sandbox
                will be automatically deleted after this duration. Must be a
                multiple of 60. 0 or None disables this TTL.
            idle_ttl_seconds: Idle timeout in seconds. The sandbox will be
                automatically deleted after this duration of inactivity. Must
                be a multiple of 60. ``0`` explicitly disables the idle
                timeout. When omitted (``None``), the server applies a default
                of ``600`` seconds (10 minutes).
            vcpus: Number of vCPUs.
            mem_bytes: Memory in bytes.
            fs_capacity_bytes: Root filesystem capacity in bytes.
            proxy_config: Per-sandbox proxy configuration forwarded to the
                server as-is. Shape matches the backend `proxy_config` field:
                ``{"rules": [...], "no_proxy": [...], "access_control":
                {"allow_list": [...]}}`` or ``{"access_control":
                {"deny_list": [...]}}``. Use ``access_control.allow_list`` to
                restrict outbound HTTPS to a set of host patterns (exact
                domains, globs like ``*.example.com``, IPs, CIDRs, or
                ``~regex``).

        Returns:
            Sandbox instance.

        Raises:
            ResourceTimeoutError: If timeout waiting for sandbox to be ready.
            ResourceCreationError: If sandbox creation fails.
            SandboxClientError: For other errors.
            ValueError: If TTL values are invalid, or if neither/both of
                ``snapshot_id`` and ``snapshot_name`` are provided.
        """
        sb = self.create_sandbox(
            snapshot_id,
            snapshot_name=snapshot_name,
            name=name,
            timeout=timeout,
            ttl_seconds=ttl_seconds,
            idle_ttl_seconds=idle_ttl_seconds,
            vcpus=vcpus,
            mem_bytes=mem_bytes,
            fs_capacity_bytes=fs_capacity_bytes,
            proxy_config=proxy_config,
            headers=headers,
        )
        sb._auto_delete = True
        return sb

    def create_sandbox(
        self,
        snapshot_id: Optional[str] = None,
        *,
        snapshot_name: Optional[str] = None,
        name: Optional[str] = None,
        timeout: int = 30,
        wait_for_ready: bool = True,
        ttl_seconds: Optional[int] = None,
        idle_ttl_seconds: Optional[int] = None,
        vcpus: Optional[int] = None,
        mem_bytes: Optional[int] = None,
        fs_capacity_bytes: Optional[int] = None,
        proxy_config: Optional[dict[str, Any]] = None,
        headers: RequestHeaders = None,
    ) -> Sandbox:
        """Create a new Sandbox.

        The sandbox is NOT automatically deleted. Use delete_sandbox() for cleanup,
        or use sandbox() for automatic cleanup with a context manager.

        Args:
            snapshot_id: Snapshot ID to boot from. Mutually exclusive with
                ``snapshot_name``; exactly one must be provided.
            snapshot_name: Snapshot name to boot from. Resolved server-side to a
                snapshot owned by the caller's tenant. Mutually exclusive with
                ``snapshot_id``; exactly one must be provided.
            name: Optional sandbox name (auto-generated if not provided).
            timeout: Timeout in seconds when waiting for ready (only used when
                wait_for_ready=True).
            wait_for_ready: If True (default), block until sandbox is ready.
                If False, return immediately with status "provisioning". Use
                get_sandbox_status() or wait_for_sandbox() to poll for readiness.
            ttl_seconds: Maximum lifetime in seconds from creation. The sandbox
                will be automatically deleted after this duration. Must be a
                multiple of 60. 0 or None disables this TTL.
            idle_ttl_seconds: Idle timeout in seconds. The sandbox will be
                automatically deleted after this duration of inactivity. Must
                be a multiple of 60. ``0`` explicitly disables the idle
                timeout. When omitted (``None``), the server applies a default
                of ``600`` seconds (10 minutes).
            vcpus: Number of vCPUs.
            mem_bytes: Memory in bytes.
            fs_capacity_bytes: Root filesystem capacity in bytes.
            proxy_config: Per-sandbox proxy configuration forwarded to the
                server as-is. Shape matches the backend `proxy_config` field:
                ``{"rules": [...], "no_proxy": [...], "access_control":
                {"allow_list": [...]}}`` or ``{"access_control":
                {"deny_list": [...]}}``. Use ``access_control.allow_list`` to
                restrict outbound HTTPS to a set of host patterns (exact
                domains, globs like ``*.example.com``, IPs, CIDRs, or
                ``~regex``).

        Returns:
            Created Sandbox. When wait_for_ready=False, the sandbox will have
            status="provisioning" and cannot be used for operations until ready.

        Raises:
            ResourceTimeoutError: If timeout waiting for sandbox to be ready.
            ResourceCreationError: If sandbox creation fails.
            SandboxClientError: For other errors.
            ValueError: If TTL values are invalid, or if neither/both of
                ``snapshot_id`` and ``snapshot_name`` are provided.
        """
        if bool(snapshot_id) == bool(snapshot_name):
            raise ValueError("Exactly one of snapshot_id or snapshot_name must be set")

        validate_ttl(ttl_seconds, "ttl_seconds")
        validate_ttl(idle_ttl_seconds, "idle_ttl_seconds")

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
        if ttl_seconds is not None:
            payload["ttl_seconds"] = ttl_seconds
        if idle_ttl_seconds is not None:
            payload["idle_ttl_seconds"] = idle_ttl_seconds
        if vcpus is not None:
            payload["vcpus"] = vcpus
        if mem_bytes is not None:
            payload["mem_bytes"] = mem_bytes
        if fs_capacity_bytes is not None:
            payload["fs_capacity_bytes"] = fs_capacity_bytes
        if proxy_config is not None:
            payload["proxy_config"] = proxy_config

        http_timeout = (timeout + 30) if wait_for_ready else 30

        try:
            response = self._http.post(
                url,
                json=payload,
                timeout=http_timeout,
                headers=self._request_headers(headers),
            )
            response.raise_for_status()
            return Sandbox.from_dict(response.json(), client=self, auto_delete=False)
        except httpx.HTTPStatusError as e:
            handle_sandbox_creation_error(e)
            raise  # pragma: no cover

    def get_sandbox(self, name: str, *, headers: RequestHeaders = None) -> Sandbox:
        """Get a Sandbox by name.

        The sandbox is NOT automatically deleted. Use delete_sandbox() for cleanup.

        Args:
            name: Sandbox name.

        Returns:
            Sandbox.

        Raises:
            ResourceNotFoundError: If sandbox not found.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/boxes/{name}"

        try:
            response = self._http.get(url, headers=self._request_headers(headers))
            response.raise_for_status()
            return Sandbox.from_dict(response.json(), client=self, auto_delete=False)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Sandbox '{name}' not found", resource_type="sandbox"
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

    def list_sandboxes(self, *, headers: RequestHeaders = None) -> list[Sandbox]:
        """List all Sandboxes.

        Returns:
            List of Sandboxes.
        """
        url = f"{self._base_url}/boxes"

        try:
            response = self._http.get(url, headers=self._request_headers(headers))
            response.raise_for_status()
            data = response.json()
            return [
                Sandbox.from_dict(c, client=self, auto_delete=False)
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

    def update_sandbox(
        self,
        name: str,
        *,
        new_name: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
        idle_ttl_seconds: Optional[int] = None,
        headers: RequestHeaders = None,
    ) -> Sandbox:
        """Update a sandbox's properties.

        Args:
            name: Current sandbox name.
            new_name: New display name.
            ttl_seconds: Maximum lifetime in seconds from creation. Must be a
                multiple of 60. 0 disables this TTL.
            idle_ttl_seconds: Idle timeout in seconds. Must be a multiple of
                60. ``0`` disables this TTL. ``None`` leaves the existing
                value unchanged.

        Returns:
            Updated Sandbox.

        Raises:
            ResourceNotFoundError: If sandbox not found.
            ResourceNameConflictError: If new_name is already in use.
            SandboxClientError: For other errors.
            ValueError: If TTL values are invalid.
        """
        validate_ttl(ttl_seconds, "ttl_seconds")
        validate_ttl(idle_ttl_seconds, "idle_ttl_seconds")

        url = f"{self._base_url}/boxes/{name}"
        payload: dict[str, Any] = {}
        if new_name is not None:
            payload["name"] = new_name
        if ttl_seconds is not None:
            payload["ttl_seconds"] = ttl_seconds
        if idle_ttl_seconds is not None:
            payload["idle_ttl_seconds"] = idle_ttl_seconds

        try:
            response = self._http.patch(
                url, json=payload, headers=self._request_headers(headers)
            )
            response.raise_for_status()
            return Sandbox.from_dict(response.json(), client=self, auto_delete=False)
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

    def delete_sandbox(self, name: str, *, headers: RequestHeaders = None) -> None:
        """Delete a Sandbox.

        Args:
            name: Sandbox name.

        Raises:
            ResourceNotFoundError: If sandbox not found.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/boxes/{name}"

        try:
            response = self._http.delete(url, headers=self._request_headers(headers))
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Sandbox '{name}' not found", resource_type="sandbox"
                ) from e
            handle_client_http_error(e)

    def get_sandbox_status(
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
        url = f"{self._base_url}/boxes/{name}/status"

        try:
            response = self._http.get(url, headers=self._request_headers(headers))
            response.raise_for_status()
            return ResourceStatus.from_dict(response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Sandbox '{name}' not found", resource_type="sandbox"
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

    def service(
        self,
        name: str,
        port: int,
        *,
        expires_in_seconds: int = 600,
        headers: RequestHeaders = None,
    ) -> ServiceURL:
        """Get an authenticated URL for a service running inside a sandbox.

        Returns a :class:`ServiceURL` whose properties auto-refresh the
        token transparently before it expires.  The object also provides
        HTTP helper methods (``.get``, ``.post``, etc.) that inject the
        authentication header automatically.

        Args:
            name: Sandbox name.
            port: Port the service is listening on inside the sandbox.
            expires_in_seconds: Token TTL in seconds (1--86400, default 600).
            headers: Optional per-request header overrides.

        Returns:
            ServiceURL with auto-refreshing token and HTTP helpers.

        Raises:
            ResourceNotFoundError: If sandbox not found.
            ValueError: If port or expires_in_seconds is out of range.
            SandboxClientError: For other errors.
        """
        validate_service_params(port, expires_in_seconds)
        url = f"{self._base_url}/boxes/{name}/service-url"
        payload = {"port": port, "expires_in_seconds": expires_in_seconds}

        def _refresher() -> ServiceURL:
            return self.service(
                name,
                port,
                expires_in_seconds=expires_in_seconds,
                headers=headers,
            )

        try:
            response = self._http.post(
                url, json=payload, headers=self._request_headers(headers)
            )
            response.raise_for_status()
            return ServiceURL.from_dict(response.json(), _refresher=_refresher)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Sandbox '{name}' not found", resource_type="sandbox"
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

    def wait_for_sandbox(
        self,
        name: str,
        *,
        timeout: int = 120,
        poll_interval: float = 1.0,
        headers: RequestHeaders = None,
    ) -> Sandbox:
        """Poll until a sandbox reaches "ready" or "failed" status.

        Uses the lightweight status endpoint for polling, then fetches the
        full sandbox data once ready.

        Args:
            name: Sandbox name.
            timeout: Maximum time to wait in seconds.
            poll_interval: Time between status checks in seconds.

        Returns:
            Sandbox in "ready" status.

        Raises:
            ResourceCreationError: If sandbox status becomes "failed".
            ResourceTimeoutError: If timeout expires while still "provisioning".
            ResourceNotFoundError: If sandbox not found.
            SandboxClientError: For other errors.
        """
        import time

        deadline = time.monotonic() + timeout
        while True:
            status = self.get_sandbox_status(name, headers=headers)
            if status.status == "ready":
                return self.get_sandbox(name, headers=headers)
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
            time.sleep(min(poll_interval, remaining))

    def start_sandbox(
        self,
        name: str,
        *,
        timeout: int = 120,
        headers: RequestHeaders = None,
    ) -> Sandbox:
        """Start a stopped sandbox and wait until ready.

        Args:
            name: Sandbox name.
            timeout: Timeout in seconds when waiting for ready.

        Returns:
            Sandbox in "ready" status.

        Raises:
            ResourceNotFoundError: If sandbox not found.
            ResourceCreationError: If sandbox fails during startup.
            ResourceTimeoutError: If sandbox doesn't become ready within timeout.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/boxes/{name}/start"

        try:
            response = self._http.post(
                url, json={}, headers=self._request_headers(headers)
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Sandbox '{name}' not found", resource_type="sandbox"
                ) from e
            handle_client_http_error(e)

        return self.wait_for_sandbox(name, timeout=timeout, headers=headers)

    def stop_sandbox(self, name: str, *, headers: RequestHeaders = None) -> None:
        """Stop a running sandbox (preserves sandbox files for later restart).

        Args:
            name: Sandbox name.

        Raises:
            ResourceNotFoundError: If sandbox not found.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/boxes/{name}/stop"

        try:
            response = self._http.post(
                url, json={}, headers=self._request_headers(headers)
            )
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

    def create_snapshot(
        self,
        name: str,
        docker_image: str,
        fs_capacity_bytes: int,
        *,
        registry_id: Optional[str] = None,
        registry_url: Optional[str] = None,
        registry_username: Optional[str] = None,
        registry_password: Optional[str] = None,
        timeout: int = 60,
        headers: RequestHeaders = None,
    ) -> Snapshot:
        """Build a snapshot from a Docker image.

        Blocks until the snapshot is ready (polls with 2s interval).

        Args:
            name: Snapshot name.
            docker_image: Docker image to build from (e.g., "python:3.12-slim").
            fs_capacity_bytes: Filesystem capacity in bytes.
            registry_id: Private registry ID (alternative to URL/credentials).
            registry_url: Registry URL for private images.
            registry_username: Registry username.
            registry_password: Registry password.
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
        if registry_url is not None:
            payload["registry_url"] = registry_url
        if registry_username is not None:
            payload["registry_username"] = registry_username
        if registry_password is not None:
            payload["registry_password"] = registry_password

        try:
            response = self._http.post(
                url, json=payload, headers=self._request_headers(headers)
            )
            response.raise_for_status()
            snapshot = Snapshot.from_dict(response.json())
        except httpx.HTTPStatusError as e:
            handle_client_http_error(e)
            raise  # pragma: no cover

        return self.wait_for_snapshot(snapshot.id, timeout=timeout, headers=headers)

    def capture_snapshot(
        self,
        sandbox_name: str,
        name: str,
        *,
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
        url = f"{self._base_url}/boxes/{sandbox_name}/snapshot"

        payload: dict[str, Any] = {"name": name}

        try:
            response = self._http.post(
                url, json=payload, headers=self._request_headers(headers)
            )
            response.raise_for_status()
            snapshot = Snapshot.from_dict(response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Sandbox '{sandbox_name}' not found", resource_type="sandbox"
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

        return self.wait_for_snapshot(snapshot.id, timeout=timeout, headers=headers)

    def get_snapshot(
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
        url = f"{self._base_url}/snapshots/{snapshot_id}"

        try:
            response = self._http.get(url, headers=self._request_headers(headers))
            response.raise_for_status()
            return Snapshot.from_dict(response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Snapshot '{snapshot_id}' not found", resource_type="snapshot"
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

    def list_snapshots(
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
            response = self._http.get(
                url,
                params=params or None,
                headers=self._request_headers(headers),
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

    def delete_snapshot(
        self, snapshot_id: str, *, headers: RequestHeaders = None
    ) -> None:
        """Delete a snapshot.

        Args:
            snapshot_id: Snapshot UUID.

        Raises:
            ResourceNotFoundError: If snapshot not found.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/snapshots/{snapshot_id}"

        try:
            response = self._http.delete(url, headers=self._request_headers(headers))
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Snapshot '{snapshot_id}' not found", resource_type="snapshot"
                ) from e
            handle_client_http_error(e)

    def wait_for_snapshot(
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
            snapshot = self.get_snapshot(snapshot_id, headers=headers)
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
            time.sleep(min(poll_interval, remaining))
