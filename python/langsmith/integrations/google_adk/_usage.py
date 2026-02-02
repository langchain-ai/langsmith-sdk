"""Token usage utilities for Google ADK."""

from typing import Any


def extract_usage_from_response(llm_response: Any) -> dict[str, Any]:
    """Extract token usage from Google ADK LlmResponse.

    Args:
        llm_response: The LlmResponse object from Google ADK.

    Returns:
        A dictionary with normalized usage metrics compatible with LangSmith.
    """
    usage: dict[str, Any] = {}

    usage_metadata = getattr(llm_response, "usage_metadata", None)
    if not usage_metadata:
        return usage

    def to_int(value: Any) -> int | None:
        try:
            return int(value) if value is not None else None
        except (ValueError, TypeError):
            return None

    # Map Google's attribute names to LangSmith standard
    prompt_tokens = to_int(getattr(usage_metadata, "prompt_token_count", None))
    if prompt_tokens is not None:
        usage["input_tokens"] = prompt_tokens

    candidates_tokens = to_int(getattr(usage_metadata, "candidates_token_count", None))
    if candidates_tokens is not None:
        usage["output_tokens"] = candidates_tokens

    total_tokens = to_int(getattr(usage_metadata, "total_token_count", None))
    if total_tokens is not None:
        usage["total_tokens"] = total_tokens

    # Cached tokens (input token details)
    cached_tokens = to_int(getattr(usage_metadata, "cached_content_token_count", None))
    if cached_tokens is not None:
        usage.setdefault("input_token_details", {})["cache_read"] = cached_tokens

    # Reasoning tokens for thinking models (output token details)
    thoughts_tokens = to_int(getattr(usage_metadata, "thoughts_token_count", None))
    if thoughts_tokens is not None:
        usage.setdefault("output_token_details", {})["reasoning"] = thoughts_tokens

    return usage


def extract_model_name(llm_request: Any) -> str | None:
    """Extract the model name from an LlmRequest.

    Args:
        llm_request: The LlmRequest object from Google ADK.

    Returns:
        The model name if available, None otherwise.
    """
    # Try to get model from the request's config
    config = getattr(llm_request, "config", None)
    if config:
        model = getattr(config, "model", None)
        if model:
            return str(model)

    # Fallback to model attribute directly
    model = getattr(llm_request, "model", None)
    if model:
        return str(model)

    return None
