from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Generator, List, TypeVar, Union
import functools

import langsmith
from langsmith import run_helpers

if TYPE_CHECKING:
    from openai import AsyncOpenAI, OpenAI
    from openai.types.chat.chat_completion_chunk import (
        ChatCompletionChunk,
    )

C = TypeVar("C", bound=Union["OpenAI", "AsyncOpenAI"])


def _reduce_chat(all_chunks: List[ChatCompletionChunk]):
    all_content = []
    for chunk in all_chunks:
        content = chunk.choices[0].delta.content
        if content is not None:
            all_content.append(content)
    content = "".join(all_content)
    if all_chunks:
        d = all_chunks[-1].model_dump()
        d["choices"] = [{"message": {"role": "assistant", "content": content}}]
    else:
        d = {"choices": [{"message": {"role": "assistant", "content": content}}]}

    return d


def _get_wrapper(original_create: Callable, name: str, reduce_fn: Callable) -> Callable:
    @functools.wraps(original_create)
    def create(*args, stream: bool = False, **kwargs):
        decorator = run_helpers.traceable(
            name=name, run_type="llm", reduce_fn=reduce_fn if stream else None
        )

        return decorator(original_create)(*args, stream=stream, **kwargs)

    @functools.wraps(original_create)
    async def acreate(*args, stream: bool = False, **kwargs):
        decorator = run_helpers.traceable(
            name=name, run_type="llm", reduce_fn=reduce_fn if stream else None
        )
        if stream:
            res = await original_create(
                *args, stream=stream, **kwargs
            )  # decorator(original_create)(*args, stream=stream, **kwargs)
            return await res
        return await decorator(original_create)(*args, stream=stream, **kwargs)

    return acreate if run_helpers.is_async(original_create) else create


def patch_openai(client: C) -> C:
    """Patch the OpenAI client to make it traceable.

    Args:
        client (Union[OpenAI, AsyncOpenAI]): The client to patch.

    Returns:
        Union[OpenAI, AsyncOpenAI]: The patched client.

    """

    # TODO: this is actually broken for async streaming
    client.chat.completions.create = _get_wrapper(
        client.chat.completions.create, "ChatOpenAI", _reduce_chat
    )
    client.completions.create = _get_wrapper(client.completions.create, "OpenAI", None)
    return client
