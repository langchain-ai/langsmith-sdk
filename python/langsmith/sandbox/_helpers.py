"""Shared helper functions for error handling.

These functions are used by both sync and async clients to parse error responses
and raise appropriate exceptions. They contain no I/O operations.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from langsmith.sandbox._exceptions import (
    PoolAlreadyExistsError,
    PoolTimeoutError,
    PoolValidationError,
    SandboxAPIError,
    SandboxAuthenticationError,
    SandboxClientError,
    SandboxCommandError,
    SandboxConnectionError,
    SandboxCrashError,
    SandboxCreationError,
    SandboxImageError,
    SandboxNotFoundError,
    SandboxNotReadyError,
    SandboxPermissionError,
    SandboxQuotaExceededError,
    SandboxReadError,
    SandboxSchedulingError,
    SandboxTimeoutError,
    SandboxValidationError,
    SandboxWriteError,
    TemplateNotFoundError,
    VolumeProvisioningError,
    VolumeTimeoutError,
)

# =============================================================================
# Error Response Parsing
# =============================================================================


def parse_error_response(error: httpx.HTTPStatusError) -> dict[str, Any]:
    """Parse standardized error response.

    Expected format: {"detail": {"error": "...", "message": "..."}}

    Returns a dict with:
    - error_type: The error type (e.g., "ImagePull", "CrashLoop")
    - message: Human-readable error message
    """
    try:
        data = error.response.json()
        detail = data.get("detail")

        # Standardized format: {"detail": {"error": "...", "message": "..."}}
        if isinstance(detail, dict):
            return {
                "error_type": detail.get("error"),
                "message": detail.get("message", str(error)),
            }

        # Pydantic validation error format: {"detail": [{"loc": [...], "msg": "..."}]}
        if isinstance(detail, list) and detail:
            messages = [d.get("msg", str(d)) for d in detail if isinstance(d, dict)]
            return {
                "error_type": None,
                "message": "; ".join(messages) if messages else str(error),
            }

        # Fallback for plain string detail
        return {"error_type": None, "message": detail or str(error)}
    except Exception:
        return {"error_type": None, "message": str(error)}


def parse_error_response_simple(error: httpx.HTTPStatusError) -> dict[str, Any]:
    """Parse error response (simplified version for sandbox operations).

    Returns a dict with:
    - error_type: The error type
    - message: Human-readable error message
    """
    try:
        data = error.response.json()
        detail = data.get("detail")

        if isinstance(detail, dict):
            return {
                "error_type": detail.get("error"),
                "message": detail.get("message", str(error)),
            }

        return {"error_type": None, "message": detail or str(error)}
    except Exception:
        return {"error_type": None, "message": str(error)}


def parse_validation_error(error: httpx.HTTPStatusError) -> list[dict]:
    """Parse Pydantic validation error response.

    Returns a list of validation error details, each containing:
    - loc: Location of the error (e.g., ["body", "resources", "cpu"])
    - msg: Human-readable error message
    - type: Error type (e.g., "value_error")
    """
    try:
        data = error.response.json()
        detail = data.get("detail", [])
        if isinstance(detail, list):
            return detail
        return []
    except Exception:
        return []


def extract_quota_type(message: str) -> Optional[str]:
    """Extract quota type from error message.

    Returns one of: "sandbox_count", "cpu", "memory", "volume_count",
    "storage", or None.
    """
    message_lower = message.lower()
    # Check for sandbox count quota
    if "sandbox" in message_lower and (
        "count" in message_lower or "limit" in message_lower
    ):
        return "sandbox_count"
    elif "cpu" in message_lower:
        return "cpu"
    elif "memory" in message_lower:
        return "memory"
    # Check for volume count quota
    elif "volume" in message_lower and (
        "count" in message_lower or "limit" in message_lower
    ):
        return "volume_count"
    elif "storage" in message_lower:
        return "storage"
    return None


# =============================================================================
# Client Error Handlers
# =============================================================================


def raise_creation_error(data: dict[str, Any], error: httpx.HTTPStatusError) -> None:
    """Raise the appropriate creation error based on error_type.

    Maps error types to specific exception types:
    - Image errors: ImagePull
    - Crash errors: CrashLoop, SandboxConfig
    - Other: Generic SandboxCreationError
    """
    error_type = data.get("error_type") or ""

    # Error types that indicate image pull failures
    image_errors = {"ImagePull"}

    # Error types that indicate container crashes or config errors
    crash_errors = {"CrashLoop", "SandboxConfig"}

    # Select the appropriate exception class
    exc_class: type[SandboxCreationError] = SandboxCreationError
    if error_type in image_errors:
        exc_class = SandboxImageError
    elif error_type in crash_errors:
        exc_class = SandboxCrashError

    raise exc_class(
        data.get("message", "Sandbox creation failed"),
        error_type=data.get("error_type"),
    ) from error


def handle_sandbox_creation_error(error: httpx.HTTPStatusError) -> None:
    """Handle HTTP errors specific to sandbox creation.

    Maps API error responses to specific exception types:
    - 408: SandboxTimeoutError (sandbox didn't become ready in time)
    - 422: SandboxValidationError (bad input) or SandboxCreationError (runtime)
    - 429: SandboxQuotaExceededError (org limits exceeded)
    - 503: SandboxSchedulingError (no resources available)
    - Other: Falls through to generic error handling
    """
    status = error.response.status_code
    data = parse_error_response(error)

    if status == 408:
        # Timeout - include the message which contains last known status
        raise SandboxTimeoutError(data["message"]) from error
    elif status == 422:
        # Check if this is a Pydantic validation error (bad input) vs creation error
        details = parse_validation_error(error)
        if details and any(d.get("type") == "value_error" for d in details):
            # Pydantic validation error (bad input - exceeds server limits)
            field = details[0].get("loc", [None])[-1] if details else None
            raise SandboxValidationError(
                message=data["message"],
                field=field,
                details=details,
            ) from error
        else:
            # Sandbox creation failed (runtime error like image pull failure)
            raise_creation_error(data, error)
    elif status == 429:
        # Organization quota exceeded
        quota_type = extract_quota_type(data["message"])
        raise SandboxQuotaExceededError(
            message=data["message"],
            quota_type=quota_type,
        ) from error
    elif status == 503:
        # Service Unavailable - scheduling failed
        raise SandboxSchedulingError(
            data["message"],
            error_type=data.get("error_type"),
        ) from error
    else:
        # Fall through to generic handling
        handle_client_http_error(error)


def handle_volume_creation_error(error: httpx.HTTPStatusError) -> None:
    """Handle HTTP errors specific to volume creation.

    Maps API error responses to specific exception types:
    - 503: VolumeProvisioningError (K8s provisioning failed)
    - 504: VolumeTimeoutError (volume didn't become ready in time)
    - Other: Falls through to generic error handling
    """
    status = error.response.status_code
    data = parse_error_response(error)

    if status == 503:
        # Provisioning failed (invalid storage class, quota exceeded at K8s level)
        raise VolumeProvisioningError(data["message"]) from error
    elif status == 504:
        # Timeout - volume didn't become ready in time
        raise VolumeTimeoutError(data["message"]) from error
    else:
        # Fall through to generic handling
        handle_client_http_error(error)


def handle_pool_error(error: httpx.HTTPStatusError) -> None:
    """Handle HTTP errors specific to pool creation/update.

    Maps API error responses to specific exception types:
    - 400: TemplateNotFoundError or PoolValidationError (template has volumes)
    - 409: PoolAlreadyExistsError
    - 429: SandboxQuotaExceededError (org limits exceeded)
    - 504: PoolTimeoutError (timeout waiting for ready replicas)
    - Other: Falls through to generic error handling
    """
    status = error.response.status_code
    data = parse_error_response(error)
    error_type = data.get("error_type")

    if status == 400:
        # Check the error type to determine the specific exception
        if error_type == "TemplateNotFound":
            raise TemplateNotFoundError(data["message"]) from error
        elif error_type == "ValidationError":
            # Template has volumes attached
            raise PoolValidationError(data["message"], error_type=error_type) from error
        else:
            # Generic bad request
            handle_client_http_error(error)
    elif status == 409:
        # Pool already exists
        raise PoolAlreadyExistsError(data["message"]) from error
    elif status == 429:
        # Organization quota exceeded
        quota_type = extract_quota_type(data["message"])
        raise SandboxQuotaExceededError(
            message=data["message"],
            quota_type=quota_type,
        ) from error
    elif status == 504:
        # Timeout waiting for pool to be ready
        raise PoolTimeoutError(data["message"]) from error
    else:
        # Fall through to generic handling
        handle_client_http_error(error)


def handle_client_http_error(error: httpx.HTTPStatusError) -> None:
    """Handle HTTP errors and raise appropriate exceptions (for client operations)."""
    data = parse_error_response(error)
    message = data["message"]
    error_type = data.get("error_type")
    status = error.response.status_code

    if status in (401, 403):
        raise SandboxAuthenticationError(message) from error
    if status == 404:
        raise SandboxNotFoundError(message) from error

    # Handle validation errors (invalid resource values, formats, etc.)
    if status == 422:
        details = parse_validation_error(error)
        field = details[0].get("loc", [None])[-1] if details else None
        raise SandboxValidationError(
            message=message,
            field=field,
            details=details,
        ) from error

    # Handle quota exceeded errors (org limits)
    if status == 429:
        quota_type = extract_quota_type(message)
        raise SandboxQuotaExceededError(
            message=message,
            quota_type=quota_type,
        ) from error

    if status == 502 and error_type == "ConnectionError":
        raise SandboxConnectionError(message) from error
    if status == 500:
        raise SandboxAPIError(message) from error
    raise SandboxClientError(message) from error


# =============================================================================
# Sandbox Operation Error Handlers
# =============================================================================


def handle_sandbox_http_error(error: httpx.HTTPStatusError) -> None:
    """Handle HTTP errors for sandbox operations (run, read, write).

    Maps API error types to specific exceptions:
    - WriteError -> SandboxWriteError
    - ReadError -> SandboxReadError
    - CommandError -> SandboxCommandError
    - ConnectionError (502) -> SandboxConnectionError
    - FileNotFound / 404 -> SandboxNotFoundError
    - NotReady (400) -> SandboxNotReadyError
    - 403 -> SandboxPermissionError
    """
    data = parse_error_response_simple(error)
    message = data["message"]
    error_type = data.get("error_type")
    status = error.response.status_code

    # Operation-specific errors (from sandbox runtime)
    if error_type == "WriteError":
        raise SandboxWriteError(message, error_type=error_type) from error
    if error_type == "ReadError":
        raise SandboxReadError(message, error_type=error_type) from error
    if error_type == "CommandError":
        raise SandboxCommandError(message, error_type=error_type) from error

    # Permission denied
    if status == 403:
        raise SandboxPermissionError(message, error_type=error_type) from error

    # Connection to sandbox failed
    if status == 502 and error_type == "ConnectionError":
        raise SandboxConnectionError(message) from error

    # Not ready / not found
    if status == 400 and error_type == "NotReady":
        raise SandboxNotReadyError(message) from error
    if status == 404 or error_type == "FileNotFound":
        raise SandboxNotFoundError(message) from error

    raise SandboxClientError(message) from error
