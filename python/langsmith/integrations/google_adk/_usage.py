"""Token usage extraction for Google ADK."""

from __future__ import annotations

from typing import Any, Optional


def extract_usage_from_response(llm_response: Any) -> dict[str, Any]:
    """Extract token usage from LlmResponse."""
    usage: dict[str, Any] = {}
    usage_metadata = getattr(llm_response, "usage_metadata", None)
    if not usage_metadata:
        return usage

    if (v := getattr(usage_metadata, "prompt_token_count", None)) is not None:
        usage["input_tokens"] = int(v)
    if (v := getattr(usage_metadata, "candidates_token_count", None)) is not None:
        usage["output_tokens"] = int(v)
    if (v := getattr(usage_metadata, "total_token_count", None)) is not None:
        usage["total_tokens"] = int(v)
    if (v := getattr(usage_metadata, "cached_content_token_count", None)) is not None:
        usage.setdefault("input_token_details", {})["cache_read"] = int(v)
    if (v := getattr(usage_metadata, "thoughts_token_count", None)) is not None:
        usage.setdefault("output_token_details", {})["reasoning"] = int(v)

    return usage


def extract_model_name(llm_request: Any) -> Optional[str]:
    """Extract the model name from an LlmRequest."""
    if config := getattr(llm_request, "config", None):
        if model := getattr(config, "model", None):
            return str(model)
    if model := getattr(llm_request, "model", None):
        return str(model)
    return None
