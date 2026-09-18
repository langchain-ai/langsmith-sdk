"""Server-Sent Events command execution, over plain HTTP.

``POST /execute/stream/start`` runs a command and streams its stdout/stderr as
SSE events carrying base64 payloads; ``POST /execute/stream/resume`` continues
one. The transport is one-way, so a client cannot ack buffered output mid-stream
the way the exec WebSocket does: the server instead ends the response with an
``ack_required`` event the moment its bounded output buffer needs room, and the
offsets on the next resume are both the ack and the cursor to continue from.

This module drives that loop and yields the same message dicts
:class:`~langsmith.sandbox._models.CommandHandle` already consumes from the
WebSocket transport, so a resume is invisible to the caller.
"""

from __future__ import annotations

import asyncio
import base64
import codecs
import json
import logging
import random
import time
from collections.abc import AsyncIterator, Iterator, Mapping
from typing import Any, Optional

from langsmith import _features
from langsmith import utils as ls_utils
from langsmith._openapi_client._httpx import httpx
from langsmith.sandbox._exceptions import (
    SandboxConnectionError,
    SandboxOperationError,
)
from langsmith.sandbox._helpers import handle_sandbox_http_error
from langsmith.sandbox._ws_execute import _raise_from_error_msg

logger = logging.getLogger(__name__)

# Named in every error raised for something SSE cannot do, so the message says
# how the caller got onto this transport.
_FEATURE = _features.SANDBOX_SSE_EXEC
_TURN_OFF = _features.setting_hint(_FEATURE, on=False)
_TURN_ON = _features.setting_hint(_FEATURE)

_START_PATH = "/execute/stream/start"
_RESUME_PATH = "/execute/stream/resume"

_STDOUT = "stdout"
_STDERR = "stderr"

# Bounds the wait for the next event. The server heartbeats every 15s, so this
# is several missed beats rather than a guess at how long a command runs.
_READ_TIMEOUT_DEFAULT = 60.0

# A resume that follows a broken connection is retried on this budget. An
# ack_required resume is the protocol working as designed and does not spend it.
_MAX_RESUME_ATTEMPTS = 5
_BACKOFF_BASE = 0.5
_BACKOFF_MAX = 8.0

_NO_CONTROL_CHANNEL = (
    "The SSE exec transport is one-way, so a running command cannot be sent "
    f"input or signals. Set {_TURN_OFF} to use the exec WebSocket, which has a "
    "control channel."
)


def sse_transport_selected() -> bool:
    """Whether the SSE exec feature is on."""
    return _features.enabled(_FEATURE)


MISSING_TRANSPORT_MSG = (
    "Running a sandbox command needs a transport. Either install the WebSocket "
    "client with `pip install 'langsmith[sandbox]'`, or set "
    f"{_TURN_ON} to stream commands over Server-Sent Events instead -- a "
    "one-way transport, so it cannot send input or signals to a running "
    "command and does not support a PTY."
)


def require_sse_supports(
    *, pty: bool, close_stdin: bool, kill_on_disconnect: bool
) -> None:
    """Reject run() options that need the WebSocket's control channel."""
    if pty:
        raise ValueError(
            "pty=True needs the exec WebSocket, which carries a terminal's "
            f"merged stream and its input; set {_TURN_OFF}."
        )
    if not close_stdin:
        raise ValueError(
            "close_input=False needs the exec WebSocket, which can write stdin "
            f"to a running command; set {_TURN_OFF}. Over SSE stdin is written "
            "once when the command spawns, then closed."
        )
    if kill_on_disconnect:
        raise ValueError(
            "kill_on_disconnect=True needs the exec WebSocket, where the "
            f"connection lasts as long as the command; set {_TURN_OFF}. An SSE "
            "stream ends and resumes whenever the server needs an ack."
        )


def read_timeout() -> Optional[float]:
    """Per-event read timeout, in seconds. ``<= 0`` disables it."""
    raw = ls_utils.get_env_var("SANDBOX_SSE_TIMEOUT_READ")
    if raw is None:
        return _READ_TIMEOUT_DEFAULT
    try:
        value = float(raw)
    except ValueError:
        logger.warning(
            "Ignoring invalid LANGSMITH_SANDBOX_SSE_TIMEOUT_READ=%r, using %s",
            raw,
            _READ_TIMEOUT_DEFAULT,
        )
        return _READ_TIMEOUT_DEFAULT
    return value if value > 0 else None


def start_payload(
    command: str,
    *,
    command_id: str,
    timeout: int,
    shell: str,
    idle_timeout: int,
    ttl_seconds: int,
    env: Optional[dict[str, str]] = None,
    cwd: Optional[str] = None,
    run_config: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build the body for ``/execute/stream/start``."""
    payload: dict[str, Any] = {
        "command": command,
        "command_id": command_id,
        "shell": shell,
        "timeout_seconds": timeout,
        "idle_timeout_seconds": idle_timeout,
        "ttl_seconds": ttl_seconds,
    }
    if env:
        payload["env"] = env
    if cwd:
        payload["cwd"] = cwd
    if run_config is not None:
        payload["run_config"] = run_config
    return payload


class _SSEStreamControl:
    """Stand-in for the WebSocket control channel, which SSE does not have.

    ``CommandHandle`` reads ``killed`` to decide whether a broken stream should
    reattach, and forwards user calls here. Everything that needs to reach a
    running command raises instead of failing silently.
    """

    @property
    def killed(self) -> bool:
        return False

    @property
    def resumes_itself(self) -> bool:
        return True

    def send_kill(self) -> None:
        raise SandboxOperationError(_NO_CONTROL_CHANNEL, operation="kill")

    def send_input(self, data: str) -> None:
        raise SandboxOperationError(_NO_CONTROL_CHANNEL, operation="send_input")

    def send_close_stdin(self) -> None:
        """No-op: this transport closes stdin when the command is spawned."""


class _AsyncSSEStreamControl:
    """Async equivalent of :class:`_SSEStreamControl`."""

    @property
    def killed(self) -> bool:
        return False

    @property
    def resumes_itself(self) -> bool:
        return True

    async def send_kill(self) -> None:
        raise SandboxOperationError(_NO_CONTROL_CHANNEL, operation="kill")

    async def send_input(self, data: str) -> None:
        raise SandboxOperationError(_NO_CONTROL_CHANNEL, operation="send_input")

    async def send_close_stdin(self) -> None:
        """No-op: this transport closes stdin when the command is spawned."""


class _Resume(Exception):
    """Internal signal to continue the command on a new request.

    A zero ``delay`` is the protocol's own ack round trip; ``None`` means the
    stream broke and the retry budget applies.
    """

    def __init__(
        self,
        stdout_offset: int,
        stderr_offset: int,
        *,
        delay: Optional[float],
        reason: str = "ack required",
    ) -> None:
        super().__init__(reason)
        self.stdout_offset = stdout_offset
        self.stderr_offset = stderr_offset
        self.delay = delay


def _is_truncated_utf8(tail: bytes) -> bool:
    """Whether ``tail`` is a valid UTF-8 prefix awaiting more bytes."""
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        decoder.decode(tail)
    except UnicodeDecodeError:
        return False
    return True


def _split_utf8(buf: bytes) -> tuple[str, bytes]:
    """Split into decodable text and a trailing partial character.

    Output arrives as raw bytes, so a chunk boundary can fall inside a
    multi-byte character. Holding the remainder back until its continuation
    bytes arrive keeps both the text and the byte offsets exact.
    """
    try:
        return buf.decode("utf-8"), b""
    except UnicodeDecodeError as exc:
        tail = buf[exc.start :]
        if len(tail) < 4 and _is_truncated_utf8(tail):
            return buf[: exc.start].decode("utf-8"), tail
        return buf.decode("utf-8", errors="replace"), b""


class _ChunkDecoder:
    """Decodes one stream's chunks, carrying a split character across them."""

    def __init__(self) -> None:
        self._pending = b""
        self._pending_offset = 0

    def feed(self, offset: int, data: bytes) -> Optional[tuple[int, str]]:
        """Return the offset and text to emit, or None while nothing decodes."""
        if self._pending:
            start = self._pending_offset
            buf = self._pending + data
        else:
            start = offset
            buf = data
        text, self._pending = _split_utf8(buf)
        self._pending_offset = start + len(buf) - len(self._pending)
        return (start, text) if text else None

    def flush(self) -> Optional[tuple[int, str]]:
        """Emit a character left incomplete by the stream ending, as U+FFFD.

        Held-back bytes are waiting for a continuation that a finished stream
        will never send, so they become a replacement character rather than
        vanishing. Idempotent, which matters because the server repeats
        ``stream_end`` to a client that resumes at the stream's final offset.
        """
        if not self._pending:
            return None
        pending, start = self._pending, self._pending_offset
        self._pending = b""
        self._pending_offset = start + len(pending)
        return start, pending.decode("utf-8", errors="replace")


class _EventPump:
    """Turns SSE events into the message dicts CommandHandle consumes.

    Also holds the cursors, which the caller sends back to resume and ack.
    """

    def __init__(
        self,
        *,
        command_id: str = "",
        stdout_offset: int = 0,
        stderr_offset: int = 0,
    ) -> None:
        self.command_id = command_id
        self.offsets = {_STDOUT: stdout_offset, _STDERR: stderr_offset}
        self.started = False
        self.exited = False
        self._decoders = {_STDOUT: _ChunkDecoder(), _STDERR: _ChunkDecoder()}

    def feed(self, event: str, raw: str) -> Iterator[dict]:
        """Yield the messages for one event, or raise to resume or fail."""
        try:
            payload = json.loads(raw) if raw else {}
        except ValueError:
            logger.debug("Ignoring exec stream event %r with unparsable data", event)
            return

        if event == "started":
            self.started = True
            self.command_id = payload.get("command_id") or self.command_id
            yield {
                "type": "started",
                "command_id": self.command_id,
                "pid": payload.get("pid"),
            }
        elif event in (_STDOUT, _STDERR):
            offset = int(payload.get("offset") or 0)
            data = base64.b64decode(payload.get("data") or "")
            self.offsets[event] = offset + len(data)
            decoded = self._decoders[event].feed(offset, data)
            if decoded is not None:
                at, text = decoded
                yield {"type": event, "data": text, "offset": at}
        elif event == "stream_end":
            stream = payload.get("stream")
            if stream in self.offsets:
                end = int(payload.get("offset") or 0)
                self.offsets[stream] = max(self.offsets[stream], end)
                yield from self._flush(stream)
        elif event == "exit":
            # Also flushed here because exit is what ends the command; a stream
            # whose end marker never arrived must not swallow its last bytes.
            yield from self._flush(_STDOUT)
            yield from self._flush(_STDERR)
            self.exited = True
            yield {"type": "exit", "exit_code": int(payload.get("exit_code", -1))}
        elif event == "ack_required":
            raise _Resume(
                int(payload.get("stdout_offset") or 0),
                int(payload.get("stderr_offset") or 0),
                delay=0.0,
            )
        elif event == "error":
            self._fail(payload)

    def _flush(self, stream: str) -> Iterator[dict]:
        flushed = self._decoders[stream].flush()
        if flushed is not None:
            at, text = flushed
            yield {"type": stream, "data": text, "offset": at}

    def _fail(self, payload: dict) -> None:
        if payload.get("error_type") == "ServerShuttingDown":
            raise _Resume(
                self.offsets[_STDOUT],
                self.offsets[_STDERR],
                delay=None,
                reason=payload.get("error", "the sandbox daemon is shutting down"),
            )
        _raise_from_error_msg(payload, command_id=self.command_id)

    def resume_payload(self) -> dict[str, Any]:
        """Build the body for ``/execute/stream/resume`` at the current cursors."""
        return {
            "command_id": self.command_id,
            "stdout_offset": self.offsets[_STDOUT],
            "stderr_offset": self.offsets[_STDERR],
        }


def _iter_sse(lines: Iterator[str]) -> Iterator[tuple[str, str]]:
    """Yield ``(event, data)`` pairs, skipping heartbeat comments."""
    event = ""
    data: list[str] = []
    for line in lines:
        if not line:
            if event:
                yield event, "\n".join(data)
            event, data = "", []
            continue
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        if value.startswith(" "):
            value = value[1:]
        if field == "event":
            event = value
        elif field == "data":
            data.append(value)
    if event:
        yield event, "\n".join(data)


async def _aiter_sse(lines: AsyncIterator[str]) -> AsyncIterator[tuple[str, str]]:
    """Async equivalent of :func:`_iter_sse`."""
    event = ""
    data: list[str] = []
    async for line in lines:
        if not line:
            if event:
                yield event, "\n".join(data)
            event, data = "", []
            continue
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        if value.startswith(" "):
            value = value[1:]
        if field == "event":
            event = value
        elif field == "data":
            data.append(value)
    if event:
        yield event, "\n".join(data)


# Transport faults that a resume can recover from, because the command keeps
# running on the sandbox independently of this request.
_RECOVERABLE = (
    httpx.ReadTimeout,
    httpx.ReadError,
    httpx.RemoteProtocolError,
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.WriteError,
    SandboxConnectionError,
)


def _check_status(response: httpx.Response, *, command_id: str, resuming: bool) -> None:
    """Raise for a non-streaming response, before any event is read."""
    if response.status_code < 400:
        return
    response.read()
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if resuming and response.status_code == 404:
            raise SandboxOperationError(
                f"Command not found: {command_id}",
                operation="reconnect",
                error_type="CommandNotFound",
            ) from exc
        handle_sandbox_http_error(exc)
        raise  # pragma: no cover


async def _acheck_status(
    response: httpx.Response, *, command_id: str, resuming: bool
) -> None:
    """Async equivalent of :func:`_check_status`."""
    if response.status_code < 400:
        return
    await response.aread()
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if resuming and response.status_code == 404:
            raise SandboxOperationError(
                f"Command not found: {command_id}",
                operation="reconnect",
                error_type="CommandNotFound",
            ) from exc
        handle_sandbox_http_error(exc)
        raise  # pragma: no cover


def _resume_delay(attempt: int) -> float:
    backoff = min(_BACKOFF_BASE * (2 ** (attempt - 1)), _BACKOFF_MAX)
    return random.uniform(backoff * 0.8, backoff)


def _exhausted(attempt: int, reason: object) -> SandboxConnectionError:
    return SandboxConnectionError(
        f"Failed to resume the exec stream {attempt} times in succession, "
        f"giving up: {reason}"
    )


def _stream_kwargs(
    payload: dict[str, Any], headers: Optional[Mapping[str, str]]
) -> dict[str, Any]:
    timeout = httpx.Timeout(read_timeout(), connect=30.0)
    kwargs: dict[str, Any] = {"json": payload, "timeout": timeout}
    if headers:
        kwargs["headers"] = dict(headers)
    return kwargs


def run_sse_stream(
    http: httpx.Client,
    dataplane_url: str,
    payload: dict[str, Any],
    *,
    headers: Optional[Mapping[str, str]] = None,
) -> tuple[Iterator[dict], _SSEStreamControl]:
    """Start a command over SSE, yielding WebSocket-shaped message dicts.

    Returns ``(messages, control)``. The iterator transparently re-requests the
    stream whenever the server asks for an ack or the connection breaks, so the
    caller sees one continuous run ending in an ``exit`` message.
    """
    pump = _EventPump(command_id=payload.get("command_id", ""))
    return (
        _sse_messages(http, dataplane_url, pump, payload, headers),
        _SSEStreamControl(),
    )


def resume_sse_stream(
    http: httpx.Client,
    dataplane_url: str,
    command_id: str,
    *,
    stdout_offset: int = 0,
    stderr_offset: int = 0,
    headers: Optional[Mapping[str, str]] = None,
) -> tuple[Iterator[dict], _SSEStreamControl]:
    """Reattach to a command started earlier, resuming from the given offsets."""
    pump = _EventPump(
        command_id=command_id,
        stdout_offset=stdout_offset,
        stderr_offset=stderr_offset,
    )
    pump.started = True
    return (
        _sse_messages(http, dataplane_url, pump, None, headers),
        _SSEStreamControl(),
    )


def _sse_messages(
    http: httpx.Client,
    dataplane_url: str,
    pump: _EventPump,
    start_body: Optional[dict[str, Any]],
    headers: Optional[Mapping[str, str]],
) -> Iterator[dict]:
    attempt = 0
    while True:
        # Before "started" there may be no command to attach to, so a retry
        # re-sends the start body; its command_id keeps that from running twice.
        resuming = pump.started or start_body is None
        url = dataplane_url + (_RESUME_PATH if resuming else _START_PATH)
        body = pump.resume_payload() if resuming else start_body
        assert body is not None
        # Only output clears the retry budget. Every resumed response opens with
        # "started", so crediting that would let a stream that delivers nothing
        # else retry forever.
        cursors = dict(pump.offsets)

        try:
            with http.stream("POST", url, **_stream_kwargs(body, headers)) as response:
                _check_status(response, command_id=pump.command_id, resuming=resuming)
                for event, raw in _iter_sse(response.iter_lines()):
                    for message in pump.feed(event, raw):
                        if pump.offsets != cursors:
                            attempt = 0
                        yield message
                    if pump.exited:
                        return
        except _Resume as resume:
            pump.offsets[_STDOUT] = resume.stdout_offset
            pump.offsets[_STDERR] = resume.stderr_offset
            if resume.delay is None:
                attempt += 1
                if attempt > _MAX_RESUME_ATTEMPTS:
                    raise _exhausted(attempt, resume) from resume
                time.sleep(_resume_delay(attempt))
            continue
        except _RECOVERABLE as exc:
            attempt += 1
            if attempt > _MAX_RESUME_ATTEMPTS:
                raise _exhausted(attempt, exc) from exc
            logger.debug(
                "exec stream broke, resuming from %s (attempt %d): %s",
                pump.offsets,
                attempt,
                exc,
            )
            time.sleep(_resume_delay(attempt))
            continue

        # The response ended without a terminal event, which a resume from the
        # current cursors recovers from the same way a broken connection does.
        attempt += 1
        if attempt > _MAX_RESUME_ATTEMPTS:
            raise SandboxConnectionError(
                "Command stream ended without an exit or ack_required event"
            )
        time.sleep(_resume_delay(attempt))


async def run_sse_stream_async(
    http: httpx.AsyncClient,
    dataplane_url: str,
    payload: dict[str, Any],
    *,
    headers: Optional[Mapping[str, str]] = None,
) -> tuple[AsyncIterator[dict], _AsyncSSEStreamControl]:
    """Async equivalent of :func:`run_sse_stream`."""
    pump = _EventPump(command_id=payload.get("command_id", ""))
    return (
        _asse_messages(http, dataplane_url, pump, payload, headers),
        _AsyncSSEStreamControl(),
    )


async def resume_sse_stream_async(
    http: httpx.AsyncClient,
    dataplane_url: str,
    command_id: str,
    *,
    stdout_offset: int = 0,
    stderr_offset: int = 0,
    headers: Optional[Mapping[str, str]] = None,
) -> tuple[AsyncIterator[dict], _AsyncSSEStreamControl]:
    """Async equivalent of :func:`resume_sse_stream`."""
    pump = _EventPump(
        command_id=command_id,
        stdout_offset=stdout_offset,
        stderr_offset=stderr_offset,
    )
    pump.started = True
    return (
        _asse_messages(http, dataplane_url, pump, None, headers),
        _AsyncSSEStreamControl(),
    )


async def _asse_messages(
    http: httpx.AsyncClient,
    dataplane_url: str,
    pump: _EventPump,
    start_body: Optional[dict[str, Any]],
    headers: Optional[Mapping[str, str]],
) -> AsyncIterator[dict]:
    attempt = 0
    while True:
        resuming = pump.started or start_body is None
        url = dataplane_url + (_RESUME_PATH if resuming else _START_PATH)
        body = pump.resume_payload() if resuming else start_body
        assert body is not None
        cursors = dict(pump.offsets)

        try:
            async with http.stream(
                "POST", url, **_stream_kwargs(body, headers)
            ) as response:
                await _acheck_status(
                    response, command_id=pump.command_id, resuming=resuming
                )
                async for event, raw in _aiter_sse(response.aiter_lines()):
                    for message in pump.feed(event, raw):
                        if pump.offsets != cursors:
                            attempt = 0
                        yield message
                    if pump.exited:
                        return
        except _Resume as resume:
            pump.offsets[_STDOUT] = resume.stdout_offset
            pump.offsets[_STDERR] = resume.stderr_offset
            if resume.delay is None:
                attempt += 1
                if attempt > _MAX_RESUME_ATTEMPTS:
                    raise _exhausted(attempt, resume) from resume
                await asyncio.sleep(_resume_delay(attempt))
            continue
        except _RECOVERABLE as exc:
            attempt += 1
            if attempt > _MAX_RESUME_ATTEMPTS:
                raise _exhausted(attempt, exc) from exc
            logger.debug(
                "exec stream broke, resuming from %s (attempt %d): %s",
                pump.offsets,
                attempt,
                exc,
            )
            await asyncio.sleep(_resume_delay(attempt))
            continue

        attempt += 1
        if attempt > _MAX_RESUME_ATTEMPTS:
            raise SandboxConnectionError(
                "Command stream ended without an exit or ack_required event"
            )
        await asyncio.sleep(_resume_delay(attempt))
