"""Custom exceptions for the sandbox client.

All sandbox exceptions extend LangSmithError for unified error handling.
The exceptions are organized by error type rather than resource type,
with a resource_type attribute for specific handling when needed.
"""

from __future__ import annotations

from typing import Optional

from langsmith.utils import LangSmithError


class SandboxClientError(LangSmithError):
    """Base exception for sandbox client errors."""

    pass


# =============================================================================
# Connection and Authentication Errors
# =============================================================================


class SandboxAPIError(SandboxClientError):
    """Raised when the API endpoint returns an unexpected error.

    For example, this is raised for wrong URL or path.
    """

    pass


class SandboxAuthenticationError(SandboxClientError):
    """Raised when authentication fails (invalid or missing API key)."""

    pass


class SandboxConnectionError(SandboxClientError):
    """Raised when connection to the sandbox server fails."""

    pass


# =============================================================================
# Resource Errors (type-based, with resource_type attribute)
# =============================================================================


class ResourceNotFoundError(SandboxClientError):
    """Raised when a resource is not found.

    Attributes:
        resource_type: Type of resource (sandbox, template, volume, pool, file).
    """

    def __init__(self, message: str, resource_type: Optional[str] = None):
        """Initialize the error."""
        super().__init__(message)
        self.resource_type = resource_type


class ResourceTimeoutError(SandboxClientError):
    """Raised when an operation times out.

    Attributes:
        resource_type: Type of resource (sandbox, volume, pool).
        last_status: The last known status before timeout (for sandboxes).
    """

    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        last_status: Optional[str] = None,
    ):
        """Initialize the error."""
        super().__init__(message)
        self.resource_type = resource_type
        self.last_status = last_status

    def __str__(self) -> str:
        """Return string representation."""
        base = super().__str__()
        if self.last_status:
            return f"{base} (last_status: {self.last_status})"
        return base


class ResourceInUseError(SandboxClientError):
    """Raised when deleting a resource that is still in use.

    Attributes:
        resource_type: Type of resource (template, volume).
    """

    def __init__(self, message: str, resource_type: Optional[str] = None):
        """Initialize the error."""
        super().__init__(message)
        self.resource_type = resource_type


class ResourceAlreadyExistsError(SandboxClientError):
    """Raised when creating a resource that already exists.

    Attributes:
        resource_type: Type of resource (e.g., pool).
    """

    def __init__(self, message: str, resource_type: Optional[str] = None):
        """Initialize the error."""
        super().__init__(message)
        self.resource_type = resource_type


class ResourceNameConflictError(SandboxClientError):
    """Raised when updating a resource name to one that already exists.

    Attributes:
        resource_type: Type of resource (volume, template, pool, sandbox).
    """

    def __init__(self, message: str, resource_type: Optional[str] = None):
        """Initialize the error."""
        super().__init__(message)
        self.resource_type = resource_type


# =============================================================================
# Validation and Quota Errors
# =============================================================================


class ValidationError(SandboxClientError):
    """Raised when request validation fails.

    This includes:
    - Resource values exceeding server-defined limits (CPU, memory, storage)
    - Invalid resource units
    - Invalid name formats
    - Pool validation failures (e.g., template has volumes)

    Attributes:
        field: The field that failed validation (e.g., "cpu", "memory").
        details: List of validation error details from the API.
        error_type: Machine-readable error type from the API.
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[list[dict]] = None,
        error_type: Optional[str] = None,
    ):
        """Initialize the error."""
        super().__init__(message)
        self.field = field
        self.details = details or []
        self.error_type = error_type


class QuotaExceededError(SandboxClientError):
    """Raised when organization quota limits are exceeded.

    Users should contact support@langchain.dev to increase quotas.

    Attributes:
        quota_type: Type of quota exceeded (e.g., "sandbox_count", "cpu").
    """

    def __init__(self, message: str, quota_type: Optional[str] = None):
        """Initialize the error."""
        super().__init__(message)
        self.quota_type = quota_type


# =============================================================================
# Sandbox Creation Errors
# =============================================================================


class SandboxCreationError(SandboxClientError):
    """Raised when sandbox creation fails.

    Attributes:
        error_type: Machine-readable error type (ImagePull, CrashLoop,
            SandboxConfig, Unschedulable).
    """

    def __init__(self, message: str, error_type: Optional[str] = None):
        """Initialize the error."""
        super().__init__(message)
        self.error_type = error_type

    def __str__(self) -> str:
        """Return string representation."""
        if self.error_type:
            return f"{super().__str__()} [{self.error_type}]"
        return super().__str__()


# =============================================================================
# Sandbox Operation Errors (runtime errors during sandbox interaction)
# =============================================================================


class DataplaneNotConfiguredError(SandboxClientError):
    """Raised when dataplane_url is not available for the sandbox.

    This occurs when the sandbox-router URL is not configured for the cluster.
    """

    pass


class SandboxNotReadyError(SandboxClientError):
    """Raised when attempting to interact with a sandbox that is not ready."""

    pass


class SandboxOperationError(SandboxClientError):
    """Raised when a sandbox operation fails (run, read, write).

    Attributes:
        operation: The operation that failed (command, read, write).
        error_type: Machine-readable error type from the API.
    """

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        error_type: Optional[str] = None,
    ):
        """Initialize the error."""
        super().__init__(message)
        self.operation = operation
        self.error_type = error_type

    def __str__(self) -> str:
        """Return string representation."""
        if self.error_type:
            return f"{super().__str__()} [{self.error_type}]"
        return super().__str__()
