"""Sandbox class for interacting with a specific sandbox instance."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Literal, Optional, Union, overload

import httpx

from langsmith.sandbox._exceptions import (
    DataplaneNotConfiguredError,
    ResourceNotFoundError,
    SandboxConnectionError,
)
from langsmith.sandbox._helpers import handle_sandbox_http_error
from langsmith.sandbox._models import (
    CommandHandle,
    ExecutionResult,
)

if TYPE_CHECKING:
    from langsmith.sandbox._client import SandboxClient


@dataclass
class Sandbox:
    """Represents an active sandbox for running commands and file operations.

    This class is typically obtained from SandboxClient.sandbox() and supports
    the context manager protocol for automatic cleanup.

    Attributes:
        name: Display name (can be updated).
        template_name: Name of the template used to create this sandbox.
        dataplane_url: URL for data plane operations (file I/O, command execution).
        id: Unique identifier (UUID). Remains constant even if name changes.
            May be None for resources created before ID support was added.
        created_at: Timestamp when the sandbox was created.
        updated_at: Timestamp when the sandbox was last updated.

    Example:
        with client.sandbox(template_name="python-sandbox") as sandbox:
            result = sandbox.run("python --version")
            print(result.stdout)
    """

    # Data fields (from API response)
    name: str
    template_name: str
    dataplane_url: Optional[str] = None
    id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    # Internal fields (not from API)
    _client: SandboxClient = field(repr=False, default=None)  # type: ignore
    _auto_delete: bool = field(repr=False, default=True)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        client: SandboxClient,
        auto_delete: bool = True,
    ) -> Sandbox:
        """Create a Sandbox from API response dict.

        Args:
            data: API response dictionary containing sandbox data.
            client: Parent SandboxClient for operations.
            auto_delete: Whether to delete the sandbox on context exit.

        Returns:
            Sandbox instance.
        """
        return cls(
            name=data.get("name", ""),
            template_name=data.get("template_name", ""),
            dataplane_url=data.get("dataplane_url"),
            id=data.get("id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            _client=client,
            _auto_delete=auto_delete,
        )

    def __enter__(self) -> Sandbox:
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Exit context manager, optionally deleting the sandbox."""
        if self._auto_delete:
            try:
                self._client.delete_sandbox(self.name)
            except Exception:
                # Don't raise on cleanup errors
                pass

    def _require_dataplane_url(self) -> str:
        """Validate and return the dataplane URL.

        Returns:
            The dataplane URL.

        Raises:
            DataplaneNotConfiguredError: If dataplane_url is not configured.
        """
        if not self.dataplane_url:
            raise DataplaneNotConfiguredError(
                f"Sandbox '{self.name}' does not have a dataplane_url configured. "
                "Runtime operations require a dataplane URL."
            )
        return self.dataplane_url

    @overload
    def run(
        self,
        command: str,
        *,
        timeout: int = ...,
        env: Optional[dict[str, str]] = ...,
        cwd: Optional[str] = ...,
        shell: str = ...,
        on_stdout: Optional[Callable[[str], Any]] = ...,
        on_stderr: Optional[Callable[[str], Any]] = ...,
        wait: Literal[True] = ...,
    ) -> ExecutionResult: ...

    @overload
    def run(
        self,
        command: str,
        *,
        timeout: int = ...,
        env: Optional[dict[str, str]] = ...,
        cwd: Optional[str] = ...,
        shell: str = ...,
        on_stdout: Optional[Callable[[str], Any]] = ...,
        on_stderr: Optional[Callable[[str], Any]] = ...,
        wait: Literal[False],
    ) -> CommandHandle: ...

    def run(
        self,
        command: str,
        *,
        timeout: int = 60,
        env: Optional[dict[str, str]] = None,
        cwd: Optional[str] = None,
        shell: str = "/bin/bash",
        on_stdout: Optional[Callable[[str], Any]] = None,
        on_stderr: Optional[Callable[[str], Any]] = None,
        wait: bool = True,
    ) -> Union[ExecutionResult, CommandHandle]:
        """Execute a command in the sandbox.

        Args:
            command: Shell command to execute.
            timeout: Command timeout in seconds.
            env: Environment variables to set for the command.
            cwd: Working directory for command execution. If None, uses sandbox default.
            shell: Shell to use for command execution. Defaults to "/bin/bash".
            on_stdout: Callback invoked with each stdout chunk as it arrives.
                Blocks until the command completes and returns ExecutionResult.
                Cannot be combined with wait=False.
            on_stderr: Callback invoked with each stderr chunk as it arrives.
                Blocks until the command completes and returns ExecutionResult.
                Cannot be combined with wait=False.
            wait: If True (default), block until the command completes and
                return ExecutionResult. If False, return a
                CommandHandle immediately for streaming output,
                kill, stdin input, and reconnection. Cannot be combined with
                on_stdout/on_stderr callbacks.

        Returns:
            ExecutionResult when wait=True (default).
            CommandHandle when wait=False.

        Raises:
            ValueError: If wait=False is combined with callbacks.
            DataplaneNotConfiguredError: If dataplane_url is not configured.
            SandboxOperationError: If command execution fails.
            CommandTimeoutError: If command exceeds its timeout.
            SandboxConnectionError: If connection to sandbox fails.
            SandboxNotReadyError: If sandbox is not ready.
            SandboxClientError: For other errors.
        """
        if not wait and (on_stdout or on_stderr):
            raise ValueError(
                "Cannot combine wait=False with on_stdout/on_stderr callbacks. "
                "Use wait=False and iterate the CommandHandle, or use callbacks."
            )

        self._require_dataplane_url()

        # When not waiting or callbacks are requested, WS is required
        use_ws = not wait or on_stdout or on_stderr
        if use_ws:
            return self._run_ws(
                command,
                timeout=timeout,
                env=env,
                cwd=cwd,
                shell=shell,
                wait=wait,
                on_stdout=on_stdout,
                on_stderr=on_stderr,
            )

        # Default (wait=True, no callbacks): try WS, fall back to HTTP.
        # Catch broad exceptions so that unexpected WS failures (e.g. version
        # incompatibilities) don't break users who don't need WS features.
        try:
            return self._run_ws(
                command,
                timeout=timeout,
                env=env,
                cwd=cwd,
                shell=shell,
                wait=True,
                on_stdout=None,
                on_stderr=None,
            )
        except (SandboxConnectionError, ImportError, OSError, TypeError):
            return self._run_http(
                command,
                timeout=timeout,
                env=env,
                cwd=cwd,
                shell=shell,
            )

    def _run_ws(
        self,
        command: str,
        *,
        timeout: int,
        env: Optional[dict[str, str]],
        cwd: Optional[str],
        shell: str,
        wait: bool,
        on_stdout: Optional[Callable[[str], Any]],
        on_stderr: Optional[Callable[[str], Any]],
    ) -> Union[ExecutionResult, CommandHandle]:
        """Execute via WebSocket /execute/ws."""
        from langsmith.sandbox._ws_execute import run_ws_stream

        dataplane_url = self._require_dataplane_url()
        api_key = self._client._api_key

        msg_stream, control = run_ws_stream(
            dataplane_url,
            api_key,
            command,
            timeout=timeout,
            env=env,
            cwd=cwd,
            shell=shell,
            on_stdout=on_stdout,
            on_stderr=on_stderr,
        )

        handle = CommandHandle(msg_stream, control, self)

        if not wait:
            return handle

        return handle.result  # blocks until command completes

    def _run_http(
        self,
        command: str,
        *,
        timeout: int,
        env: Optional[dict[str, str]],
        cwd: Optional[str],
        shell: str,
    ) -> ExecutionResult:
        """Execute via HTTP POST /execute (existing implementation)."""
        dataplane_url = self._require_dataplane_url()
        url = f"{dataplane_url}/execute"
        payload: dict[str, Any] = {
            "command": command,
            "timeout": timeout,
            "shell": shell,
        }
        if env is not None:
            payload["env"] = env
        if cwd is not None:
            payload["cwd"] = cwd

        try:
            response = self._client._http.post(url, json=payload, timeout=timeout + 10)
            response.raise_for_status()
            data = response.json()
            return ExecutionResult(
                stdout=data.get("stdout", ""),
                stderr=data.get("stderr", ""),
                exit_code=data.get("exit_code", -1),
            )
        except httpx.ConnectError as e:
            raise SandboxConnectionError(
                f"Failed to connect to sandbox '{self.name}': {e}"
            ) from e
        except httpx.HTTPStatusError as e:
            handle_sandbox_http_error(e)
            # This line should never be reached but satisfies type checker
            raise  # pragma: no cover

    def reconnect(
        self,
        command_id: str,
        *,
        stdout_offset: int = 0,
        stderr_offset: int = 0,
    ) -> CommandHandle:
        """Reconnect to a running or recently-finished command.

        Resumes output from the given byte offsets. Any output produced while
        the client was disconnected is replayed from the server's ring buffer.

        Args:
            command_id: The command ID from handle.command_id.
            stdout_offset: Byte offset to resume stdout from (default: 0).
            stderr_offset: Byte offset to resume stderr from (default: 0).

        Returns:
            A CommandHandle for the command.

        Raises:
            SandboxOperationError: If command_id is not found or session expired.
            SandboxConnectionError: If connection to sandbox fails.
        """
        from langsmith.sandbox._ws_execute import reconnect_ws_stream

        dataplane_url = self._require_dataplane_url()
        api_key = self._client._api_key

        msg_stream, control = reconnect_ws_stream(
            dataplane_url,
            api_key,
            command_id,
            stdout_offset=stdout_offset,
            stderr_offset=stderr_offset,
        )

        return CommandHandle(
            msg_stream,
            control,
            self,
            command_id=command_id,
            stdout_offset=stdout_offset,
            stderr_offset=stderr_offset,
        )

    def write(
        self,
        path: str,
        content: Union[str, bytes],
        *,
        timeout: int = 60,
    ) -> None:
        """Write content to a file in the sandbox.

        Args:
            path: Target file path in the sandbox.
            content: File content (str or bytes).
            timeout: Request timeout in seconds.

        Raises:
            DataplaneNotConfiguredError: If dataplane_url is not configured.
            SandboxOperationError: If file write fails.
            SandboxConnectionError: If connection to sandbox fails.
            SandboxNotReadyError: If sandbox is not ready.
            SandboxClientError: For other errors.
        """
        dataplane_url = self._require_dataplane_url()
        url = f"{dataplane_url}/upload"

        # Ensure content is bytes for multipart upload
        if isinstance(content, str):
            content = content.encode("utf-8")

        files = {"file": ("file", content)}

        try:
            response = self._client._http.post(
                url, params={"path": path}, files=files, timeout=timeout
            )
            response.raise_for_status()
        except httpx.ConnectError as e:
            raise SandboxConnectionError(
                f"Failed to connect to sandbox '{self.name}': {e}"
            ) from e
        except httpx.HTTPStatusError as e:
            handle_sandbox_http_error(e)

    def read(self, path: str, *, timeout: int = 60) -> bytes:
        """Read a file from the sandbox.

        Args:
            path: File path to read. Supports both absolute paths (e.g., /tmp/file.txt)
                  and relative paths (resolved from /home/user/).
            timeout: Request timeout in seconds.

        Returns:
            File contents as bytes.

        Raises:
            DataplaneNotConfiguredError: If dataplane_url is not configured.
            ResourceNotFoundError: If the file doesn't exist.
            SandboxOperationError: If file read fails.
            SandboxConnectionError: If connection to sandbox fails.
            SandboxNotReadyError: If sandbox is not ready.
            SandboxClientError: For other errors.
        """
        dataplane_url = self._require_dataplane_url()
        url = f"{dataplane_url}/download"

        try:
            response = self._client._http.get(
                url, params={"path": path}, timeout=timeout
            )
            response.raise_for_status()
            return response.content
        except httpx.ConnectError as e:
            raise SandboxConnectionError(
                f"Failed to connect to sandbox '{self.name}': {e}"
            ) from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ResourceNotFoundError(
                    f"File '{path}' not found in sandbox '{self.name}'",
                    resource_type="file",
                ) from e
            handle_sandbox_http_error(e)
            # This line should never be reached but satisfies type checker
            raise  # pragma: no cover
