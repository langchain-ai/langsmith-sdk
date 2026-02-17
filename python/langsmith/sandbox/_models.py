"""Data models for the sandbox client."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from langsmith.sandbox._exceptions import (
    SandboxConnectionError,
    SandboxOperationError,
    SandboxServerReloadError,
)

if TYPE_CHECKING:
    from langsmith.sandbox._async_sandbox import AsyncSandbox
    from langsmith.sandbox._sandbox import Sandbox
    from langsmith.sandbox._ws_execute import (
        _AsyncWSStreamControl,
        _WSStreamControl,
    )


@dataclass
class ExecutionResult:
    """Result of executing a command in a sandbox."""

    stdout: str
    stderr: str
    exit_code: int

    @property
    def success(self) -> bool:
        """Return True if the command exited with code 0."""
        return self.exit_code == 0


@dataclass
class ResourceSpec:
    """Resource specification for a sandbox."""

    cpu: str = "500m"
    memory: str = "512Mi"
    storage: Optional[str] = None


@dataclass
class Volume:
    """Represents a persistent volume.

    Volumes are persistent storage that can be mounted in sandboxes.

    Attributes:
        id: Unique identifier (UUID). Remains constant even if name changes.
            May be None for resources created before ID support was added.
        name: Display name (can be updated).
    """

    name: str
    size: str
    storage_class: str
    id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Volume:
        """Create a Volume from API response dict."""
        return cls(
            name=data.get("name", ""),
            size=data.get("size", "unknown"),
            storage_class=data.get("storage_class", "default"),
            id=data.get("id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class VolumeMountSpec:
    """Specification for mounting a volume in a sandbox template."""

    volume_name: str
    mount_path: str


@dataclass
class SandboxTemplate:
    """Represents a SandboxTemplate.

    Templates define the image, resource limits, and volume mounts for sandboxes.
    All other container details are handled by the server with secure defaults.

    Attributes:
        id: Unique identifier (UUID). Remains constant even if name changes.
            May be None for resources created before ID support was added.
        name: Display name (can be updated).
    """

    name: str
    image: str
    resources: ResourceSpec
    volume_mounts: list[VolumeMountSpec] = field(default_factory=list)
    id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SandboxTemplate:
        """Create a SandboxTemplate from API response dict."""
        resources_data = data.get("resources", {})
        volume_mounts_data = data.get("volume_mounts", [])
        return cls(
            name=data.get("name", ""),
            image=data.get("image", "unknown"),
            resources=ResourceSpec(
                cpu=resources_data.get("cpu", "500m"),
                memory=resources_data.get("memory", "512Mi"),
                storage=resources_data.get("storage"),
            ),
            volume_mounts=[
                VolumeMountSpec(
                    volume_name=vm.get("volume_name", ""),
                    mount_path=vm.get("mount_path", ""),
                )
                for vm in volume_mounts_data
            ],
            id=data.get("id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class Pool:
    """Represents a Sandbox Pool for pre-provisioned sandboxes.

    Pools pre-provision sandboxes from a template for faster startup.
    Instead of waiting for a new sandbox to be created, sandboxes can
    be served from a pre-warmed pool.

    Note: Templates with volume mounts cannot be used in pools.

    Attributes:
        id: Unique identifier (UUID). Remains constant even if name changes.
            May be None for resources created before ID support was added.
        name: Display name (can be updated).
    """

    name: str
    template_name: str
    replicas: int  # Desired replicas
    id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Pool:
        """Create a Pool from API response dict."""
        return cls(
            name=data.get("name", ""),
            template_name=data.get("template_name", ""),
            replicas=data.get("replicas", 0),
            id=data.get("id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


# =============================================================================
# WebSocket Command Execution Models
# =============================================================================


@dataclass
class OutputChunk:
    """A single chunk of streaming output from command execution.

    Attributes:
        stream: Either "stdout" or "stderr".
        data: The text content of this chunk (valid UTF-8, server handles
            boundary splitting).
        offset: Byte offset within the stream. Used internally for
            reconnection; users typically don't need this.
    """

    stream: str
    data: str
    offset: int


class CommandHandle:
    """Handle to a running command with streaming output and auto-reconnect.

    Iterable, yielding OutputChunk objects (stdout and stderr interleaved
    in arrival order). Access .result after iteration to get the full
    ExecutionResult.

    Auto-reconnect behavior:
    - Server hot-reload (1001 Going Away): reconnect immediately
    - Network error / unexpected close:    reconnect with exponential backoff
    - User called kill():                  do NOT reconnect (propagate error)

    The auto-reconnect is transparent -- the iterator reconnects and
    continues yielding chunks without any user intervention. If all
    reconnect attempts are exhausted, SandboxConnectionError is raised.

    Construction modes (controlled by ``command_id``):
    - **New execution** (``command_id=""``, the default): the constructor
      eagerly reads the server's ``"started"`` message to populate
      ``command_id`` and ``pid`` before returning.
    - **Reconnection** (``command_id`` set): skips the started-message
      read, since reconnect streams don't emit one.

    Example:
        handle = sandbox.run("make build", timeout=600, wait=False)

        for chunk in handle:          # auto-reconnects on transient errors
            print(chunk.data, end="")

        result = handle.result
        print(f"Exit code: {result.exit_code}")
    """

    MAX_AUTO_RECONNECTS = 5
    _BACKOFF_BASE = 0.5  # seconds
    _BACKOFF_MAX = 8.0  # seconds

    def __init__(
        self,
        message_stream: Iterator[dict],
        control: Optional[_WSStreamControl],
        sandbox: Sandbox,
        *,
        command_id: str = "",
        stdout_offset: int = 0,
        stderr_offset: int = 0,
    ) -> None:
        self._stream = message_stream
        self._control = control
        self._sandbox = sandbox
        self._command_id: Optional[str] = None
        self._pid: Optional[int] = None
        self._result: Optional[ExecutionResult] = None
        self._stdout_parts: list[str] = []
        self._stderr_parts: list[str] = []
        self._exhausted = False
        self._last_stdout_offset = stdout_offset
        self._last_stderr_offset = stderr_offset

        # New executions (command_id=""): eager_start reads "started" message.
        # Reconnections (command_id set): skip eager_start since reconnect
        # streams don't send a "started" message.
        if command_id:
            self._command_id = command_id
        else:
            self._consume_started()

    def _consume_started(self) -> None:
        """Eagerly read the 'started' message to populate command_id and pid.

        Blocks briefly until the server sends the started message (arrives
        near-instantly after connection). After this call, command_id and
        pid are available, and the WebSocket is bound to the control object
        (so kill() works).
        """
        try:
            first_msg = next(self._stream)
        except StopIteration:
            raise SandboxOperationError(
                "Command stream ended before 'started' message",
                operation="command",
            )
        if first_msg.get("type") != "started":
            raise SandboxOperationError(
                f"Expected 'started' message, got '{first_msg.get('type')}'",
                operation="command",
            )
        self._command_id = first_msg.get("command_id")
        self._pid = first_msg.get("pid")

    @property
    def command_id(self) -> Optional[str]:
        """The server-assigned command ID. Available after construction."""
        return self._command_id

    @property
    def pid(self) -> Optional[int]:
        """The process ID on the sandbox. Available after construction."""
        return self._pid

    @property
    def result(self) -> ExecutionResult:
        """The final execution result. Blocks until the command completes.

        Drains the remaining stream if not already exhausted, then returns
        the ExecutionResult with aggregated stdout, stderr, and exit_code.
        """
        if self._result is None:
            for _ in self:
                pass
        if self._result is None:
            raise SandboxOperationError(
                "Command stream ended without exit message",
                operation="command",
            )
        return self._result

    def _iter_stream(self) -> Iterator[OutputChunk]:
        """Iterate over output chunks from the current stream (no reconnect)."""
        if self._exhausted:
            return
        for msg in self._stream:
            msg_type = msg.get("type")
            if msg_type in ("stdout", "stderr"):
                chunk = OutputChunk(
                    stream=msg_type,
                    data=msg["data"],
                    offset=msg.get("offset", 0),
                )
                if msg_type == "stdout":
                    self._stdout_parts.append(msg["data"])
                else:
                    self._stderr_parts.append(msg["data"])
                yield chunk
            elif msg_type == "exit":
                self._result = ExecutionResult(
                    stdout="".join(self._stdout_parts),
                    stderr="".join(self._stderr_parts),
                    exit_code=msg["exit_code"],
                )
                self._exhausted = True
                return
        self._exhausted = True

    def __iter__(self) -> Iterator[OutputChunk]:
        """Iterate over output chunks, auto-reconnecting on transient errors.

        Reconnect strategy:
        - 1001 Going Away (hot-reload): immediate reconnect, no delay
        - Other SandboxConnectionError:  exponential backoff (0.5s, 1s, 2s...)
        - After kill():                  no reconnect, error propagates
        """
        import time

        reconnect_attempts = 0
        while True:
            try:
                for chunk in self._iter_stream():
                    reconnect_attempts = 0  # Reset on successful data
                    if chunk.stream == "stdout":
                        self._last_stdout_offset = chunk.offset + len(
                            chunk.data.encode("utf-8")
                        )
                    else:
                        self._last_stderr_offset = chunk.offset + len(
                            chunk.data.encode("utf-8")
                        )
                    yield chunk
                return  # Stream ended normally (exit message received)

            except SandboxConnectionError as e:
                if self._control and self._control.killed:
                    raise

                reconnect_attempts += 1
                if reconnect_attempts > self.MAX_AUTO_RECONNECTS:
                    raise SandboxConnectionError(
                        f"Lost connection {reconnect_attempts} times in "
                        f"succession, giving up"
                    ) from e

                is_hot_reload = isinstance(e, SandboxServerReloadError)
                if not is_hot_reload:
                    delay = min(
                        self._BACKOFF_BASE * (2 ** (reconnect_attempts - 1)),
                        self._BACKOFF_MAX,
                    )
                    time.sleep(delay)

                assert self._command_id is not None
                new_handle = self._sandbox.reconnect(
                    self._command_id,
                    stdout_offset=self._last_stdout_offset,
                    stderr_offset=self._last_stderr_offset,
                )
                self._stream = new_handle._stream
                self._control = new_handle._control
                self._exhausted = False

    def kill(self) -> None:
        """Send a kill signal to the running command (SIGKILL).

        The server kills the entire process group. The stream will
        subsequently yield an exit message with a non-zero exit code.

        Has no effect if the command has already exited or the
        WebSocket connection is closed.
        """
        if self._control:
            self._control.send_kill()

    def send_input(self, data: str) -> None:
        """Write data to the command's stdin.

        Args:
            data: String data to write to stdin.

        Has no effect if the command has already exited or the
        WebSocket connection is closed.
        """
        if self._control:
            self._control.send_input(data)

    @property
    def last_stdout_offset(self) -> int:
        """Last known stdout byte offset (for manual reconnection)."""
        return self._last_stdout_offset

    @property
    def last_stderr_offset(self) -> int:
        """Last known stderr byte offset (for manual reconnection)."""
        return self._last_stderr_offset

    def reconnect(self) -> CommandHandle:
        """Reconnect to this command from the last known offsets.

        Returns a new handle that resumes output from where this one
        left off. Any output produced while disconnected is replayed
        from the server's ring buffer.

        Returns:
            A new CommandHandle.

        Raises:
            SandboxOperationError: If command_id is not found or
                session expired.
            SandboxConnectionError: If connection to sandbox fails.
        """
        assert self._command_id is not None
        return self._sandbox.reconnect(
            self._command_id,
            stdout_offset=self._last_stdout_offset,
            stderr_offset=self._last_stderr_offset,
        )


class AsyncCommandHandle:
    """Async handle to a running command with streaming output and auto-reconnect.

    Async iterable, yielding OutputChunk objects (stdout and stderr interleaved
    in arrival order). Access .result after iteration to get the full
    ExecutionResult.

    Auto-reconnect behavior:
    - Server hot-reload (1001 Going Away): reconnect immediately
    - Network error / unexpected close:    reconnect with exponential backoff
    - User called kill():                  do NOT reconnect (propagate error)

    Construction modes (controlled by ``command_id``):
    - **New execution** (``command_id=""``, the default): call
      ``await handle._ensure_started()`` after construction to read the
      server's ``"started"`` message and populate ``command_id`` / ``pid``.
    - **Reconnection** (``command_id`` set): skips the started-message
      read, since reconnect streams don't emit one.

    Example:
        handle = await sandbox.run("make build", timeout=600, wait=False)

        async for chunk in handle:    # auto-reconnects on transient errors
            print(chunk.data, end="")

        result = await handle.result
        print(f"Exit code: {result.exit_code}")
    """

    MAX_AUTO_RECONNECTS = 5
    _BACKOFF_BASE = 0.5  # seconds
    _BACKOFF_MAX = 8.0  # seconds

    def __init__(
        self,
        message_stream: AsyncIterator[dict],
        control: Optional[_AsyncWSStreamControl],
        sandbox: AsyncSandbox,
        *,
        command_id: str = "",
        stdout_offset: int = 0,
        stderr_offset: int = 0,
    ) -> None:
        self._stream = message_stream
        self._control = control
        self._sandbox = sandbox
        self._command_id: Optional[str] = None
        self._pid: Optional[int] = None
        self._result: Optional[ExecutionResult] = None
        self._stdout_parts: list[str] = []
        self._stderr_parts: list[str] = []
        self._exhausted = False
        self._last_stdout_offset = stdout_offset
        self._last_stderr_offset = stderr_offset

        # New executions (command_id=""): _ensure_started reads "started".
        # Reconnections (command_id set): skip since reconnect streams
        # don't send a "started" message.
        if command_id:
            self._command_id = command_id
            self._started = True
        else:
            self._started = False

    async def _ensure_started(self) -> None:
        """Read the 'started' message to populate command_id and pid."""
        if self._started:
            return
        try:
            first_msg = await self._stream.__anext__()
        except StopAsyncIteration:
            raise SandboxOperationError(
                "Command stream ended before 'started' message",
                operation="command",
            )
        if first_msg.get("type") != "started":
            raise SandboxOperationError(
                f"Expected 'started' message, got '{first_msg.get('type')}'",
                operation="command",
            )
        self._command_id = first_msg.get("command_id")
        self._pid = first_msg.get("pid")
        self._started = True

    @property
    def command_id(self) -> Optional[str]:
        """The server-assigned command ID. Available after _ensure_started."""
        return self._command_id

    @property
    def pid(self) -> Optional[int]:
        """The process ID on the sandbox. Available after _ensure_started."""
        return self._pid

    @property
    async def result(self) -> ExecutionResult:
        """The final execution result. Awaitable."""
        if self._result is None:
            async for _ in self:
                pass
        if self._result is None:
            raise SandboxOperationError(
                "Command stream ended without exit message",
                operation="command",
            )
        return self._result

    async def _aiter_stream(self) -> AsyncIterator[OutputChunk]:
        """Iterate over output chunks from the current stream (no reconnect)."""
        await self._ensure_started()
        if self._exhausted:
            return
        async for msg in self._stream:
            msg_type = msg.get("type")
            if msg_type in ("stdout", "stderr"):
                chunk = OutputChunk(
                    stream=msg_type,
                    data=msg["data"],
                    offset=msg.get("offset", 0),
                )
                if msg_type == "stdout":
                    self._stdout_parts.append(msg["data"])
                else:
                    self._stderr_parts.append(msg["data"])
                yield chunk
            elif msg_type == "exit":
                self._result = ExecutionResult(
                    stdout="".join(self._stdout_parts),
                    stderr="".join(self._stderr_parts),
                    exit_code=msg["exit_code"],
                )
                self._exhausted = True
                return
        self._exhausted = True

    async def __aiter__(self) -> AsyncIterator[OutputChunk]:
        """Async iterate with auto-reconnect on transient errors."""
        import asyncio

        reconnect_attempts = 0
        while True:
            try:
                async for chunk in self._aiter_stream():
                    reconnect_attempts = 0
                    if chunk.stream == "stdout":
                        self._last_stdout_offset = chunk.offset + len(
                            chunk.data.encode("utf-8")
                        )
                    else:
                        self._last_stderr_offset = chunk.offset + len(
                            chunk.data.encode("utf-8")
                        )
                    yield chunk
                return  # Stream ended normally

            except SandboxConnectionError as e:
                if self._control and self._control.killed:
                    raise

                reconnect_attempts += 1
                if reconnect_attempts > self.MAX_AUTO_RECONNECTS:
                    raise SandboxConnectionError(
                        f"Lost connection {reconnect_attempts} times "
                        f"in succession, giving up"
                    ) from e

                is_hot_reload = isinstance(e, SandboxServerReloadError)
                if not is_hot_reload:
                    delay = min(
                        self._BACKOFF_BASE * (2 ** (reconnect_attempts - 1)),
                        self._BACKOFF_MAX,
                    )
                    await asyncio.sleep(delay)

                assert self._command_id is not None
                new_handle = await self._sandbox.reconnect(
                    self._command_id,
                    stdout_offset=self._last_stdout_offset,
                    stderr_offset=self._last_stderr_offset,
                )
                self._stream = new_handle._stream
                self._control = new_handle._control
                self._exhausted = False

    async def kill(self) -> None:
        """Send a kill signal to the running command."""
        if self._control:
            await self._control.send_kill()

    async def send_input(self, data: str) -> None:
        """Write data to the command's stdin."""
        if self._control:
            await self._control.send_input(data)

    @property
    def last_stdout_offset(self) -> int:
        """Last known stdout byte offset (for manual reconnection)."""
        return self._last_stdout_offset

    @property
    def last_stderr_offset(self) -> int:
        """Last known stderr byte offset (for manual reconnection)."""
        return self._last_stderr_offset

    async def reconnect(self) -> AsyncCommandHandle:
        """Reconnect to this command from the last known offsets."""
        assert self._command_id is not None
        return await self._sandbox.reconnect(
            self._command_id,
            stdout_offset=self._last_stdout_offset,
            stderr_offset=self._last_stderr_offset,
        )
