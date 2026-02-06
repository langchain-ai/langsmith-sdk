"""Main SandboxClient class for interacting with the sandbox server API."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from langsmith import utils as ls_utils
from langsmith.sandbox._exceptions import (
    ResourceInUseError,
    ResourceNameConflictError,
    ResourceNotFoundError,
    SandboxAPIError,
    SandboxConnectionError,
    ValidationError,
)
from langsmith.sandbox._helpers import (
    handle_client_http_error,
    handle_pool_error,
    handle_sandbox_creation_error,
    handle_volume_creation_error,
    parse_error_response,
)
from langsmith.sandbox._models import Pool, SandboxTemplate, Volume, VolumeMountSpec
from langsmith.sandbox._sandbox import Sandbox


def _get_default_api_endpoint() -> str:
    """Get the default sandbox API endpoint from environment.

    Derives the endpoint from LANGSMITH_ENDPOINT (or LANGCHAIN_ENDPOINT).
    """
    base = ls_utils.get_env_var("ENDPOINT", default="https://api.smith.langchain.com")
    return f"{base.rstrip('/')}/v2/sandboxes"


def _get_default_api_key() -> Optional[str]:
    """Get the default API key from environment."""
    return ls_utils.get_env_var("API_KEY")


class SandboxClient:
    """Client for interacting with the Sandbox Server API.

    This client provides a simple interface for managing sandboxes and templates.

    Example:
        # Uses LANGSMITH_ENDPOINT and LANGSMITH_API_KEY from environment
        client = SandboxClient()

        # Or with explicit configuration
        client = SandboxClient(
            api_endpoint="https://api.smith.langchain.com/v2/sandboxes",
            api_key="your-api-key",
        )

        # Create a sandbox and run commands
        with client.sandbox(template_name="python-sandbox") as sandbox:
            result = sandbox.run("python --version")
            print(result.stdout)
    """

    def __init__(
        self,
        *,
        api_endpoint: Optional[str] = None,
        timeout: float = 10.0,
        api_key: Optional[str] = None,
    ):
        """Initialize the SandboxClient.

        Args:
            api_endpoint: Full URL of the sandbox API endpoint. If not provided,
                          derived from LANGSMITH_ENDPOINT environment variable.
            timeout: Default HTTP timeout in seconds.
            api_key: API key for authentication. If not provided, uses
                     LANGSMITH_API_KEY environment variable.
        """
        self._base_url = (api_endpoint or _get_default_api_endpoint()).rstrip("/")
        resolved_api_key = api_key or _get_default_api_key()
        headers: dict[str, str] = {}
        if resolved_api_key:
            headers["X-Api-Key"] = resolved_api_key
        self._http = httpx.Client(timeout=timeout, headers=headers)

    def close(self) -> None:
        """Close the HTTP client."""
        self._http.close()

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

    # ========================================================================
    # Volume Operations
    # ========================================================================

    def create_volume(
        self,
        name: str,
        size: str,
        *,
        timeout: int = 60,
    ) -> Volume:
        """Create a new persistent volume.

        Creates a persistent storage volume that can be referenced in templates.

        Args:
            name: Volume name.
            size: Storage size (e.g., "1Gi", "10Gi").
            timeout: Timeout in seconds when waiting for ready (min: 5, max: 300).

        Returns:
            Created Volume.

        Raises:
            VolumeProvisioningError: If volume provisioning fails.
            ResourceTimeoutError: If volume doesn't become ready within timeout.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/volumes"

        payload = {
            "name": name,
            "size": size,
            "wait_for_ready": True,
            "timeout": timeout,
        }

        try:
            # Use longer timeout for volume creation (includes wait_for_ready)
            response = self._http.post(url, json=payload, timeout=timeout + 30)
            response.raise_for_status()
            return Volume.from_dict(response.json())
        except httpx.ConnectError as e:
            raise SandboxConnectionError(f"Failed to connect to server: {e}") from e
        except httpx.HTTPStatusError as e:
            handle_volume_creation_error(e)
            raise  # pragma: no cover

    def get_volume(self, name: str) -> Volume:
        """Get a volume by name.

        Args:
            name: Volume name.

        Returns:
            Volume.

        Raises:
            ResourceNotFoundError: If volume not found.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/volumes/{name}"

        try:
            response = self._http.get(url)
            response.raise_for_status()
            return Volume.from_dict(response.json())
        except httpx.ConnectError as e:
            raise SandboxConnectionError(f"Failed to connect to server: {e}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Volume '{name}' not found", resource_type="volume"
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

    def list_volumes(self) -> list[Volume]:
        """List all volumes.

        Returns:
            List of Volumes.
        """
        url = f"{self._base_url}/volumes"

        try:
            response = self._http.get(url)
            response.raise_for_status()
            data = response.json()
            return [Volume.from_dict(v) for v in data.get("volumes", [])]
        except httpx.ConnectError as e:
            raise SandboxConnectionError(f"Failed to connect to server: {e}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise SandboxAPIError(
                    f"API endpoint not found: {url}. "
                    f"Check that api_endpoint is correct."
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

    def delete_volume(self, name: str) -> None:
        """Delete a volume.

        Args:
            name: Volume name.

        Raises:
            ResourceNotFoundError: If volume not found.
            ResourceInUseError: If volume is referenced by templates.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/volumes/{name}"

        try:
            response = self._http.delete(url)
            response.raise_for_status()
        except httpx.ConnectError as e:
            raise SandboxConnectionError(f"Failed to connect to server: {e}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Volume '{name}' not found", resource_type="volume"
                ) from e
            if e.response.status_code == 409:
                data = parse_error_response(e)
                raise ResourceInUseError(data["message"], resource_type="volume") from e
            handle_client_http_error(e)

    def update_volume(
        self,
        name: str,
        *,
        new_name: Optional[str] = None,
        size: Optional[str] = None,
    ) -> Volume:
        """Update a volume's name and/or size.

        You can update the display name, size, or both in a single request.
        Only storage size increases are allowed (storage backend limitation).

        Args:
            name: Current volume name.
            new_name: New display name (optional).
            size: New storage size (must be >= current size). Optional.

        Returns:
            Updated Volume.

        Raises:
            ResourceNotFoundError: If volume not found.
            VolumeResizeError: If storage decrease attempted.
            ResourceNameConflictError: If new_name is already in use.
            SandboxQuotaExceededError: If storage quota would be exceeded.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/volumes/{name}"
        payload: dict[str, Any] = {}
        if new_name is not None:
            payload["name"] = new_name
        if size is not None:
            payload["size"] = size

        if not payload:
            # Nothing to update, just return the current volume
            return self.get_volume(name)

        try:
            response = self._http.patch(url, json=payload)
            response.raise_for_status()
            return Volume.from_dict(response.json())
        except httpx.ConnectError as e:
            raise SandboxConnectionError(f"Failed to connect to server: {e}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Volume '{name}' not found", resource_type="volume"
                ) from e
            if e.response.status_code == 400:
                data = parse_error_response(e)
                raise ValidationError(data["message"], error_type="VolumeResize") from e
            if e.response.status_code == 409:
                data = parse_error_response(e)
                raise ResourceNameConflictError(
                    data["message"], resource_type="volume"
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

    # ========================================================================
    # Template Operations
    # ========================================================================

    def create_template(
        self,
        name: str,
        image: str,
        *,
        cpu: str = "500m",
        memory: str = "512Mi",
        storage: Optional[str] = None,
        volume_mounts: Optional[list[VolumeMountSpec]] = None,
    ) -> SandboxTemplate:
        """Create a new SandboxTemplate.

        Only the container image, resource limits, and volume mounts can be
        configured. All other container details are handled by the server.

        Args:
            name: Template name.
            image: Container image (e.g., "python:3.12-slim").
            cpu: CPU limit (e.g., "500m", "1", "2"). Default: "500m".
            memory: Memory limit (e.g., "256Mi", "1Gi"). Default: "512Mi".
            storage: Ephemeral storage limit (e.g., "1Gi"). Optional.
            volume_mounts: List of volumes to mount in the sandbox. Optional.

        Returns:
            Created SandboxTemplate.

        Raises:
            SandboxClientError: If creation fails.
        """
        url = f"{self._base_url}/templates"

        payload: dict[str, Any] = {
            "name": name,
            "image": image,
            "resources": {
                "cpu": cpu,
                "memory": memory,
            },
        }
        if storage:
            payload["resources"]["storage"] = storage
        if volume_mounts:
            payload["volume_mounts"] = [
                {"volume_name": vm.volume_name, "mount_path": vm.mount_path}
                for vm in volume_mounts
            ]

        try:
            response = self._http.post(url, json=payload)
            response.raise_for_status()
            return SandboxTemplate.from_dict(response.json())
        except httpx.ConnectError as e:
            raise SandboxConnectionError(f"Failed to connect to server: {e}") from e
        except httpx.HTTPStatusError as e:
            handle_client_http_error(e)
            raise  # pragma: no cover

    def get_template(self, name: str) -> SandboxTemplate:
        """Get a SandboxTemplate by name.

        Args:
            name: Template name.

        Returns:
            SandboxTemplate.

        Raises:
            ResourceNotFoundError: If template not found.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/templates/{name}"

        try:
            response = self._http.get(url)
            response.raise_for_status()
            return SandboxTemplate.from_dict(response.json())
        except httpx.ConnectError as e:
            raise SandboxConnectionError(f"Failed to connect to server: {e}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Template '{name}' not found", resource_type="template"
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

    def list_templates(self) -> list[SandboxTemplate]:
        """List all SandboxTemplates.

        Returns:
            List of SandboxTemplates.
        """
        url = f"{self._base_url}/templates"

        try:
            response = self._http.get(url)
            response.raise_for_status()
            data = response.json()
            return [SandboxTemplate.from_dict(t) for t in data.get("templates", [])]
        except httpx.ConnectError as e:
            raise SandboxConnectionError(f"Failed to connect to server: {e}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise SandboxAPIError(
                    f"API endpoint not found: {url}. "
                    f"Check that api_endpoint is correct."
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

    def update_template(self, name: str, *, new_name: str) -> SandboxTemplate:
        """Update a template's display name.

        Args:
            name: Current template name.
            new_name: New display name.

        Returns:
            Updated SandboxTemplate.

        Raises:
            ResourceNotFoundError: If template not found.
            ResourceNameConflictError: If new_name is already in use.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/templates/{name}"
        payload = {"name": new_name}

        try:
            response = self._http.patch(url, json=payload)
            response.raise_for_status()
            return SandboxTemplate.from_dict(response.json())
        except httpx.ConnectError as e:
            raise SandboxConnectionError(f"Failed to connect to server: {e}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Template '{name}' not found", resource_type="template"
                ) from e
            if e.response.status_code == 409:
                data = parse_error_response(e)
                raise ResourceNameConflictError(
                    data["message"], resource_type="template"
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

    def delete_template(self, name: str) -> None:
        """Delete a SandboxTemplate.

        Args:
            name: Template name.

        Raises:
            ResourceNotFoundError: If template not found.
            ResourceInUseError: If template is referenced by sandboxes or pools.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/templates/{name}"

        try:
            response = self._http.delete(url)
            response.raise_for_status()
        except httpx.ConnectError as e:
            raise SandboxConnectionError(f"Failed to connect to server: {e}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Template '{name}' not found", resource_type="template"
                ) from e
            if e.response.status_code == 409:
                data = parse_error_response(e)
                raise ResourceInUseError(
                    data["message"], resource_type="template"
                ) from e
            handle_client_http_error(e)

    # ========================================================================
    # Pool Operations
    # ========================================================================

    def create_pool(
        self,
        name: str,
        template_name: str,
        replicas: int,
        *,
        timeout: int = 30,
    ) -> Pool:
        """Create a new Sandbox Pool.

        Pools pre-provision sandboxes from a template for faster startup.

        Args:
            name: Pool name (lowercase letters, numbers, hyphens; max 63 chars).
            template_name: Name of the SandboxTemplate to use (no volume mounts).
            replicas: Number of sandboxes to pre-provision (1-100).
            timeout: Timeout in seconds when waiting for ready (10-600).

        Returns:
            Created Pool.

        Raises:
            ResourceNotFoundError: If template not found.
            ValidationError: If template has volumes attached.
            ResourceAlreadyExistsError: If pool with this name already exists.
            ResourceTimeoutError: If pool doesn't reach ready state within timeout.
            SandboxQuotaExceededError: If organization quota is exceeded.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/pools"

        payload: dict[str, Any] = {
            "name": name,
            "template_name": template_name,
            "replicas": replicas,
            "wait_for_ready": True,
            "timeout": timeout,
        }

        try:
            # Use longer HTTP timeout when waiting for ready
            http_timeout = timeout + 30
            response = self._http.post(url, json=payload, timeout=http_timeout)
            response.raise_for_status()
            return Pool.from_dict(response.json())
        except httpx.ConnectError as e:
            raise SandboxConnectionError(f"Failed to connect to server: {e}") from e
        except httpx.HTTPStatusError as e:
            handle_pool_error(e)
            raise  # pragma: no cover

    def get_pool(self, name: str) -> Pool:
        """Get a Pool by name.

        Args:
            name: Pool name.

        Returns:
            Pool.

        Raises:
            ResourceNotFoundError: If pool not found.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/pools/{name}"

        try:
            response = self._http.get(url)
            response.raise_for_status()
            return Pool.from_dict(response.json())
        except httpx.ConnectError as e:
            raise SandboxConnectionError(f"Failed to connect to server: {e}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Pool '{name}' not found", resource_type="pool"
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

    def list_pools(self) -> list[Pool]:
        """List all Pools.

        Returns:
            List of Pools.
        """
        url = f"{self._base_url}/pools"

        try:
            response = self._http.get(url)
            response.raise_for_status()
            data = response.json()
            return [Pool.from_dict(p) for p in data.get("pools", [])]
        except httpx.ConnectError as e:
            raise SandboxConnectionError(f"Failed to connect to server: {e}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise SandboxAPIError(
                    f"API endpoint not found: {url}. "
                    f"Check that api_endpoint is correct."
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

    def update_pool(
        self,
        name: str,
        *,
        new_name: Optional[str] = None,
        replicas: Optional[int] = None,
    ) -> Pool:
        """Update a Pool's name and/or replica count.

        You can update the display name, replica count, or both.
        The template reference cannot be changed after creation.

        Args:
            name: Current pool name.
            new_name: New display name (optional).
            replicas: New number of replicas (0-100). Set to 0 to pause.

        Returns:
            Updated Pool.

        Raises:
            ResourceNotFoundError: If pool not found.
            ValidationError: If template was deleted.
            ResourceNameConflictError: If new_name is already in use.
            SandboxQuotaExceededError: If quota exceeded when scaling up.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/pools/{name}"

        payload: dict[str, Any] = {}
        if new_name is not None:
            payload["name"] = new_name
        if replicas is not None:
            payload["replicas"] = replicas

        if not payload:
            # Nothing to update, just return the current pool
            return self.get_pool(name)

        try:
            response = self._http.patch(url, json=payload)
            response.raise_for_status()
            return Pool.from_dict(response.json())
        except httpx.ConnectError as e:
            raise SandboxConnectionError(f"Failed to connect to server: {e}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Pool '{name}' not found", resource_type="pool"
                ) from e
            if e.response.status_code == 409:
                data = parse_error_response(e)
                raise ResourceNameConflictError(
                    data["message"], resource_type="pool"
                ) from e
            handle_pool_error(e)
            raise  # pragma: no cover

    def delete_pool(self, name: str) -> None:
        """Delete a Pool.

        This will terminate all sandboxes in the pool.

        Args:
            name: Pool name.

        Raises:
            ResourceNotFoundError: If pool not found.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/pools/{name}"

        try:
            response = self._http.delete(url)
            response.raise_for_status()
        except httpx.ConnectError as e:
            raise SandboxConnectionError(f"Failed to connect to server: {e}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Pool '{name}' not found", resource_type="pool"
                ) from e
            handle_client_http_error(e)

    # ========================================================================
    # Sandbox Operations
    # ========================================================================

    def sandbox(
        self,
        template_name: str,
        *,
        name: Optional[str] = None,
        timeout: int = 30,
    ) -> Sandbox:
        """Create a sandbox and return a Sandbox instance.

        This is the primary method for creating sandboxes. Use it as a
        context manager for automatic cleanup:

            with client.sandbox(template_name="my-template") as sandbox:
                result = sandbox.run("echo hello")

        The sandbox is automatically deleted when exiting the context manager.
        For sandboxes with manual lifecycle management, use create_sandbox().

        Args:
            template_name: Name of the SandboxTemplate to use.
            name: Optional sandbox name (auto-generated if not provided).
            timeout: Timeout in seconds when waiting for ready.

        Returns:
            Sandbox instance.

        Raises:
            ResourceTimeoutError: If timeout waiting for sandbox to be ready.
            SandboxCreationError: If sandbox creation fails.
            SandboxClientError: For other errors.
        """
        sb = self.create_sandbox(
            template_name=template_name,
            name=name,
            timeout=timeout,
        )
        sb._auto_delete = True
        return sb

    def create_sandbox(
        self,
        template_name: str,
        *,
        name: Optional[str] = None,
        timeout: int = 30,
    ) -> Sandbox:
        """Create a new Sandbox.

        The sandbox is NOT automatically deleted. Use delete_sandbox() for cleanup,
        or use sandbox() for automatic cleanup with a context manager.

        Args:
            template_name: Name of the SandboxTemplate to use.
            name: Optional sandbox name (auto-generated if not provided).
            timeout: Timeout in seconds when waiting for ready.

        Returns:
            Created Sandbox.

        Raises:
            ResourceTimeoutError: If timeout waiting for sandbox to be ready.
            SandboxCreationError: If sandbox creation fails.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/boxes"

        payload: dict[str, Any] = {
            "template_name": template_name,
            "wait_for_ready": True,
            "timeout": timeout,
        }
        if name:
            payload["name"] = name

        try:
            # Use longer timeout for sandbox creation (includes wait_for_ready)
            response = self._http.post(url, json=payload, timeout=timeout + 30)
            response.raise_for_status()
            return Sandbox.from_dict(response.json(), client=self, auto_delete=False)
        except httpx.ConnectError as e:
            raise SandboxConnectionError(f"Failed to connect to server: {e}") from e
        except httpx.HTTPStatusError as e:
            handle_sandbox_creation_error(e)
            raise  # pragma: no cover

    def get_sandbox(self, name: str) -> Sandbox:
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
            response = self._http.get(url)
            response.raise_for_status()
            return Sandbox.from_dict(response.json(), client=self, auto_delete=False)
        except httpx.ConnectError as e:
            raise SandboxConnectionError(f"Failed to connect to server: {e}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Sandbox '{name}' not found", resource_type="sandbox"
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

    def list_sandboxes(self) -> list[Sandbox]:
        """List all Sandboxes.

        Returns:
            List of Sandboxes.
        """
        url = f"{self._base_url}/boxes"

        try:
            response = self._http.get(url)
            response.raise_for_status()
            data = response.json()
            return [
                Sandbox.from_dict(c, client=self, auto_delete=False)
                for c in data.get("sandboxes", [])
            ]
        except httpx.ConnectError as e:
            raise SandboxConnectionError(f"Failed to connect to server: {e}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise SandboxAPIError(
                    f"API endpoint not found: {url}. "
                    f"Check that api_endpoint is correct."
                ) from e
            handle_client_http_error(e)
            raise  # pragma: no cover

    def update_sandbox(self, name: str, *, new_name: str) -> Sandbox:
        """Update a sandbox's display name.

        Args:
            name: Current sandbox name.
            new_name: New display name.

        Returns:
            Updated Sandbox.

        Raises:
            ResourceNotFoundError: If sandbox not found.
            ResourceNameConflictError: If new_name is already in use.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/boxes/{name}"
        payload = {"name": new_name}

        try:
            response = self._http.patch(url, json=payload)
            response.raise_for_status()
            return Sandbox.from_dict(response.json(), client=self, auto_delete=False)
        except httpx.ConnectError as e:
            raise SandboxConnectionError(f"Failed to connect to server: {e}") from e
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

    def delete_sandbox(self, name: str) -> None:
        """Delete a Sandbox.

        Args:
            name: Sandbox name.

        Raises:
            ResourceNotFoundError: If sandbox not found.
            SandboxClientError: For other errors.
        """
        url = f"{self._base_url}/boxes/{name}"

        try:
            response = self._http.delete(url)
            response.raise_for_status()
        except httpx.ConnectError as e:
            raise SandboxConnectionError(f"Failed to connect to server: {e}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Sandbox '{name}' not found", resource_type="sandbox"
                ) from e
            handle_client_http_error(e)
