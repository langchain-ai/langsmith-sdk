from __future__ import annotations

import functools
import logging
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    List,
    Mapping,
    Optional,
    Type,
    TypeVar,
    Union,
)

from typing_extensions import TypedDict
from pydantic import TypeAdapter
from contextlib import contextmanager, asynccontextmanager

from langsmith import client as ls_client
from langsmith import run_helpers
from langsmith.schemas import InputTokenDetails, UsageMetadata

if TYPE_CHECKING:
    from anthropic import Anthropic, AsyncAnthropic
    from anthropic.types import (
        Completion,
        Message,
        MessageStreamEvent
    )

C = TypeVar("C", bound=Union["Anthropic", "AsyncAnthropic", Any])
logger = logging.getLogger(__name__)


@functools.lru_cache
def _get_not_given() -> Optional[Type]:
    try:
        from anthropic._types import NotGiven

        return NotGiven
    except ImportError:
        return None


def _strip_not_given(d: dict) -> dict:
    if 'system' in d:
        d['messages'] = [{"role": "system", "content": d['system']}] + d.get('messages', [])
        d.pop('system')
    try:
        not_given = _get_not_given()
        if not_given is None:
            return d
        return {k: v for k, v in d.items() if not isinstance(v, not_given)}
    except Exception as e:
        logger.error(f"Error stripping NotGiven: {e}")
        return d


def _accumulate_event(
    *, event: MessageStreamEvent, current_snapshot: Message | None
) -> Message | None:
    try:
        from anthropic.types import ContentBlock
    except ImportError:
        logger.debug("Error importing ContentBlock")
        return current_snapshot

    if current_snapshot is None:
        if event.type == "message_start":
            return event.message

        raise RuntimeError(
            f'Unexpected event order, got {event.type} before "message_start"'
        )

    if event.type == "content_block_start":
        # TODO: check index <-- from anthropic SDK :)
        adapter = TypeAdapter(ContentBlock)
        content_block_instance = adapter.validate_python(event.content_block.model_dump())
        current_snapshot.content.append(
            content_block_instance,  # type: ignore[attr-defined]
        )
    elif event.type == "content_block_delta":
        content = current_snapshot.content[event.index]
        if content.type == "text" and event.delta.type == "text_delta":
            content.text += event.delta.text
    elif event.type == "message_delta":
        current_snapshot.stop_reason = event.delta.stop_reason
        current_snapshot.stop_sequence = event.delta.stop_sequence
        current_snapshot.usage.output_tokens = event.usage.output_tokens

    return current_snapshot


def _reduce_chat(all_chunks: List) -> dict:
    full_message = None
    for chunk in all_chunks:
        try:
            full_message = _accumulate_event(event=chunk, current_snapshot=full_message)
        except RuntimeError as e:
            logger.debug(f"Error accumulating event in Anthropic Wrapper: {e}")
            return {"output": all_chunks}
    if full_message is None:
        return {"output": all_chunks}
    d = full_message.model_dump()
    d['usage_metadata'] = _create_usage_metadata(d.get("usage", {}))
    d.pop("usage")
    return d


def _create_usage_metadata(anthropic_token_usage: dict) -> UsageMetadata:
    input_tokens = anthropic_token_usage.get("input_tokens") or 0
    output_tokens = anthropic_token_usage.get("output_tokens") or 0
    total_tokens = input_tokens + output_tokens
    input_token_details: dict = {
        "cache_read": anthropic_token_usage.get("cache_creation_input_tokens", 0) + 
            anthropic_token_usage.get("cache_read_input_tokens", 0)
    }
    return UsageMetadata(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        input_token_details=InputTokenDetails(
            **{k: v for k, v in input_token_details.items() if v is not None}
        ),
    )


def _reduce_completions(all_chunks: List[Completion]) -> dict:
    all_content = []
    for chunk in all_chunks:
        content = chunk.completion
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
        rdict = outputs.model_dump()
        anthropic_token_usage = rdict.pop("usage", None)
        rdict["usage_metadata"] = (
            _create_usage_metadata(anthropic_token_usage) if anthropic_token_usage else None
        )
        return rdict
    except BaseException as e:
        logger.debug(f"Error processing chat completion: {e}")
        return {"output": outputs}

def _get_wrapper(
    original_create: Callable,
    name: str,
    reduce_fn: Optional[Callable] = None,
    tracing_extra: Optional[TracingExtra] = None,
    force_stream: bool = False,
) -> Callable:
    textra = tracing_extra or {}

    @functools.wraps(original_create)
    def create(*args, **kwargs):
        stream = kwargs.get("stream", False)
        decorator = run_helpers.traceable(
            name=name,
            run_type="llm",
            reduce_fn=reduce_fn if force_stream or stream else None,
            process_inputs=_strip_not_given,
            process_outputs=_process_chat_completion,
            **textra,
        )

        result = decorator(original_create)(*args, **kwargs)
        return result

    @functools.wraps(original_create)
    async def acreate(*args, **kwargs):
        stream = kwargs.get("stream", False)
        decorator = run_helpers.traceable(
            name=name,
            run_type="llm",
            reduce_fn=reduce_fn if force_stream or stream else None,
            process_inputs=_strip_not_given,
            process_outputs=_process_chat_completion,
            **textra,
        )
        result = await decorator(original_create)(*args, **kwargs)
        return result

    return acreate if run_helpers.is_async(original_create) else create

def _get_stream_wrapper(
    original_stream: Callable,
    name: str,
    tracing_extra: Optional[TracingExtra] = None,
) -> Callable:
    """Creates a wrapper for Anthropic's streaming context manager."""
    textra = tracing_extra or {}
    is_async = 'async' in str(original_stream).lower()

    if is_async:
        class AsyncWrapperManager:
            def __init__(self, *args2, **kwargs2):
                self.args = args2
                self.kwargs = kwargs2

            async def __aenter__(self):
                self._context = await original_stream(*self.args, **self.kwargs).__aenter__()
                return self

            async def __aexit__(self, *exc):
                await self._context.__aexit__(*exc)

            async def __aiter__(self):
                trace_kwargs = self.kwargs.copy()
                if "system" in trace_kwargs:
                    trace_kwargs['messages'] = [{"role": "system", "content": trace_kwargs.pop("system")}] + trace_kwargs['messages']
                
                @run_helpers.traceable(name=name, reduce_fn=_reduce_chat, run_type="llm")
                async def stream_generator(*args3, **kwargs3):
                    async for chunk in self._context:
                        yield chunk
                
                async for chunk in stream_generator(*self.args, **trace_kwargs):
                    yield chunk

            @property
            def _raw_stream(self):
                return self.__aiter__()

            @property
            def text_stream(self):
                trace_kwargs = self.kwargs.copy()
                if "system" in trace_kwargs:
                    trace_kwargs['messages'] = [{"role": "system", "content": trace_kwargs.pop("system")}] + trace_kwargs['messages']
                
                @run_helpers.traceable(name=name, run_type="llm", reduce_fn=lambda x: ''.join(x))
                async def text_stream_generator(*args3, **kwargs3):
                    async for chunk in self._context.text_stream:
                        yield chunk
                    run_tree = run_helpers.get_current_run_tree()
                    final_message = await self._context.get_final_message()
                    run_tree.add_outputs(
                        {"usage_metadata": _create_usage_metadata(final_message.usage.model_dump())}
                    )

                
                return text_stream_generator(*self.args, **trace_kwargs)

        return AsyncWrapperManager
    else:
        class WrapperManager:
            def __init__(self, *args2, **kwargs2):
                self.args = args2
                self.kwargs = kwargs2

            def __enter__(self):
                self._context = original_stream(*self.args, **self.kwargs).__enter__()
                return self

            def __exit__(self, *exc):
                self._context.__exit__(*exc)

            def __iter__(self):
                trace_kwargs = self.kwargs.copy()
                if "system" in trace_kwargs:
                    trace_kwargs['messages'] = [{"role": "system", "content": trace_kwargs.pop("system")}] + trace_kwargs['messages']
                
                @run_helpers.traceable(name=name, reduce_fn=_reduce_chat, run_type="llm")
                def stream_generator(*args3, **kwargs3):
                    for chunk in self._context:
                        yield chunk
                
                for chunk in stream_generator(*self.args, **trace_kwargs):
                    yield chunk

            @property
            def raw_stream(self):
                return self.__iter__()

            @property
            def text_stream(self):
                @run_helpers.traceable(name=name, run_type="llm", reduce_fn=lambda x: ''.join(x))
                def text_stream(*args3, **kwargs3):
                    yield from self._context.text_stream
                    run_tree = run_helpers.get_current_run_tree()
                    final_message = self._context.get_final_message()
                    run_tree.add_outputs(
                        {"usage_metadata": _create_usage_metadata(final_message.usage.model_dump())}
                    )

                trace_kwargs = self.kwargs.copy()
                if "system" in trace_kwargs:
                    trace_kwargs['messages'] = [{"role": "system", "content": trace_kwargs.pop("system")}] + trace_kwargs['messages']
                return text_stream(*self.args, **trace_kwargs)

        return WrapperManager

class TracingExtra(TypedDict, total=False):
    metadata: Optional[Mapping[str, Any]]
    tags: Optional[List[str]]
    client: Optional[ls_client.Client]


def wrap_anthropic(client: C, *, tracing_extra: Optional[TracingExtra] = None) -> C:
    """Patch the Anthropic client to make it traceable.

    Args:
        client (Union[Anthropic, AsyncAnthropic]): The client to patch.
        tracing_extra (Optional[TracingExtra], optional): Extra tracing information.
            Defaults to None.

    Returns:
        Union[Anthropic, AsyncAnthropic]: The patched client.

    Example:

        .. code-block:: python

            import anthropic
            from langsmith import wrappers

            client = wrappers.wrap_anthropic(anthropic.Anthropic())

            # Use Anthropic client same as you normally would:
            system = "You are a helpful assistant."
            messages = [
                {
                    "role": "user",
                    "content": "What physics breakthroughs do you predict will happen by 2300?",
                }
            ]
            completion = client.messages.create(
                model="claude-3-5-sonnet-latest",
                messages=messages,
                max_tokens=1000,
                system=system,
            )
            print(completion.content)

            # You can also use the streaming context manager:
            with client.messages.stream(
                model="claude-3-5-sonnet-latest",
                messages=messages,
                max_tokens=1000,
                system=system,
            ) as stream:
                for text in stream.text_stream:
                    print(text, end="", flush=True)
                message = stream.get_final_message()

    """  # noqa: E501
    client.messages.create = _get_wrapper(  # type: ignore[method-assign]
        client.messages.create,
        "ChatAnthropic",
        _reduce_chat,
        tracing_extra=tracing_extra,
    )
    # Use the stream-specific wrapper for the context manager-based stream method
    client.messages.stream = _get_stream_wrapper(  # type: ignore[method-assign]
        client.messages.stream,
        "ChatAnthropic",
        tracing_extra=tracing_extra,
    )
    client.completions.create = _get_wrapper(  # type: ignore[method-assign]
        client.completions.create,
        "Anthropic",
        _reduce_completions,
        tracing_extra=tracing_extra,
    )

    if (
        hasattr(client, "beta")
        and hasattr(client.beta, "messages")
        and hasattr(client.beta.messages, "create")
    ):
        client.beta.messages.create = _get_wrapper(  # type: ignore[method-assign]
            client.beta.messages.create,  # type: ignore
            "Anthropic",
            tracing_extra=tracing_extra,
        )
    return client
