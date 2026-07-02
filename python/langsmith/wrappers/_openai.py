from __future__ import annotations

import functools
import logging
from collections import defaultdict
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

# ``_create_usage_metadata`` lives in a non-deprecated internal module so
# integrations can reuse it without importing the ``wrappers`` package (whose
# ``__init__`` warns at import time). Re-exported here for backwards compat.
from langsmith._internal._usage import _create_usage_metadata

if TYPE_CHECKING:
    from openai import AsyncOpenAI, OpenAI
    from openai.types.chat.chat_completion_chunk import (
        ChatCompletionChunk,
        Choice,
        ChoiceDeltaToolCall,
    )
    from openai.types.completion import Completion
    from openai.types.responses import ResponseStreamEvent  # type: ignore

# Any is used since it may work with Azure or other providers
C = TypeVar("C", bound=Union["OpenAI", "AsyncOpenAI", Any])
logger = logging.getLogger(__name__)


@functools.lru_cache
def _get_omit_types() -> tuple[type, ...]:
    """Get NotGiven/Omit sentinel types used by OpenAI SDK."""
    types: list[type[Any]] = []
    try:
        from openai._types import NotGiven, Omit

        types.append(NotGiven)
        types.append(Omit)
    except ImportError:
        pass

    return tuple(types)


def _strip_not_given(d: dict) -> dict:
    try:
        omit_types = _get_omit_types()
        if not omit_types:
            return d
        return {
            k: v
            for k, v in d.items()
            if not (isinstance(v, omit_types) or (k.startswith("extra_") and v is None))
        }
    except Exception as e:
        logger.error(f"Error stripping NotGiven: {e}")
        return d


def _process_inputs(d: dict) -> dict:
    """Strip `NotGiven` values and serialize `text_format` to JSON schema."""
    d = _strip_not_given(d)

    # Convert text_format (Pydantic model) to JSON schema if present
    if "text_format" in d:
        text_format = d["text_format"]
        if hasattr(text_format, "model_json_schema"):
            try:
                return {
                    **d,
                    "text_format": text_format.model_json_schema(),
                }
            except Exception:
                pass
    return d


def _infer_invocation_params(
    model_type: str,
    provider: str,
    prepopulated_invocation_params: dict,
    use_responses_api: bool,
    kwargs: dict,
):
    stripped = _strip_not_given(kwargs)

    stop = stripped.get("stop")
    if stop and isinstance(stop, str):
        stop = [stop]

    # Allowlist of safe invocation parameters to include
    # Only include known, non-sensitive parameters
    allowed_invocation_keys = {
        "frequency_penalty",
        "n",
        "logit_bias",
        "logprobs",
        "modalities",
        "parallel_tool_calls",
        "prediction",
        "presence_penalty",
        "prompt_cache_key",
        "reasoning",
        "reasoning_effort",
        "response_format",
        "seed",
        "service_tier",
        "stream_options",
        "top_logprobs",
        "top_p",
        "truncation",
        "user",
        "verbosity",
        "web_search_options",
    }

    # Only include allowlisted parameters
    invocation_params = {
        k: v for k, v in stripped.items() if k in allowed_invocation_keys
    }

    if use_responses_api:
        invocation_params["use_responses_api"] = True

    return {
        "ls_provider": provider,
        "ls_model_type": model_type,
        "ls_model_name": stripped.get("model"),
        "ls_temperature": stripped.get("temperature"),
        "ls_max_tokens": stripped.get("max_tokens")
        or stripped.get("max_completion_tokens")
        or stripped.get("max_output_tokens"),
        "ls_stop": stop,
        "ls_invocation_params": {
            **prepopulated_invocation_params,
            **invocation_params,
        },
    }


def _reduce_choices(choices: list[Choice]) -> dict:
    reversed_choices = list(reversed(choices))
    message: dict[str, Any] = {
        "role": "assistant",
        "content": "",
    }
    for c in reversed_choices:
        if hasattr(c, "delta") and getattr(c.delta, "role", None):
            message["role"] = c.delta.role
            break
    tool_calls: defaultdict[int, list[ChoiceDeltaToolCall]] = defaultdict(list)
    for c in choices:
        if hasattr(c, "delta"):
            if getattr(c.delta, "content", None):
                message["content"] += c.delta.content
            if getattr(c.delta, "function_call", None):
                if not message.get("function_call"):
                    message["function_call"] = {"name": "", "arguments": ""}
                name_ = getattr(c.delta.function_call, "name", None)
                if name_:
                    message["function_call"]["name"] += name_
                arguments_ = getattr(c.delta.function_call, "arguments", None)
                if arguments_:
                    message["function_call"]["arguments"] += arguments_
            if getattr(c.delta, "tool_calls", None):
                tool_calls_list = c.delta.tool_calls
                if tool_calls_list is not None:
                    for tool_call in tool_calls_list:
                        tool_calls[tool_call.index].append(tool_call)
    if tool_calls:
        message["tool_calls"] = [None for _ in range(max(tool_calls.keys()) + 1)]
        for index, tool_call_chunks in tool_calls.items():
            message["tool_calls"][index] = {
                "index": index,
                "id": next((c.id for c in tool_call_chunks if c.id), None),
                "type": next((c.type for c in tool_call_chunks if c.type), None),
                "function": {"name": "", "arguments": ""},
            }
            for chunk in tool_call_chunks:
                if getattr(chunk, "function", None):
                    name_ = getattr(chunk.function, "name", None)
                    if name_:
                        message["tool_calls"][index]["function"]["name"] += name_
                    arguments_ = getattr(chunk.function, "arguments", None)
                    if arguments_:
                        message["tool_calls"][index]["function"]["arguments"] += (
                            arguments_
                        )
    return {
        "index": getattr(choices[0], "index", 0) if choices else 0,
        "finish_reason": next(
            (
                c.finish_reason
                for c in reversed_choices
                if getattr(c, "finish_reason", None)
            ),
            None,
        ),
        "message": message,
    }


def _reduce_chat(all_chunks: list[ChatCompletionChunk]) -> dict:
    choices_by_index: defaultdict[int, list[Choice]] = defaultdict(list)
    for chunk in all_chunks:
        for choice in chunk.choices:
            choices_by_index[choice.index].append(choice)
    if all_chunks:
        d = all_chunks[-1].model_dump()
        d["choices"] = [
            _reduce_choices(choices) for choices in choices_by_index.values()
        ]
    else:
        d = {"choices": [{"message": {"role": "assistant", "content": ""}}]}
    # streamed outputs don't go through `process_outputs`
    # so we need to flatten metadata here
    oai_token_usage = d.pop("usage", None)
    d["usage_metadata"] = (
        _create_usage_metadata(oai_token_usage) if oai_token_usage else None
    )
    return d


def _reduce_completions(all_chunks: list[Completion]) -> dict:
    all_content = []
    for chunk in all_chunks:
        content = chunk.choices[0].text
        if content is not None:
            all_content.append(content)
    content = "".join(all_content)
    if all_chunks:
        d = all_chunks[-1].model_dump()
        d["choices"] = [{"text": content}]
    else:
        d = {"choices": [{"text": content}]}

    return d


def _process_chat_completion(outputs: Any):
    try:
        # Check if outputs is an APIResponse wrapper (from with_raw_response).
        # The OpenAI SDK's APIResponse wraps the actual response object.
        # Call .parse() to extract the ChatCompletion/Completion for tracing.
        # See: github.com/openai/openai-python/blob/main/src/openai/_response.py#L285
        if hasattr(outputs, "parse") and callable(outputs.parse):
            try:
                outputs = outputs.parse()
            except Exception:
                pass

        rdict = outputs.model_dump()
        oai_token_usage = rdict.pop("usage", None)
        rdict["usage_metadata"] = (
            _create_usage_metadata(oai_token_usage, rdict.get("service_tier"))
            if oai_token_usage
            else None
        )
        return rdict
    except BaseException as e:
        logger.debug(f"Error processing chat completion: {e}")
        return {"output": outputs}


def _get_wrapper(
    original_create: Callable,
    name: str,
    reduce_fn: Callable,
    tracing_extra: Optional[TracingExtra] = None,
    invocation_params_fn: Optional[Callable] = None,
    process_outputs: Optional[Callable] = None,
) -> Callable:
    textra = tracing_extra or {}

    @functools.wraps(original_create)
    def create(*args, **kwargs):
        decorator = run_helpers.traceable(
            name=name,
            run_type="llm",
            reduce_fn=reduce_fn if kwargs.get("stream") is True else None,
            process_inputs=_process_inputs,
            _invocation_params_fn=invocation_params_fn,
            process_outputs=process_outputs,
            **textra,
        )

        return decorator(original_create)(*args, **kwargs)

    @functools.wraps(original_create)
    async def acreate(*args, **kwargs):
        decorator = run_helpers.traceable(
            name=name,
            run_type="llm",
            reduce_fn=reduce_fn if kwargs.get("stream") is True else None,
            process_inputs=_process_inputs,
            _invocation_params_fn=invocation_params_fn,
            process_outputs=process_outputs,
            **textra,
        )
        return await decorator(original_create)(*args, **kwargs)

    return acreate if run_helpers.is_async(original_create) else create


def _get_parse_wrapper(
    original_parse: Callable,
    name: str,
    process_outputs: Callable,
    tracing_extra: Optional[TracingExtra] = None,
    invocation_params_fn: Optional[Callable] = None,
) -> Callable:
    textra = tracing_extra or {}

    @functools.wraps(original_parse)
    def parse(*args, **kwargs):
        decorator = run_helpers.traceable(
            name=name,
            run_type="llm",
            reduce_fn=None,
            process_inputs=_process_inputs,
            _invocation_params_fn=invocation_params_fn,
            process_outputs=process_outputs,
            **textra,
        )
        return decorator(original_parse)(*args, **kwargs)

    @functools.wraps(original_parse)
    async def aparse(*args, **kwargs):
        decorator = run_helpers.traceable(
            name=name,
            run_type="llm",
            reduce_fn=None,
            process_inputs=_process_inputs,
            _invocation_params_fn=invocation_params_fn,
            process_outputs=process_outputs,
            **textra,
        )
        return await decorator(original_parse)(*args, **kwargs)

    return aparse if run_helpers.is_async(original_parse) else parse


def _reduce_response_events(events: list[ResponseStreamEvent]) -> dict:
    for event in events:
        if event.type == "response.completed":
            return _process_responses_api_output(event.response)
    return {}


class TracingExtra(TypedDict, total=False):
    metadata: Optional[Mapping[str, Any]]
    tags: Optional[list[str]]
    client: Optional[ls_client.Client]


def wrap_openai(
    client: C,
    *,
    tracing_extra: Optional[TracingExtra] = None,
    chat_name: str = "ChatOpenAI",
    completions_name: str = "OpenAI",
) -> C:
    """Patch the OpenAI client to make it traceable.

    Supports:
        - Chat and Responses API's
        - Sync and async OpenAI clients
        - `create` and `parse` methods
        - With and without streaming
        - `with_raw_response` API for accessing HTTP headers

    Args:
        client: The client to patch.
        tracing_extra: Extra tracing information.
        chat_name: The run name for the chat completions endpoint.
        completions_name: The run name for the completions endpoint.

    Returns:
        The patched client.

    Example:
        ```python
        import openai
        from langsmith import wrappers

        # Use OpenAI client same as you normally would.
        client = wrappers.wrap_openai(openai.OpenAI())

        # Chat API:
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": "What physics breakthroughs do you predict will happen by 2300?",
            },
        ]
        completion = client.chat.completions.create(
            model="gpt-4o-mini", messages=messages
        )
        print(completion.choices[0].message.content)

        # Responses API:
        response = client.responses.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        print(response.output_text)

        # With raw response to access headers:
        raw_response = client.chat.completions.with_raw_response.create(
            model="gpt-4o-mini", messages=messages
        )
        print(raw_response.headers)  # Access HTTP headers
        completion = raw_response.parse()  # Get parsed response
        ```

    !!! warning "Behavior changed in `langsmith` 0.3.16"

        Support for Responses API added.

    !!! warning "Behavior changed in `langsmith` 0.3.x"

        Support for `with_raw_response` API added.
    """  # noqa: E501
    tracing_extra = tracing_extra or {}

    # Extract ls_invocation_params from metadata
    metadata = dict(tracing_extra.get("metadata") or {})
    prepopulated_invocation_params = metadata.pop("ls_invocation_params", {})

    # Create new tracing_extra without ls_invocation_params in metadata
    tracing_extra_rest: TracingExtra = {  # type: ignore[assignment]
        k: v for k, v in tracing_extra.items() if k != "metadata"
    }
    if metadata:
        tracing_extra_rest["metadata"] = metadata  # type: ignore[typeddict-item]

    ls_provider = "openai"
    try:
        from openai import AsyncAzureOpenAI, AzureOpenAI

        if isinstance(client, AzureOpenAI) or isinstance(client, AsyncAzureOpenAI):
            ls_provider = "azure"
            chat_name = "AzureChatOpenAI"
            completions_name = "AzureOpenAI"
    except ImportError:
        pass

    # First wrap the create methods - these handle non-streaming cases
    client.chat.completions.create = _get_wrapper(  # type: ignore[method-assign]
        client.chat.completions.create,
        chat_name,
        _reduce_chat,
        tracing_extra=tracing_extra_rest,
        invocation_params_fn=functools.partial(
            _infer_invocation_params,
            "chat",
            ls_provider,
            prepopulated_invocation_params,
            False,
        ),
        process_outputs=_process_chat_completion,
    )

    client.completions.create = _get_wrapper(  # type: ignore[method-assign]
        client.completions.create,
        completions_name,
        _reduce_completions,
        tracing_extra=tracing_extra_rest,
        invocation_params_fn=functools.partial(
            _infer_invocation_params,
            "llm",
            ls_provider,
            prepopulated_invocation_params,
            False,
        ),
    )

    # Wrap beta.chat.completions.parse if it exists
    if (
        hasattr(client, "beta")
        and hasattr(client.beta, "chat")
        and hasattr(client.beta.chat, "completions")
        and hasattr(client.beta.chat.completions, "parse")
    ):
        client.beta.chat.completions.parse = _get_parse_wrapper(  # type: ignore[method-assign]
            client.beta.chat.completions.parse,  # type: ignore
            chat_name,
            _process_chat_completion,
            tracing_extra=tracing_extra_rest,
            invocation_params_fn=functools.partial(
                _infer_invocation_params,
                "chat",
                ls_provider,
                prepopulated_invocation_params,
                False,
            ),
        )

    # Wrap chat.completions.parse if it exists
    if (
        hasattr(client, "chat")
        and hasattr(client.chat, "completions")
        and hasattr(client.chat.completions, "parse")
    ):
        client.chat.completions.parse = _get_parse_wrapper(  # type: ignore[method-assign]
            client.chat.completions.parse,  # type: ignore
            chat_name,
            _process_chat_completion,
            tracing_extra=tracing_extra_rest,
            invocation_params_fn=functools.partial(
                _infer_invocation_params,
                "chat",
                ls_provider,
                prepopulated_invocation_params,
                False,
            ),
        )

    # For the responses API: "client.responses.create(**kwargs)"
    if hasattr(client, "responses"):
        if hasattr(client.responses, "create"):
            client.responses.create = _get_wrapper(  # type: ignore[method-assign]
                client.responses.create,
                chat_name,
                _reduce_response_events,
                process_outputs=_process_responses_api_output,
                tracing_extra=tracing_extra_rest,
                invocation_params_fn=functools.partial(
                    _infer_invocation_params,
                    "chat",
                    ls_provider,
                    prepopulated_invocation_params,
                    True,
                ),
            )
        if hasattr(client.responses, "parse"):
            client.responses.parse = _get_parse_wrapper(  # type: ignore[method-assign]
                client.responses.parse,
                chat_name,
                _process_responses_api_output,
                tracing_extra=tracing_extra_rest,
                invocation_params_fn=functools.partial(
                    _infer_invocation_params,
                    "chat",
                    ls_provider,
                    prepopulated_invocation_params,
                    True,
                ),
            )

    return client


def _process_responses_api_output(response: Any) -> dict:
    if response:
        try:
            # Unwrap APIResponse from with_raw_response for tracing
            if hasattr(response, "parse") and callable(response.parse):
                try:
                    response = response.parse()
                except Exception:
                    pass

            output = response.model_dump(exclude_none=True, mode="json")
            if usage := output.pop("usage", None):
                output["usage_metadata"] = _create_usage_metadata(
                    usage, output.get("service_tier")
                )
            return output
        except Exception:
            return {"output": response}
    return {}
