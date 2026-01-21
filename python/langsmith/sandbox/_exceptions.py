"""Custom exceptions for the sandbox client.

All sandbox exceptions extend LangSmithError for unified error handling.
"""

from __future__ import annotations

from typing import Optional

from langsmith.utils import LangSmithError


class SandboxClientError(LangSmithError):
    """Base exception for sandbox client errors."""

    pass


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


class SandboxNotFoundError(SandboxClientError):
    """Raised when a sandbox (claim) or file is not found."""

    pass


class TemplateNotFoundError(SandboxClientError):
    """Raised when a sandbox template is not found."""

    pass


class VolumeNotFoundError(SandboxClientError):
    """Raised when a volume is not found."""

    pass


class VolumeProvisioningError(SandboxClientError):
    """Raised when volume provisioning fails (503 - invalid storage class, quota)."""

    pass


class VolumeTimeoutError(SandboxClientError):
    """Raised when volume doesn't become ready within timeout (504)."""

    pass


class VolumeInUseError(SandboxClientError):
    """Raised when deleting a volume referenced by templates (409)."""

    pass


class VolumeResizeError(SandboxClientError):
    """Raised when volume resize fails (400 - cannot decrease size)."""

    pass


class TemplateInUseError(SandboxClientError):
    """Raised when deleting a template referenced by sandboxes or pools (409)."""

    pass


class ResourceNameConflictError(SandboxClientError):
    """Raised when updating a resource name to one that already exists (409).

    This error occurs when attempting to rename a volume, template, or pool
    to a name that is already in use by another resource of the same type.

    Attributes:
        resource_type: Type of resource (e.g., "volume", "template", "pool").
    """

    def __init__(self, message: str, resource_type: Optional[str] = None):
        """Initialize the error."""
        super().__init__(message)
        self.resource_type = resource_type


class PoolNotFoundError(SandboxClientError):
    """Raised when a pool is not found."""

    pass


class PoolAlreadyExistsError(SandboxClientError):
    """Raised when creating a pool that already exists (409 Conflict)."""

    pass


class PoolValidationError(SandboxClientError):
    """Raised when pool validation fails.

    This includes:
    - Template has volume mounts (pools only support stateless templates)
    - Template was deleted after pool creation

    Attributes:
        error_type: Machine-readable error type from the API.
    """

    def __init__(self, message: str, error_type: Optional[str] = None):
        """Initialize the error."""
        super().__init__(message)
        self.error_type = error_type


class PoolTimeoutError(SandboxClientError):
    """Raised when pool doesn't reach ready state within timeout.

    This occurs when the pool doesn't have at least one ready replica
    within the specified timeout.
    """

    pass


class SandboxNotReadyError(SandboxClientError):
    """Raised when attempting to interact with a sandbox that is not ready."""

    pass


class SandboxTimeoutError(SandboxClientError):
    """Raised when an operation times out.

    Attributes:
        last_status: The last known status of the sandbox before timeout.
    """

    def __init__(self, message: str, last_status: Optional[str] = None):
        """Initialize the error."""
        super().__init__(message)
        self.last_status = last_status

    def __str__(self) -> str:
        """Return string representation."""
        base = super().__str__()
        if self.last_status:
            return f"{base} (last_status: {self.last_status})"
        return base


class SandboxValidationError(SandboxClientError):
    """Raised when request validation fails (invalid resource values).

    This includes:
    - Resource values exceeding server-defined limits (CPU, memory, storage)
    - Invalid resource units
    - Invalid name formats (must start with lowercase letter, only lowercase
      letters, numbers, and hyphens allowed, cannot end with hyphen)

    Attributes:
        field: The field that failed validation (e.g., "cpu", "memory").
        details: List of validation error details from the API.
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[list[dict]] = None,
    ):
        """Initialize the error."""
        super().__init__(message)
        self.field = field
        self.details = details or []


class SandboxQuotaExceededError(SandboxClientError):
    """Raised when organization quota limits are exceeded.

    This indicates the organization has reached its resource limits
    (max sandboxes, total CPU, total memory, etc.).

    Users should contact support@langchain.dev to increase quotas.

    Attributes:
        quota_type: Type of quota exceeded (e.g., "sandbox_count", "cpu").
    """

    def __init__(self, message: str, quota_type: Optional[str] = None):
        """Initialize the error."""
        super().__init__(message)
        self.quota_type = quota_type


class SandboxCreationError(SandboxClientError):
    """Raised when sandbox creation fails (image pull, crash, config error).

    This is the base class for all sandbox creation failures. Use the specific
    subclasses (SandboxImageError, SandboxCrashError, SandboxSchedulingError)
    to catch specific error types.

    Attributes:
        error_type: Machine-readable error type from the API.
    """

    def __init__(
        self,
        message: str,
        error_type: Optional[str] = None,
    ):
        """Initialize the error."""
        super().__init__(message)
        self.error_type = error_type

    def __str__(self) -> str:
        """Return string representation."""
        if self.error_type:
            return f"{super().__str__()} [{self.error_type}]"
        return super().__str__()


class SandboxImageError(SandboxCreationError):
    """Raised for image pull failures.

    Error types: ImagePull.

    This typically indicates the container image doesn't exist, is inaccessible,
    or the image reference is malformed. Check your template's image configuration.
    """

    pass


class SandboxCrashError(SandboxCreationError):
    """Raised when container crashes during startup.

    Error types: CrashLoop, SandboxConfig.

    This typically indicates an issue with the container itself - it may be
    crashing on startup, running out of memory, or have an invalid configuration.
    """

    pass


class SandboxSchedulingError(SandboxCreationError):
    """Raised when sandbox cannot be scheduled.

    Error types: Unschedulable.

    This typically indicates insufficient cluster resources (CPU, memory, etc.).
    May succeed on retry when resources become available.
    """

    pass


# =============================================================================
# Sandbox Operation Errors (runtime errors during sandbox interaction)
# =============================================================================


class DataplaneNotConfiguredError(SandboxClientError):
    """Raised when dataplane_url is not available for the sandbox.

    This occurs when the sandbox-router URL is not configured for the cluster,
    meaning runtime operations (run, write, read) cannot be performed directly.
    """

    pass


class SandboxOperationError(SandboxClientError):
    """Base class for sandbox operation errors (run, read, write).

    This is raised when an operation on a running sandbox fails.

    Attributes:
        error_type: Machine-readable error type from the API.
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


class SandboxCommandError(SandboxOperationError):
    """Raised when command execution fails in the sandbox.

    Error type: CommandError.

    This indicates the command could not be executed (not the same as
    a non-zero exit code, which is returned in ExecutionResult).
    """

    pass


class SandboxWriteError(SandboxOperationError):
    """Raised when writing a file to the sandbox fails.

    Error type: WriteError.

    Common causes include permission denied, disk full, or invalid path.
    """

    pass


class SandboxReadError(SandboxOperationError):
    """Raised when reading a file from the sandbox fails.

    Error type: ReadError.

    Common causes include permission denied or I/O errors.
    For file not found, SandboxNotFoundError is raised instead.
    """

    pass


class SandboxPermissionError(SandboxOperationError):
    """Raised when an operation is denied due to permissions.

    This is raised for HTTP 403 errors from sandbox operations.
    """

    pass
