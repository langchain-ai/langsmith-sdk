"""Common test utilities for unit tests."""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Iterator
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List

import pytest


class HttpEndpoint:
    def __init__(self) -> None:
        self.count = 0
        self.status: int = HTTPStatus.OK
        self.retry_after: int | None = None
        self.url = ""
        self.responses: dict[str, tuple[str, bytes]] = {}
        self.requests: list[tuple[str, str, bytes]] = []


@pytest.fixture
def endpoint() -> Iterator[HttpEndpoint]:
    ep = HttpEndpoint()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self) -> None:  # noqa: N802
            # Drain the body first, otherwise the client sees a reset rather
            # than the status code we are trying to exercise.
            request_body = b""
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                request_body = self.rfile.read(length)
            elif self.headers.get("Transfer-Encoding") == "chunked":
                while True:
                    size = int(self.rfile.readline().strip() or b"0", 16)
                    request_body += self.rfile.read(size)
                    self.rfile.read(2)
                    if size == 0:
                        break
            ep.count += 1
            ep.requests.append((self.command, self.path, request_body))
            content_type, body = ep.responses.get(
                self.path, ("application/json", b"{}")
            )
            self.send_response(ep.status)
            if ep.retry_after is not None:
                self.send_header("Retry-After", str(ep.retry_after))
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_PATCH = do_POST

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(
        server_address=("127.0.0.1", 0), RequestHandlerClass=Handler
    )
    # The default 0.5s polling interval would dominate fixture teardown.
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.001}, daemon=True
    )
    thread.start()
    ep.url = f"http://127.0.0.1:{server.server_port}"
    try:
        yield ep
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def parse_multipart_data(data: bytes) -> Dict[str, Any]:
    """Parse multipart form data into a batch-like dict structure.

    Returns a dict with "post" and "patch" keys containing lists of runs,
    similar to the batch endpoint format.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")

    result: Dict[str, List[Dict[str, Any]]] = {"post": [], "patch": []}

    # Extract boundary from content type or detect from data
    boundary_match = re.search(rb"--([^\r\n]+)", data)
    if not boundary_match:
        return result

    boundary = boundary_match.group(1)

    # Split by boundary
    parts = data.split(b"--" + boundary)

    # Track runs by ID to merge main payload with field parts
    runs: Dict[str, Dict[str, Any]] = {}
    run_methods: Dict[str, str] = {}  # track whether post or patch

    for part in parts:
        if not part or part.strip() in (b"", b"--", b"--\r\n"):
            continue

        # Parse headers and body
        try:
            if b"\r\n\r\n" in part:
                headers_section, body = part.split(b"\r\n\r\n", 1)
            else:
                continue

            # Remove trailing boundary markers
            body = body.rstrip(b"\r\n")

            # Extract name from Content-Disposition
            name_match = re.search(rb'name="([^"]+)"', headers_section)
            if not name_match:
                continue

            name = name_match.group(1).decode("utf-8")

            # Parse the name: format is "method.run_id" or "method.run_id.field"
            name_parts = name.split(".")

            if len(name_parts) >= 2:
                method = name_parts[0]  # "post" or "patch"
                run_id = name_parts[1]

                if method not in ("post", "patch"):
                    continue

                # Initialize run dict if needed
                if run_id not in runs:
                    runs[run_id] = {}
                    run_methods[run_id] = method

                if len(name_parts) == 2:
                    # Main payload: method.run_id
                    try:
                        run_data = json.loads(body)
                        runs[run_id].update(run_data)
                    except json.JSONDecodeError:
                        pass
                elif len(name_parts) == 3:
                    # Field payload: method.run_id.field
                    field = name_parts[2]
                    try:
                        field_data = json.loads(body)
                        runs[run_id][field] = field_data
                    except json.JSONDecodeError:
                        pass

        except Exception:
            continue

    # Organize into post/patch lists
    for run_id, run_data in runs.items():
        method = run_methods.get(run_id, "post")
        result[method].append(run_data)

    return result


def parse_request_data(data: bytes, content_type: str = "") -> Dict[str, Any]:
    """Parse request data, handling both JSON and multipart formats.

    This function automatically detects the format based on content type
    or data structure.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")

    # Try JSON first
    if "multipart" not in content_type.lower():
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            pass

    # Try multipart
    if data.startswith(b"--"):
        return parse_multipart_data(data)

    # Fallback to JSON
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return {"post": [], "patch": []}
