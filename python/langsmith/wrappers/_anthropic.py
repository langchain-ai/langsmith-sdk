from __future__ import annotations

import functools
import logging
from collections import defaultdict
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    DefaultDict,
    Dict,
    List,
    Mapping,
    Optional,
    Type,
    TypeVar,
    Union,
)

from anthropic import MessageStreamEvent, Stream, TextEvent
from typing_extensions import TypedDict

from langsmith import client as ls_client
from langsmith import run_helpers

if TYPE_CHECKING:
    from anthropic import Anthropic, AsyncAnthropic
    from anthropic.types import RawContentBlockDeltaEvent, TextDelta

# Any is used since it may work with Azure or other providers
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
    try:
        not_given = _get_not_given()
        if not_given is None:
            return d
        return {k: v for k, v in d.items() if not isinstance(v, not_given)}
    except Exception as e:
        logger.error(f"Error stripping NotGiven: {e}")
        return d


def _infer_invocation_params(model_type: str, kwargs: dict):
    stripped = _strip_not_given(kwargs)

    stop = stripped.get("stop")
    if stop and isinstance(stop, str):
        stop = [stop]

    return {
        "ls_provider": "anthropic",
        "ls_model_type": model_type,
        "ls_model_name": stripped.get("model", None),
        "ls_temperature": stripped.get("temperature", None),
        "ls_max_tokens": stripped.get("max_tokens", None),
        "ls_stop": stop,
    }


def _reduce_events(events: Stream[MessageStreamEvent]) -> dict:
    text = ""
    for event in events:
        if event.type == "content_block_delta" and event.delta.type == "text_delta":
            text += event.delta.text

    return {
        "text": text,
    }


def _get_wrapper(
    original_create: Callable,
    name: str,
    reduce_fn: Callable,
    tracing_extra: Optional[TracingExtra] = None,
    invocation_params_fn: Optional[Callable] = None,
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
            **textra,
        )
        if stream:
            # TODO: This slightly alters the output to be a generator instead of the
            # stream object. We can probably fix this with a bit of simple changes
            res = decorator(original_create)(*args, stream=stream, **kwargs)
            return res
        return await decorator(original_create)(*args, stream=stream, **kwargs)

    return acreate if run_helpers.is_async(original_create) else create


class TracingExtra(TypedDict, total=False):
    metadata: Optional[Mapping[str, Any]]
    tags: Optional[List[str]]
    client: Optional[ls_client.Client]


def wrap_anthropic(
    client: C,
    *,
    tracing_extra: Optional[TracingExtra] = None,
    chat_name: str = "ChatAnthropic",
) -> C:
    """Patch the Anthropic client to make it traceable.

    Args:
        client (Union[Anthropic, AsyncAnthropic]): The client to patch.
        tracing_extra (Optional[TracingExtra], optional): Extra tracing information.
            Defaults to None.
        chat_name (str, optional): The run name for the chat completions endpoint.
            Defaults to "ChatAnthropic".
        completions_name (str, optional): The run name for the completions endpoint.
            Defaults to "Anthropic".

    Returns:
        Union[Anthropic, AsyncAnthropic]: The patched client.

    """
    client.messages.create = _get_wrapper(  # type: ignore[method-assign]
        client.messages.create,
        chat_name,
        _reduce_events,
        tracing_extra=tracing_extra,
        invocation_params_fn=functools.partial(_infer_invocation_params, "chat"),
    )
    return client
