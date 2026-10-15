"""Helpers for building SSE exec-stream response bodies in tests."""

import base64
import json

SSE_HEADERS = {"content-type": "text/event-stream"}


def sse_bytes(*events: tuple[str, object]) -> bytes:
    """Render events the way the daemon does, with a heartbeat comment mixed in."""
    body = ": ping\n\n"
    for name, payload in events:
        body += f"event: {name}\ndata: {json.dumps(payload)}\n\n"
    return body.encode()


def out(offset: int, data: bytes) -> dict:
    """An stdout/stderr payload, with its bytes base64 as on the wire."""
    return {"offset": offset, "data": base64.b64encode(data).decode()}


def started(command_id: str = "cmd-1", pid: int = 42) -> tuple[str, object]:
    return "started", {"command_id": command_id, "pid": pid, "stdin_received": 0}


def exited(exit_code: int = 0) -> tuple[str, object]:
    return "exit", {"exit_code": exit_code}
