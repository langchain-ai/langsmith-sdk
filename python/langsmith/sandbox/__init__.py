"""LangSmith Sandbox Module.

This module provides sandboxed code execution capabilities through the
LangSmith Sandbox API.

Example:
    from langsmith.sandbox import SandboxClient

    # Uses LANGSMITH_ENDPOINT and LANGSMITH_API_KEY from environment
    client = SandboxClient()

    with client.sandbox(template_name="python-sandbox") as sb:
        result = sb.run("python --version")
        print(result.stdout)

    # Or async:
    from langsmith.sandbox import AsyncSandboxClient

    async with AsyncSandboxClient() as client:
        async with await client.sandbox(template_name="python-sandbox") as sb:
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
    ResourceInUseError,
    ResourceNameConflictError,
    ResourceNotFoundError,
    ResourceTimeoutError,
    SandboxAPIError,
    SandboxAuthenticationError,
    SandboxClientError,
    SandboxConnectionError,
    SandboxCreationError,
    SandboxNotReadyError,
    SandboxOperationError,
    SandboxServerReloadError,
    ValidationError,
)
from langsmith.sandbox._models import (
    AsyncCommandHandle,
    CommandHandle,
    ExecutionResult,
    OutputChunk,
    Pool,
    ResourceSpec,
    SandboxTemplate,
    Volume,
    VolumeMountSpec,
)
from langsmith.sandbox._sandbox import Sandbox

__all__ = [
    # Main classes
    "SandboxClient",
    "AsyncSandboxClient",
    "Sandbox",
    "AsyncSandbox",
    # Models
    "SandboxTemplate",
    "ResourceSpec",
    "ExecutionResult",
    "Volume",
    "VolumeMountSpec",
    "Pool",
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
    "ResourceNotFoundError",
    "ResourceTimeoutError",
    "ResourceInUseError",
    "ResourceAlreadyExistsError",
    "ResourceNameConflictError",
    # Validation and quota errors
    "ValidationError",
    "QuotaExceededError",
    # Sandbox-specific errors
    "SandboxCreationError",
    "SandboxNotReadyError",
    "SandboxOperationError",
    "CommandTimeoutError",
    "DataplaneNotConfiguredError",
]

# Emit warning on import
import warnings

warnings.warn(
    "langsmith.sandbox is in alpha. "
    "This feature is experimental, and breaking changes are expected.",
    FutureWarning,
    stacklevel=2,
)
