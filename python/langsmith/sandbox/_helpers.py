"""Shared helper functions for error handling.

These functions are used by both sync and async clients to parse error responses
and raise appropriate exceptions. They contain no I/O operations.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

from langsmith._openapi_client._httpx import httpx
from langsmith.sandbox._exceptions import (
    QuotaExceededError,
    ResourceCreationError,
    ResourceNotFoundError,
    ResourceTimeoutError,
    SandboxAPIError,
    SandboxAuthenticationError,
    SandboxClientError,
    SandboxConnectionError,
    SandboxNotReadyError,
    SandboxOperationError,
    ValidationError,
)
from langsmith.sandbox._models import FileChunk, FileStat, _run_config_payload

# =============================================================================
# Header Utilities
# =============================================================================


def merge_headers(
    base_headers: Optional[Mapping[str, str]] = None,
    override_headers: Optional[Mapping[str, str]] = None,
) -> dict[str, str]:
    """Merge request headers, giving precedence to overrides.

    Names are normalized to lowercase so an override replaces a base header that
    differs only in casing. HTTP header names are case-insensitive, so keeping
    both would be ambiguous — a server reading the first value would see the
    base header instead of the override.
    """
    merged: dict[str, str] = {}
    for headers in (base_headers, override_headers):
        for name, value in (headers or {}).items():
            merged[name.lower()] = value
    return merged


# =============================================================================
# Input Validation
# =============================================================================


def resolve_command_run_config(
    run_config: Any, *, env: Optional[dict[str, str]], cwd: Optional[str]
) -> Optional[dict[str, Any]]:
    """Normalize a per-command run_config, rejecting the deprecated pairing.

    The server answers 400 for a request carrying both spellings rather than
    letting one silently win, so refuse it here where the message can name
    the replacement.
    """
    if run_config is None:
        return None
    if env is not None or cwd is not None:
        raise ValueError(
            "Cannot combine run_config with the deprecated env/cwd arguments. "
            "Use run_config.env_vars and run_config.work_dir instead."
        )
    return _run_config_payload(run_config)


def resolve_close_input(close_input: Optional[bool], *, pty: bool) -> bool:
    """Whether to half-close stdin at spawn.

    Defaults on for a non-PTY command: a command that reads stdin otherwise
    blocks on a pipe nobody writes to until the timeout kills it. A PTY has
    no separate write end to close, so the server ignores the flag there.
    """
    if pty:
        return False
    if close_input is None:
        return True
    return close_input


def build_range_header(
    *, start: Optional[int], end: Optional[int], suffix_bytes: Optional[int]
) -> str:
    """Render a byte range as an RFC 9110 ``Range`` header value."""
    if suffix_bytes is not None:
        if start is not None or end is not None:
            raise ValueError("Cannot combine suffix_bytes with start/end.")
        if suffix_bytes <= 0:
            raise ValueError("suffix_bytes must be positive.")
        return f"bytes=-{suffix_bytes}"
    if start is None:
        raise ValueError("Provide start (with optional end), or suffix_bytes.")
    if start < 0:
        raise ValueError("start must not be negative.")
    if end is None:
        return f"bytes={start}-"
    if end < start:
        raise ValueError("end must not precede start.")
    return f"bytes={start}-{end}"


def _parse_content_range(value: Optional[str]) -> tuple[int, Optional[int]]:
    """Read the first byte offset and total size out of ``Content-Range``."""
    if not value or not value.startswith("bytes "):
        return 0, None
    spec = value[len("bytes ") :].strip()
    range_part, _, total_part = spec.partition("/")
    start = 0
    first, _, _ = range_part.partition("-")
    if first.strip().isdigit():
        start = int(first)
    total = int(total_part) if total_part.strip().isdigit() else None
    return start, total


def file_stat_from_response(response: httpx.Response) -> FileStat:
    """Build a FileStat from a HEAD response's headers."""
    length = response.headers.get("content-length")
    return FileStat(
        size_bytes=int(length) if length and length.isdigit() else 0,
        etag=response.headers.get("etag"),
        last_modified=response.headers.get("last-modified"),
        content_type=response.headers.get("content-type"),
    )


def file_chunk_from_response(response: httpx.Response) -> FileChunk:
    """Build a FileChunk from a ranged download response."""
    if response.status_code == 304:
        return FileChunk(
            content=b"",
            etag=response.headers.get("etag"),
            unchanged=True,
            last_modified=response.headers.get("last-modified"),
        )
    partial = response.status_code == 206
    start, total = _parse_content_range(response.headers.get("content-range"))
    content = response.content
    if not partial:
        # A stale If-Range answers 200 with the whole file; the caller has to
        # restart rather than append, so report it from byte zero.
        start = 0
        total = len(content)
    return FileChunk(
        content=content,
        etag=response.headers.get("etag"),
        total_bytes=total,
        start=start,
        partial=partial,
        last_modified=response.headers.get("last-modified"),
    )


def raise_file_http_error(
    error: httpx.HTTPStatusError, *, path: str, sandbox_name: str
) -> None:
    """Map a file-operation HTTP error, including the non-JSON 416."""
    status = error.response.status_code
    if status == 404:
        raise ResourceNotFoundError(
            f"File '{path}' not found in sandbox '{sandbox_name}'",
            resource_type="file",
        ) from error
    if status == 416:
        raise SandboxOperationError(
            f"Requested range for '{path}' starts past the end of the file "
            f"({error.response.headers.get('content-range', 'unknown size')})."
        ) from error
    handle_sandbox_http_error(error)


def validate_service_params(port: int, expires_in_seconds: int) -> None:
    """Validate parameters for service URL generation.

    Args:
        port: Target port inside the sandbox.
        expires_in_seconds: Token TTL.

    Raises:
        ValueError: If port or TTL is out of range.
    """
    if not isinstance(port, int) or port <= 0:
        raise ValueError(f"port must be a positive integer, got {port!r}")
    if not isinstance(expires_in_seconds, int) or not (
        1 <= expires_in_seconds <= 86400
    ):
        raise ValueError(
            f"expires_in_seconds must be between 1 and 86400, "
            f"got {expires_in_seconds!r}"
        )


def validate_ttl(value: Optional[int], name: str) -> None:
    """Validate a TTL value for sandbox create/update.

    Args:
        value: TTL in seconds (None means unset, 0 disables).
        name: Parameter name for error messages.

    Raises:
        ValueError: If value is negative or not a multiple of 60.
    """
    if value is None:
        return
    if value < 0:
        raise ValueError(f"{name} must be >= 0, got {value}")
    if value != 0 and value % 60 != 0:
        raise ValueError(f"{name} must be a multiple of 60 seconds, got {value}")


# =============================================================================
# Error Response Parsing
# =============================================================================


def _message_with_error_id(message: str, error_id: Any) -> str:
    if isinstance(error_id, str) and error_id:
        return f"{message} (error_id={error_id})"
    return message


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
                "message": _message_with_error_id(
                    detail.get("message", str(error)), detail.get("error_id")
                ),
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
                "message": _message_with_error_id(
                    detail.get("message", str(error)), detail.get("error_id")
                ),
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

    Returns one of: "sandbox_count", "cpu", "memory", "storage", or None.
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
    elif "storage" in message_lower:
        return "storage"
    return None


# =============================================================================
# Client Error Handlers
# =============================================================================


def raise_creation_error(
    data: dict[str, Any],
    error: httpx.HTTPStatusError,
    resource_type: str = "sandbox",
) -> None:
    """Raise ResourceCreationError with the error_type from the API response.

    The error_type indicates the specific failure reason:
    - ImagePull: Image pull failed
    - CrashLoop: Container crashed during startup
    - SandboxConfig: Configuration error
    - Unschedulable: Cannot be scheduled
    """
    raise ResourceCreationError(
        data.get("message", f"{resource_type.title()} creation failed"),
        resource_type=resource_type,
        error_type=data.get("error_type"),
    ) from error


def handle_sandbox_creation_error(error: httpx.HTTPStatusError) -> None:
    """Handle HTTP errors specific to sandbox creation.

    Maps API error responses to specific exception types:
    - 408: ResourceTimeoutError (sandbox didn't become ready in time)
    - 422: ValidationError (bad input) or ResourceCreationError (runtime)
    - 429: QuotaExceededError (org limits exceeded)
    - 503: ResourceCreationError (no resources available)
    - Other: Falls through to generic error handling
    """
    status = error.response.status_code
    data = parse_error_response(error)

    if status == 408:
        # Timeout - include the message which contains last known status
        raise ResourceTimeoutError(data["message"], resource_type="sandbox") from error
    elif status == 422:
        # Check if this is a Pydantic validation error (bad input) vs creation error
        details = parse_validation_error(error)
        if details and any(d.get("type") == "value_error" for d in details):
            # Pydantic validation error (bad input - exceeds server limits)
            field = details[0].get("loc", [None])[-1] if details else None
            raise ValidationError(
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
        raise QuotaExceededError(
            message=data["message"],
            quota_type=quota_type,
        ) from error
    elif status == 503:
        # Service Unavailable - scheduling failed
        raise ResourceCreationError(
            data["message"],
            resource_type="sandbox",
            error_type=data.get("error_type") or "Unschedulable",
        ) from error
    else:
        # Fall through to generic handling
        handle_client_http_error(error)


def raise_if_not_ready(error: httpx.HTTPStatusError, name: str) -> None:
    """Raise ``SandboxNotReadyError`` when the API rejected a proxy-config update.

    A proxy config can only be written to a ``ready`` sandbox, and that status
    check is the sole source of ``InvalidRequest`` on the update endpoint for the
    fields this client sends — a typed error lets callers start the sandbox and
    retry instead of matching on status codes.
    """
    if error.response.status_code != 400:
        return
    data = parse_error_response(error)
    if data.get("error_type") != "InvalidRequest":
        return
    raise SandboxNotReadyError(
        data["message"] or f"Sandbox '{name}' is not ready"
    ) from error


def handle_client_http_error(error: httpx.HTTPStatusError) -> None:
    """Handle HTTP errors and raise appropriate exceptions (for client operations)."""
    data = parse_error_response(error)
    message = data["message"]
    error_type = data.get("error_type")
    status = error.response.status_code

    if status in (401, 403):
        raise SandboxAuthenticationError(message) from error
    if status == 404:
        raise ResourceNotFoundError(message) from error

    # Handle validation errors (invalid resource values, formats, etc.)
    if status == 422:
        details = parse_validation_error(error)
        field = details[0].get("loc", [None])[-1] if details else None
        raise ValidationError(
            message=message,
            field=field,
            details=details,
        ) from error

    # Handle quota exceeded errors (org limits)
    if status == 429:
        quota_type = extract_quota_type(message)
        raise QuotaExceededError(
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
    - WriteError -> SandboxOperationError (operation="write")
    - ReadError -> SandboxOperationError (operation="read")
    - CommandError -> SandboxOperationError (operation="command")
    - ConnectionError (502) -> SandboxConnectionError
    - FileNotFound / 404 -> ResourceNotFoundError (resource_type="file")
    - NotReady (400) -> SandboxNotReadyError
    - ServiceUnavailable (503) -> SandboxNotReadyError
    - 403 -> SandboxOperationError (permission denied)
    """
    data = parse_error_response_simple(error)
    message = data["message"]
    error_type = data.get("error_type")
    status = error.response.status_code

    # Operation-specific errors (from sandbox runtime)
    if error_type == "WriteError":
        raise SandboxOperationError(
            message, operation="write", error_type=error_type
        ) from error
    if error_type == "ReadError":
        raise SandboxOperationError(
            message, operation="read", error_type=error_type
        ) from error
    if error_type == "CommandError":
        raise SandboxOperationError(
            message, operation="command", error_type=error_type
        ) from error

    # Permission denied
    if status == 403:
        raise SandboxOperationError(
            message, operation=None, error_type="PermissionDenied"
        ) from error

    # Connection to sandbox failed
    if status == 502 and error_type == "ConnectionError":
        raise SandboxConnectionError(message) from error

    # Not ready / not found
    if (status == 400 and error_type == "NotReady") or (
        status == 503 and error_type == "ServiceUnavailable"
    ):
        raise SandboxNotReadyError(message) from error
    if status == 404 or error_type == "FileNotFound":
        raise ResourceNotFoundError(message, resource_type="file") from error

    raise SandboxClientError(message) from error
