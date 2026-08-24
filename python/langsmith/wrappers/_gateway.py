"""Helpers for attaching LLM Gateway response metadata to traced provider runs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import httpx

from langsmith import run_helpers
from langsmith.run_trees import RunTree

_GATEWAY_METADATA_HEADER = "x-langsmith-gateway-metadata"
_HOOK_MARKER = "_langsmith_gateway_metadata_hook_installed"


def add_gateway_response_metadata(
    headers_or_response: Any,
    *,
    run_tree: RunTree | None = None,
) -> None:
    """Best-effort parse and merge of gateway metadata into the active LLM run."""
    try:
        headers = getattr(headers_or_response, "headers", headers_or_response)
        if not isinstance(headers, Mapping) and not hasattr(headers, "get"):
            sdk_response = getattr(headers_or_response, "sdk_http_response", None)
            headers = getattr(sdk_response, "headers", None)
        if headers is None or not hasattr(headers, "get"):
            return

        if isinstance(headers, Mapping):
            raw_metadata = next(
                (
                    value
                    for key, value in headers.items()
                    if str(key).lower() == _GATEWAY_METADATA_HEADER
                ),
                None,
            )
        else:
            raw_metadata = headers.get(_GATEWAY_METADATA_HEADER)
        if not isinstance(raw_metadata, str):
            return

        gateway_metadata = json.loads(raw_metadata)
        if not isinstance(gateway_metadata, dict):
            return

        run = run_tree or run_helpers.get_current_run_tree()
        if run is None or (run_tree is None and run.run_type != "llm"):
            return
        run.add_metadata({"ls_gateway_info": gateway_metadata})
    except Exception:
        # Response diagnostics must never alter provider-call behavior.
        return


def install_gateway_response_hook(client: Any) -> None:
    """Best-effort install of one httpx response hook on an SDK client."""
    try:
        http_client = getattr(client, "_client", None)
        event_hooks = getattr(http_client, "event_hooks", None)
        if not isinstance(event_hooks, dict) or getattr(
            http_client, _HOOK_MARKER, False
        ):
            return

        hooks = event_hooks.setdefault("response", [])
        if isinstance(http_client, httpx.AsyncClient):

            async def capture_async(response: Any) -> None:
                add_gateway_response_metadata(response)

            hooks.append(capture_async)
        else:

            def capture(response: Any) -> None:
                add_gateway_response_metadata(response)

            hooks.append(capture)
        setattr(http_client, _HOOK_MARKER, True)
    except Exception:
        # Custom transports may expose immutable or unusual hook collections.
        return
