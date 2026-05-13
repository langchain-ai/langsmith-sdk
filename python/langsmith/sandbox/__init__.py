"""LangSmith Sandbox Module.

This module provides sandboxed code execution capabilities through the
LangSmith Sandbox API.

Example:
    from langsmith.sandbox import SandboxClient

    # Uses LANGSMITH_ENDPOINT and LANGSMITH_API_KEY from environment
    client = SandboxClient()

    snapshot = client.create_snapshot(
        docker_image="python:3.12-slim", name="python-snapshot"
    )
    with client.sandbox(snapshot_id=snapshot.id) as sb:
        result = sb.run("python --version")
        print(result.stdout)

    # Or async:
    from langsmith.sandbox import AsyncSandboxClient

    async with AsyncSandboxClient() as client:
        snapshot = await client.create_snapshot(
            docker_image="python:3.12-slim", name="python-snapshot"
        )
        async with await client.sandbox(snapshot_id=snapshot.id) as sb:
            result = await sb.run("python --version")
            print(result.stdout)
"""

from langsmith.sandbox._async_client import AsyncSandboxClient
from langsmith.sandbox._async_sandbox import AsyncSandbox
from langsmith.sandbox._client import SandboxClient
from langsmith.sandbox._exceptions import (
    CommandTimeoutError,
    DataplaneNotConfiguredError,
    QuotaExceededError,
    ResourceAlreadyExistsError,
    ResourceCreationError,
    ResourceInUseError,
    ResourceNameConflictError,
    ResourceNotFoundError,
    ResourceTimeoutError,
    SandboxAPIError,
    SandboxAuthenticationError,
    SandboxClientError,
    SandboxConnectionError,
    SandboxNotReadyError,
    SandboxOperationError,
    SandboxServerReloadError,
    TunnelConnectionRefusedError,
    TunnelError,
    TunnelPortNotAllowedError,
    TunnelUnsupportedVersionError,
    ValidationError,
)
from langsmith.sandbox._models import (
    AsyncCommandHandle,
    AsyncServiceURL,
    CommandHandle,
    ExecutionResult,
    OutputChunk,
    ResourceStatus,
    ServiceURL,
    Snapshot,
)
from langsmith.sandbox._sandbox import Sandbox
from langsmith.sandbox._tunnel import AsyncTunnel, Tunnel

__all__ = [
    # Main classes
    "SandboxClient",
    "AsyncSandboxClient",
    "Sandbox",
    "AsyncSandbox",
    # Models
    "ResourceStatus",
    "ExecutionResult",
    "Snapshot",
    "ServiceURL",
    "AsyncServiceURL",
    # WebSocket streaming models
    "CommandHandle",
    "AsyncCommandHandle",
    "OutputChunk",
    # Base and connection errors
    "SandboxClientError",
    "SandboxAPIError",
    "SandboxAuthenticationError",
    "SandboxConnectionError",
    "SandboxServerReloadError",
    # Resource errors (type-based with resource_type attribute)
    "ResourceCreationError",
    "ResourceNotFoundError",
    "ResourceTimeoutError",
    "ResourceInUseError",
    "ResourceAlreadyExistsError",
    "ResourceNameConflictError",
    # Validation and quota errors
    "ValidationError",
    "QuotaExceededError",
    # Sandbox-specific errors
    "SandboxNotReadyError",
    "SandboxOperationError",
    "CommandTimeoutError",
    "DataplaneNotConfiguredError",
    # Tunnel
    "Tunnel",
    "AsyncTunnel",
    "TunnelError",
    "TunnelPortNotAllowedError",
    "TunnelConnectionRefusedError",
    "TunnelUnsupportedVersionError",
]
