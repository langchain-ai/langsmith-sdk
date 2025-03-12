from __future__ import annotations

import functools
import logging
from collections import defaultdict
from collections.abc import Mapping
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    DefaultDict,
    Dict,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
)

from typing_extensions import TypedDict

from langsmith import client as ls_client
from langsmith import run_helpers
from langsmith.schemas import InputTokenDetails, OutputTokenDetails, UsageMetadata

# Try to import from different possible locations depending on OpenAI SDK version
try:
    from openai.lib.streaming.responses import AsyncResponseStream, ResponseStream
    from openai.types.responses import ParsedResponse
except ImportError:
    try:
        from openai.lib.responses import ParsedResponse
        from openai.lib.streaming.responses import AsyncResponseStream, ResponseStream
    except ImportError:
        # Define fallback types if needed
        class ParsedResponse:
            pass

        class ResponseStream:
            pass

        class AsyncResponseStream:
            pass


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
def _get_not_given() -> Optional[Type]:
    try:
        from openai._types import NotGiven

        return NotGiven
    except ImportError:
        return None


def _strip_not_given(d: dict) -> dict:
    try:
        not_given = _get_not_given()
        if not_given is None:
            return d
        return {
            k: v
            for k, v in d.items()
            if not (isinstance(v, not_given) or (k.startswith("extra_") and v is None))
        }
    except Exception as e:
        logger.error(f"Error stripping NotGiven: {e}")
        return d


def _infer_invocation_params(model_type: str, kwargs: dict):
    stripped = _strip_not_given(kwargs)

    stop = stripped.get("stop")
    if stop and isinstance(stop, str):
        stop = [stop]

    return {
        "ls_provider": "openai",
        "ls_model_type": model_type,
        "ls_model_name": stripped.get("model", None),
        "ls_temperature": stripped.get("temperature", None),
        "ls_max_tokens": stripped.get("max_tokens", None),
        "ls_stop": stop,
    }


def _reduce_choices(choices: List[Choice]) -> dict:
    reversed_choices = list(reversed(choices))
    message: Dict[str, Any] = {
        "role": "assistant",
        "content": "",
    }
    for c in reversed_choices:
        if hasattr(c, "delta") and getattr(c.delta, "role", None):
            message["role"] = c.delta.role
            break
    tool_calls: DefaultDict[int, List[ChoiceDeltaToolCall]] = defaultdict(list)
    for c in choices:
        if hasattr(c, "delta") and getattr(c.delta, "content", None):
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
                        tool_calls[c.index].append(tool_call)
    if tool_calls:
        message["tool_calls"] = [None for _ in tool_calls.keys()]
        for index, tool_call_chunks in tool_calls.items():
            message["tool_calls"][index] = {
                "index": index,
                "id": next((c.id for c in tool_call_chunks if c.id), None),
                "type": next((c.type for c in tool_call_chunks if c.type), None),
            }
            for chunk in tool_call_chunks:
                if getattr(chunk, "function", None):
                    if not message["tool_calls"][index].get("function"):
                        message["tool_calls"][index]["function"] = {
                            "name": "",
                            "arguments": "",
                        }
                    name_ = getattr(chunk.function, "name", None)
                    if name_:
                        fn_ = message["tool_calls"][index]["function"]
                        fn_["name"] += name_
                    arguments_ = getattr(chunk.function, "arguments", None)
                    if arguments_:
                        fn_ = message["tool_calls"][index]["function"]
                        fn_["arguments"] += arguments_
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


def _reduce_chat(all_chunks: List[ChatCompletionChunk]) -> dict:
    choices_by_index: DefaultDict[int, List[Choice]] = defaultdict(list)
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


def _reduce_completions(all_chunks: List[Completion]) -> dict:
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


def _create_usage_metadata(oai_token_usage: dict) -> UsageMetadata:
    input_tokens = (
        oai_token_usage.get("prompt_tokens") or oai_token_usage.get("input_tokens") or 0
    )
    output_tokens = (
        oai_token_usage.get("completion_tokens")
        or oai_token_usage.get("output_tokens")
        or 0
    )
    total_tokens = oai_token_usage.get("total_tokens") or input_tokens + output_tokens
    input_token_details: dict = {
        "audio": (
            oai_token_usage.get("prompt_tokens_details")
            or oai_token_usage.get("input_tokens_details")
            or {}
        ).get("audio_tokens"),
        "cache_read": (
            oai_token_usage.get("prompt_tokens_details")
            or oai_token_usage.get("input_tokens_details")
            or {}
        ).get("cached_tokens"),
    }
    output_token_details: dict = {
        "audio": (
            oai_token_usage.get("completion_tokens_details")
            or oai_token_usage.get("output_tokens_details")
            or {}
        ).get("audio_tokens"),
        "reasoning": (
            oai_token_usage.get("completion_tokens_details")
            or oai_token_usage.get("output_tokens_details")
            or {}
        ).get("reasoning_tokens"),
    }
    return UsageMetadata(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        input_token_details=InputTokenDetails(
            **{k: v for k, v in input_token_details.items() if v is not None}
        ),
        output_token_details=OutputTokenDetails(
            **{k: v for k, v in output_token_details.items() if v is not None}
        ),
    )


def _process_chat_completion(outputs: Any):
    try:
        rdict = outputs.model_dump()
        oai_token_usage = rdict.pop("usage", None)
        rdict["usage_metadata"] = (
            _create_usage_metadata(oai_token_usage) if oai_token_usage else None
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
    def create(*args, stream: bool = False, **kwargs):
        decorator = run_helpers.traceable(
            name=name,
            run_type="llm",
            reduce_fn=reduce_fn if stream else None,
            process_inputs=_strip_not_given,
            _invocation_params_fn=invocation_params_fn,
            process_outputs=process_outputs,
            **textra,
        )

        return decorator(original_create)(*args, stream=stream, **kwargs)

    @functools.wraps(original_create)
    async def acreate(*args, stream: bool = False, **kwargs):
        kwargs = _strip_not_given(kwargs)
        decorator = run_helpers.traceable(
            name=name,
            run_type="llm",
            reduce_fn=reduce_fn if stream else None,
            process_inputs=_strip_not_given,
            _invocation_params_fn=invocation_params_fn,
            process_outputs=process_outputs,
            **textra,
        )
        return await decorator(original_create)(*args, stream=stream, **kwargs)

    return acreate if run_helpers.is_async(original_create) else create


def _get_parse_wrapper(
    original_parse: Callable,
    name: str,
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
            process_inputs=_strip_not_given,
            _invocation_params_fn=invocation_params_fn,
            process_outputs=_process_chat_completion,
            **textra,
        )
        return decorator(original_parse)(*args, **kwargs)

    @functools.wraps(original_parse)
    async def aparse(*args, **kwargs):
        kwargs = _strip_not_given(kwargs)
        decorator = run_helpers.traceable(
            name=name,
            run_type="llm",
            reduce_fn=None,
            process_inputs=_strip_not_given,
            _invocation_params_fn=invocation_params_fn,
            process_outputs=_process_chat_completion,
            **textra,
        )
        return await decorator(original_parse)(*args, **kwargs)

    return aparse if run_helpers.is_async(original_parse) else parse


def _get_stream_wrapper(
    original_stream: Callable,
    name: str,
    tracing_extra: TracingExtra,
    invocation_params_fn: Optional[Callable] = None,
) -> Callable:
    """Create a wrapper for OpenAI's streaming context manager."""
    is_async = "async" in str(original_stream).lower()

    if is_async:

        @functools.wraps(original_stream)
        async def wrapped_stream(*args, **kwargs):
            from openai.lib.streaming.responses import AsyncResponseStreamManager

            # Process the kwargs to get full input representation
            processed_kwargs = _strip_not_given(kwargs)

            # Extract the actual parameters that were passed to stream()
            # This ensures we capture all the important arguments (input, model, etc.)
            # not just the invocation parameters
            inputs = processed_kwargs

            # Apply invocation_params_fn for additional metadata if available
            if invocation_params_fn:
                invocation_params = invocation_params_fn(processed_kwargs)
                # Add these as metadata rather than replacing the actual inputs
                tracing_extra_with_params = dict(tracing_extra)
                if "metadata" not in tracing_extra_with_params:
                    tracing_extra_with_params["metadata"] = {}
                tracing_extra_with_params["metadata"].update(
                    {"invocation_params": invocation_params}
                )
            else:
                tracing_extra_with_params = tracing_extra

            # Get the original ResponseStreamManager
            manager = original_stream(*args, **kwargs)

            # Create a trace to be used in the context manager
            trace_ctx = run_helpers.trace(
                name=name,
                run_type="llm",
                inputs=inputs,  # Use the full processed kwargs as inputs
                extra=tracing_extra_with_params,
            )

            class ProxyContextManager:
                def __init__(self, stream_manager: AsyncResponseStreamManager):
                    self.__stream_manager = stream_manager
                    self.__events = []

                async def __aenter__(self):
                    self._ls_run = trace_ctx.__enter__()
                    self.__ls_stream = await self.__stream_manager.__aenter__()
                    return self

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    await self.__stream_manager.__aexit__(exc_type, exc_val, exc_tb)
                    try:
                        result = await self.__ls_stream.get_final_response()
                        outputs = {}

                        if hasattr(result, "model_dump"):
                            result_dict = result.model_dump(mode="json")

                            # Extract usage data if available
                            if hasattr(result, "usage") and result.usage:
                                usage_data = result.usage.model_dump()
                                usage_metadata = _create_usage_metadata(usage_data)
                                outputs["usage_metadata"] = usage_metadata

                            outputs.update(
                                {
                                    "output": result_dict.get("output") or {},
                                    "events": self.__events,
                                }
                            )

                        self._ls_run.add_outputs(outputs)
                    except Exception as e:
                        logger.warning(f"Error getting final output: {e}")
                    trace_ctx.__exit__(exc_type, exc_val, exc_tb)

                async def __aiter__(self):
                    async for chunk in self.__ls_stream:
                        self.__events.append(chunk)
                        yield chunk

                async def __anext__(self):
                    event = await self.__ls_stream.__anext__()
                    self.__events.append(event)
                    return event

                async def close(self):
                    await self.__ls_stream.close()

                async def get_final_response(self):
                    return await self.__ls_stream.get_final_response()

                async def until_done(self):
                    await self.__ls_stream.until_done()
                    return self

            return ProxyContextManager(manager)

        return wrapped_stream
    else:

        @functools.wraps(original_stream)
        def wrapped_stream(*args, **kwargs):
            from openai.lib.streaming.responses import ResponseStreamManager

            # Process the kwargs to get full input representation
            processed_kwargs = _strip_not_given(kwargs)

            # Extract the actual parameters that were passed to stream()
            # This ensures we capture all the important arguments (input, model, etc.)
            # not just the invocation parameters
            inputs = processed_kwargs

            # Apply invocation_params_fn for additional metadata if available
            if invocation_params_fn:
                invocation_params = invocation_params_fn(processed_kwargs)
                # Add these as metadata rather than replacing the actual inputs
                tracing_extra_with_params = dict(tracing_extra)
                if "metadata" not in tracing_extra_with_params:
                    tracing_extra_with_params["metadata"] = {}
                tracing_extra_with_params["metadata"].update(
                    {"invocation_params": invocation_params}
                )
            else:
                tracing_extra_with_params = tracing_extra

            # Get the original ResponseStreamManager
            manager = original_stream(*args, **kwargs)

            # Create a trace to be used in the context manager
            trace_ctx = run_helpers.trace(
                name=name,
                run_type="llm",
                inputs=inputs,  # Use the full processed kwargs as inputs
                extra=tracing_extra_with_params,
            )

            class ProxyContextManager:
                def __init__(self, stream_manager: ResponseStreamManager):
                    self.__stream_manager = stream_manager
                    self.__events = []

                def __enter__(self):
                    self._ls_run = trace_ctx.__enter__()
                    self.__ls_stream = self.__stream_manager.__enter__()
                    return self

                def __exit__(self, exc_type, exc_val, exc_tb):
                    self.__stream_manager.__exit__(exc_type, exc_val, exc_tb)
                    try:
                        result = self.__ls_stream.get_final_response()
                        outputs = {}

                        if hasattr(result, "model_dump"):
                            result_dict = result.model_dump(mode="json")

                            # Extract usage data if available
                            if hasattr(result, "usage") and result.usage:
                                usage_data = result.usage.model_dump()
                                usage_metadata = _create_usage_metadata(usage_data)
                                outputs["usage_metadata"] = usage_metadata

                            outputs.update(
                                {
                                    "output": result_dict.get("output") or {},
                                    "events": self.__events,
                                }
                            )

                        self._ls_run.add_outputs(outputs)
                    except Exception as e:
                        logger.warning(f"Error getting final output: {e}")
                    trace_ctx.__exit__(exc_type, exc_val, exc_tb)

                def __iter__(self):
                    for chunk in self.__ls_stream:
                        self.__events.append(chunk)
                        yield chunk

                def __next__(self):
                    event = self.__ls_stream.__next__()
                    self.__events.append(event)
                    return event

                def close(self):
                    self.__ls_stream.close()

                def get_final_response(self):
                    return self.__ls_stream.get_final_response()

                def until_done(self):
                    self.__ls_stream.until_done()
                    return self

            return ProxyContextManager(manager)

        return wrapped_stream


def _reduce_response(events: List[ResponseStreamEvent]) -> dict:
    output_text = []
    for event in events:
        if event.type == "response.output_text.done":
            output_text.append(event.text)
    return {"output_text": "".join(output_text), "events": events}


class TracingExtra(TypedDict, total=False):
    metadata: Optional[Mapping[str, Any]]
    tags: Optional[List[str]]
    client: Optional[ls_client.Client]


def wrap_openai(
    client: C,
    *,
    tracing_extra: Optional[TracingExtra] = None,
    chat_name: str = "ChatOpenAI",
    completions_name: str = "OpenAI",
) -> C:
    """Patch the OpenAI client to make it traceable.

    Args:
        client (Union[OpenAI, AsyncOpenAI]): The client to patch.
        tracing_extra (Optional[TracingExtra], optional): Extra tracing information.
            Defaults to None.
        chat_name (str, optional): The run name for the chat completions endpoint.
            Defaults to "ChatOpenAI".
        completions_name (str, optional): The run name for the completions endpoint.
            Defaults to "OpenAI".

    Returns:
        Union[OpenAI, AsyncOpenAI]: The patched client.

    Example:

        .. code-block:: python

            import openai
            from langsmith import wrappers

            client = wrappers.wrap_openai(openai.OpenAI())

            # Use OpenAI client same as you normally would:
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

            # You can also use the streaming context manager:
            with client.chat.completions.stream(
                model="gpt-4o-mini",
                messages=messages,
            ) as stream:
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        print(chunk.choices[0].delta.content, end="", flush=True)

    """  # noqa: E501
    tracing_extra = tracing_extra or {}
    # Store original stream methods if they exist
    original_chat_stream = getattr(client.chat.completions, "stream", None)
    original_completions_stream = getattr(client.completions, "stream", None)
    original_responses_stream = None
    if hasattr(client, "responses") and hasattr(client.responses, "stream"):
        original_responses_stream = client.responses.stream

    # First wrap the create methods - these handle non-streaming cases
    client.chat.completions.create = _get_wrapper(  # type: ignore[method-assign]
        client.chat.completions.create,
        chat_name,
        _reduce_chat,
        tracing_extra=tracing_extra,
        invocation_params_fn=functools.partial(_infer_invocation_params, "chat"),
        process_outputs=_process_chat_completion,
    )

    client.completions.create = _get_wrapper(  # type: ignore[method-assign]
        client.completions.create,
        completions_name,
        _reduce_completions,
        tracing_extra=tracing_extra,
        invocation_params_fn=functools.partial(_infer_invocation_params, "llm"),
    )

    # Now wrap streaming methods if they exist
    if original_chat_stream:
        client.chat.completions.stream = _get_stream_wrapper(  # type: ignore[method-assign]
            original_chat_stream,
            chat_name,
            tracing_extra=tracing_extra,
            invocation_params_fn=functools.partial(_infer_invocation_params, "chat"),
        )

    if original_completions_stream:
        client.completions.stream = _get_stream_wrapper(  # type: ignore[method-assign]
            original_completions_stream,
            completions_name,
            tracing_extra=tracing_extra,
            invocation_params_fn=functools.partial(_infer_invocation_params, "llm"),
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
            tracing_extra=tracing_extra,
            invocation_params_fn=functools.partial(_infer_invocation_params, "chat"),
        )

    # For the responses API: "client.responses.create(**kwargs)"
    if hasattr(client, "responses"):

        def process_outputs(response: Any):
            if response:
                try:
                    return {
                        "output_text": response.output_text,
                        "message": (
                            response.output.content[0].text
                            if hasattr(response, "output")
                            and hasattr(response.output, "content")
                            else ""
                        ),
                        **response.model_dump(mode="json"),
                    }
                except Exception:
                    return {"output": response}
            return {}

        if hasattr(client.responses, "create"):
            client.responses.create = _get_wrapper(  # type: ignore[method-assign]
                client.responses.create,
                "openai.responses.create",
                _reduce_response,
                process_outputs=process_outputs,
                tracing_extra=tracing_extra,
                invocation_params_fn=functools.partial(
                    _infer_invocation_params, "chat"
                ),
            )
        if hasattr(client.responses, "parse"):
            client.responses.parse = _get_parse_wrapper(  # type: ignore[method-assign]
                client.responses.parse,
                "openai.responses.parse",
                tracing_extra=tracing_extra,
                invocation_params_fn=functools.partial(
                    _infer_invocation_params, "chat"
                ),
            )
        if original_responses_stream:
            client.responses.stream = _get_stream_wrapper(  # type: ignore[method-assign]
                original_responses_stream,
                "openai.responses.stream",
                tracing_extra=tracing_extra,
                invocation_params_fn=functools.partial(
                    _infer_invocation_params, "chat"
                ),
            )

    return client
