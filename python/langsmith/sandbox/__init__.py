"""LangSmith Sandbox Module.

This module provides sandboxed code execution capabilities through the
LangSmith Sandbox API.

Example:
    # Uses LANGSMITH_ENDPOINT and LANGSMITH_API_KEY from environment
    from langsmith import sandbox

    client = sandbox.SandboxClient()

    with client.sandbox(template_name="python-sandbox") as sb:
        result = sb.run("python --version")
        print(result.stdout)

    # Or async:
    async with sandbox.AsyncSandboxClient() as client:
        async with await client.sandbox(template_name="python-sandbox") as sb:
            result = await sb.run("python --version")
            print(result.stdout)
"""

from langsmith.sandbox._async_client import AsyncSandboxClient
from langsmith.sandbox._async_sandbox import AsyncSandbox
from langsmith.sandbox._client import SandboxClient
from langsmith.sandbox._exceptions import (
    DataplaneNotConfiguredError,
    PoolAlreadyExistsError,
    PoolNotFoundError,
    PoolTimeoutError,
    PoolValidationError,
    ResourceNameConflictError,
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
    SandboxOperationError,
    SandboxPermissionError,
    SandboxQuotaExceededError,
    SandboxReadError,
    SandboxSchedulingError,
    SandboxTimeoutError,
    SandboxValidationError,
    SandboxWriteError,
    TemplateInUseError,
    TemplateNotFoundError,
    VolumeInUseError,
    VolumeNotFoundError,
    VolumeProvisioningError,
    VolumeResizeError,
    VolumeTimeoutError,
)
from langsmith.sandbox._models import (
    ExecutionResult,
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
    # Base exceptions
    "SandboxClientError",
    "SandboxAPIError",
    "SandboxAuthenticationError",
    "SandboxConnectionError",
    "SandboxNotFoundError",
    "SandboxNotReadyError",
    "SandboxTimeoutError",
    # Validation and quota errors
    "SandboxValidationError",
    "SandboxQuotaExceededError",
    # Creation errors
    "SandboxCreationError",
    "SandboxImageError",
    "SandboxCrashError",
    "SandboxSchedulingError",
    # Operation errors (runtime)
    "DataplaneNotConfiguredError",
    "SandboxOperationError",
    "SandboxCommandError",
    "SandboxWriteError",
    "SandboxReadError",
    "SandboxPermissionError",
    # Resource not found errors
    "TemplateNotFoundError",
    "VolumeNotFoundError",
    # Volume errors
    "VolumeInUseError",
    "VolumeResizeError",
    "VolumeProvisioningError",
    "VolumeTimeoutError",
    # Template errors
    "TemplateInUseError",
    # Pool errors
    "PoolNotFoundError",
    "PoolAlreadyExistsError",
    "PoolValidationError",
    "PoolTimeoutError",
    # Name conflict errors (409 on update)
    "ResourceNameConflictError",
]
