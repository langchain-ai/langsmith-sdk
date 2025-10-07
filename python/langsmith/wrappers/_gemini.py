from __future__ import annotations

import functools
import logging
import warnings
from collections.abc import Mapping
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Optional,
    TypeVar,
    Union,
)

from typing_extensions import TypedDict

from langsmith import client as ls_client
from langsmith import run_helpers
from langsmith.schemas import InputTokenDetails, OutputTokenDetails, UsageMetadata

if TYPE_CHECKING:
    from google import genai
    from google.genai.types import GenerateContentResponse

C = TypeVar("C", bound=Union["genai.Client", Any])
logger = logging.getLogger(__name__)


def _strip_none(d: dict) -> dict:
    """Remove None values from dictionary."""
    return {k: v for k, v in d.items() if v is not None}


def _process_gemini_inputs(inputs: dict) -> dict:
    """Process Gemini inputs to normalize them for LangSmith tracing."""
    # If contents is not present or not in list format, return as-is
    contents = inputs.get("contents")
    if not contents:
        return inputs

    # Handle string input (simple case)
    if isinstance(contents, str):
        return {
            "messages": [{"role": "user", "content": contents}],
            "model": inputs.get("model"),
            **({k: v for k, v in inputs.items() if k not in ("contents", "model")}),
        }

    # Handle list of content objects (multimodal case)
    if isinstance(contents, list):
        messages = []
        for content in contents:
            if isinstance(content, dict):
                role = content.get("role", "user")
                parts = content.get("parts", [])

                # Extract text and other parts
                text_parts = []
                content_parts = []

                for part in parts:
                    if isinstance(part, dict):
                        # Handle text parts
                        if "text" in part and part["text"]:
                            text_parts.append(part["text"])
                            content_parts.append({"type": "text", "text": part["text"]})
                        # Handle inline data (images)
                        elif "inline_data" in part:
                            inline_data = part["inline_data"]
                            mime_type = inline_data.get("mime_type", "image/jpeg")
                            data = inline_data.get("data", "")
                            content_parts.append(
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{data}",
                                        "detail": "high",
                                    },
                                }
                            )
                    elif isinstance(part, str):
                        # Handle simple string parts
                        text_parts.append(part)
                        content_parts.append({"type": "text", "text": part})

                # If only text parts, use simple string format
                if content_parts and all(
                    p.get("type") == "text" for p in content_parts
                ):
                    message_content = "\n".join(text_parts)
                else:
                    message_content = content_parts if content_parts else ""

                messages.append({"role": role, "content": message_content})

        return {
            "messages": messages,
            "model": inputs.get("model"),
            **({k: v for k, v in inputs.items() if k not in ("contents", "model")}),
        }

    # Fallback: return original inputs
    return inputs


def _infer_invocation_params(kwargs: dict) -> dict:
    """Extract invocation parameters for tracing."""
    stripped = _strip_none(kwargs)
    config = stripped.get("config", {})

    # Handle both dict config and GenerateContentConfig object
    if hasattr(config, "temperature"):
        temperature = config.temperature
        max_tokens = getattr(config, "max_output_tokens", None)
        stop = getattr(config, "stop_sequences", None)
    else:
        temperature = config.get("temperature")
        max_tokens = config.get("max_output_tokens")
        stop = config.get("stop_sequences")

    return {
        "ls_provider": "google",
        "ls_model_type": "chat",
        "ls_model_name": stripped.get("model"),
        "ls_temperature": temperature,
        "ls_max_tokens": max_tokens,
        "ls_stop": stop,
    }


def _create_usage_metadata(gemini_usage_metadata: dict) -> UsageMetadata:
    """Convert Gemini usage metadata to LangSmith format."""
    prompt_token_count = gemini_usage_metadata.get("prompt_token_count") or 0
    candidates_token_count = gemini_usage_metadata.get("candidates_token_count") or 0
    cached_content_token_count = (
        gemini_usage_metadata.get("cached_content_token_count") or 0
    )
    thoughts_token_count = gemini_usage_metadata.get("thoughts_token_count") or 0
    total_token_count = (
        gemini_usage_metadata.get("total_token_count")
        or prompt_token_count + candidates_token_count
    )

    input_token_details: dict = {}
    if cached_content_token_count:
        input_token_details["cache_read"] = cached_content_token_count

    output_token_details: dict = {}
    if thoughts_token_count:
        output_token_details["reasoning"] = thoughts_token_count

    return UsageMetadata(
        input_tokens=prompt_token_count,
        output_tokens=candidates_token_count,
        total_tokens=total_token_count,
        input_token_details=InputTokenDetails(
            **{k: v for k, v in input_token_details.items() if v is not None}
        ),
        output_token_details=OutputTokenDetails(
            **{k: v for k, v in output_token_details.items() if v is not None}
        ),
    )


def _process_generate_content_response(response: Any) -> dict:
    """Process Gemini response for tracing."""
    try:
        # Convert response to dictionary
        if hasattr(response, "to_dict"):
            rdict = response.to_dict()
        elif hasattr(response, "model_dump"):
            rdict = response.model_dump()
        else:
            rdict = {"text": getattr(response, "text", str(response))}

        # Extract text content from candidates if available
        text_content = ""
        if "candidates" in rdict and rdict["candidates"]:
            candidate = rdict["candidates"][0]
            if "content" in candidate:
                content = candidate["content"]
                if "parts" in content and content["parts"]:
                    # Combine text from all parts
                    text_parts = [
                        part.get("text", "")
                        for part in content["parts"]
                        if "text" in part
                    ]
                    text_content = "".join(text_parts)
        elif "text" in rdict:
            text_content = rdict["text"]

        # Build chat-like response format
        result = {"content": text_content, "role": "assistant"}

        # Extract and convert usage metadata
        usage_metadata = rdict.get("usage_metadata")
        if usage_metadata:
            result["usage_metadata"] = _create_usage_metadata(usage_metadata)

        return result
    except Exception as e:
        logger.debug(f"Error processing Gemini response: {e}")
        return {"output": response}


def _reduce_generate_content_chunks(all_chunks: list) -> dict:
    """Reduce streaming chunks into a single response."""
    if not all_chunks:
        return {"content": "", "role": "assistant"}

    # Accumulate text from all chunks
    full_text = ""
    last_chunk = None

    for chunk in all_chunks:
        try:
            if hasattr(chunk, "text") and chunk.text:
                full_text += chunk.text
            last_chunk = chunk
        except Exception as e:
            logger.debug(f"Error processing chunk: {e}")

    # Build chat-like response format
    result = {"content": full_text, "role": "assistant"}

    if last_chunk:
        try:
            # Extract usage metadata from the last chunk
            if hasattr(last_chunk, "usage_metadata") and last_chunk.usage_metadata:
                if hasattr(last_chunk.usage_metadata, "to_dict"):
                    usage_dict = last_chunk.usage_metadata.to_dict()
                elif hasattr(last_chunk.usage_metadata, "model_dump"):
                    usage_dict = last_chunk.usage_metadata.model_dump()
                else:
                    usage_dict = {
                        "prompt_token_count": getattr(
                            last_chunk.usage_metadata, "prompt_token_count", 0
                        ),
                        "candidates_token_count": getattr(
                            last_chunk.usage_metadata, "candidates_token_count", 0
                        ),
                        "cached_content_token_count": getattr(
                            last_chunk.usage_metadata, "cached_content_token_count", 0
                        ),
                        "thoughts_token_count": getattr(
                            last_chunk.usage_metadata, "thoughts_token_count", 0
                        ),
                        "total_token_count": getattr(
                            last_chunk.usage_metadata, "total_token_count", 0
                        ),
                    }
                result["usage_metadata"] = _create_usage_metadata(usage_dict)
        except Exception as e:
            logger.debug(f"Error extracting metadata from last chunk: {e}")

    return result


def _get_wrapper(
    original_generate: Callable,
    name: str,
    tracing_extra: Optional[TracingExtra] = None,
    is_streaming: bool = False,
) -> Callable:
    """Create a wrapper for Gemini's generate_content methods."""
    textra = tracing_extra or {}

    @functools.wraps(original_generate)
    def generate(*args, **kwargs):
        decorator = run_helpers.traceable(
            name=name,
            run_type="llm",
            reduce_fn=_reduce_generate_content_chunks if is_streaming else None,
            process_inputs=_process_gemini_inputs,
            process_outputs=_process_generate_content_response,
            _invocation_params_fn=_infer_invocation_params,
            **textra,
        )

        return decorator(original_generate)(*args, **kwargs)

    @functools.wraps(original_generate)
    async def agenerate(*args, **kwargs):
        decorator = run_helpers.traceable(
            name=name,
            run_type="llm",
            reduce_fn=_reduce_generate_content_chunks if is_streaming else None,
            process_inputs=_process_gemini_inputs,
            process_outputs=_process_generate_content_response,
            _invocation_params_fn=_infer_invocation_params,
            **textra,
        )

        return await decorator(original_generate)(*args, **kwargs)

    return agenerate if run_helpers.is_async(original_generate) else generate


class TracingExtra(TypedDict, total=False):
    metadata: Optional[Mapping[str, Any]]
    tags: Optional[list[str]]
    client: Optional[ls_client.Client]


def wrap_gemini(
    client: C,
    *,
    tracing_extra: Optional[TracingExtra] = None,
    chat_name: str = "ChatGoogleGenerativeAI",
) -> C:
    """Patch the Google Gen AI client to make it traceable.

    .. warning::
        **BETA**: This wrapper is in beta.

    Supports:
        - generate_content() and generate_content_stream() methods
        - Sync and async clients
        - Streaming and non-streaming responses
        - Multimodal inputs (text + images)
        - Token usage tracking including reasoning tokens

    Args:
        client (genai.Client): The Google Gen AI client to patch.
        tracing_extra (Optional[TracingExtra], optional): Extra tracing information.
            Defaults to None.
        chat_name (str, optional): The run name for the chat endpoint.
            Defaults to "ChatGoogleGenerativeAI".

    Returns:
        genai.Client: The patched client.

    Example:

        .. code-block:: python

            from google import genai
            from langsmith import wrappers

            # Use Google Gen AI client same as you normally would.
            client = wrappers.wrap_gemini(genai.Client(api_key="your-api-key"))

            # Non-streaming:
            response = client.models.generate_content(
                model="gemini-2.0-flash-001",
                contents="Why is the sky blue?",
            )
            print(response.text)

            # Streaming:
            for chunk in client.models.generate_content_stream(
                model="gemini-2.0-flash-001",
                contents="Tell me a story",
            ):
                print(chunk.text, end="")

    .. versionadded:: 0.4.33
        Initial beta release of Google Gemini wrapper.

    """
    # Issue beta warning on first use
    warnings.warn(
        "wrap_gemini is currently in beta."
        "Please report any issues at https://github.com/langchain-ai/langsmith-sdk",
        FutureWarning,
        stacklevel=2,
    )

    tracing_extra = tracing_extra or {}

    # Check if already wrapped to prevent double-wrapping
    if (
        hasattr(client, "models")
        and hasattr(client.models, "generate_content")
        and hasattr(client.models.generate_content, "__wrapped__")
    ):
        raise ValueError(
            "This Google Gen AI client has already been wrapped. "
            "Wrapping a client multiple times is not supported."
        )

    # Wrap synchronous methods
    if hasattr(client, "models") and hasattr(client.models, "generate_content"):
        client.models.generate_content = _get_wrapper(  # type: ignore[method-assign]
            client.models.generate_content,
            chat_name,
            tracing_extra=tracing_extra,
            is_streaming=False,
        )

    if hasattr(client, "models") and hasattr(client.models, "generate_content_stream"):
        client.models.generate_content_stream = _get_wrapper(  # type: ignore[method-assign]
            client.models.generate_content_stream,
            chat_name,
            tracing_extra=tracing_extra,
            is_streaming=True,
        )

    # Wrap async methods (aio namespace)
    if (
        hasattr(client, "aio")
        and hasattr(client.aio, "models")
        and hasattr(client.aio.models, "generate_content")
    ):
        client.aio.models.generate_content = _get_wrapper(  # type: ignore[method-assign]
            client.aio.models.generate_content,
            chat_name,
            tracing_extra=tracing_extra,
            is_streaming=False,
        )

    if (
        hasattr(client, "aio")
        and hasattr(client.aio, "models")
        and hasattr(client.aio.models, "generate_content_stream")
    ):
        client.aio.models.generate_content_stream = _get_wrapper(  # type: ignore[method-assign]
            client.aio.models.generate_content_stream,
            chat_name,
            tracing_extra=tracing_extra,
            is_streaming=True,
        )

    return client
