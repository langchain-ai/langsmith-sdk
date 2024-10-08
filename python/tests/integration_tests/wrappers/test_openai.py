# mypy: disable-error-code="attr-defined, union-attr, arg-type, call-overload"
import asyncio
import json
import time
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

import langsmith
from langsmith.wrappers import wrap_openai


@mock.patch("langsmith.client.requests.Session")
@pytest.mark.parametrize("stream", [False, True])
def test_completions_sync_api(mock_session: mock.MagicMock, stream: bool):
    import openai

    client = langsmith.Client(session=mock_session())
    original_client = openai.Client()
    patched_client = wrap_openai(openai.Client(), tracing_extra={"client": client})
    prompt = ("Say 'Foo' then stop.",)
    original = original_client.completions.create(
        model="gpt-3.5-turbo-instruct",
        prompt=prompt,
        max_tokens=3,
        temperature=0,
        seed=42,
        stream=stream,
    )
    patched = patched_client.completions.create(
        model="gpt-3.5-turbo-instruct",
        prompt=prompt,
        max_tokens=3,
        temperature=0,
        seed=42,
        stream=stream,
    )
    if stream:
        # We currently return a generator, so
        # the types aren't the same.
        original_chunks = list(original)
        patched_chunks = list(patched)
        assert len(original_chunks) == len(patched_chunks)
        assert [o.choices == p.choices for o, p in zip(original_chunks, patched_chunks)]
        assert original.response
        assert patched.response
    else:
        assert type(original) == type(patched)
        assert original.choices == patched.choices
    # Give the thread a chance.
    time.sleep(0.1)
    for call in mock_session.return_value.request.call_args_list[1:]:
        assert call[0][0].upper() == "POST"


@mock.patch("langsmith.client.requests.Session")
@pytest.mark.parametrize("stream", [False, True])
async def test_completions_async_api(mock_session: mock.MagicMock, stream: bool):
    import openai

    client = langsmith.Client(session=mock_session())

    original_client = openai.AsyncClient()
    patched_client = wrap_openai(
        openai.AsyncClient(),
        tracing_extra={"client": client},
        chat_name="chattychat",
        completions_name="incompletions",
    )
    prompt = ("Say 'Hi i'm ChatGPT' then stop.",)
    original = await original_client.completions.create(
        model="gpt-3.5-turbo-instruct",
        prompt=prompt,
        max_tokens=5,
        temperature=0,
        seed=42,
        stream=stream,
    )
    patched = await patched_client.completions.create(
        model="gpt-3.5-turbo-instruct",
        prompt=prompt,
        max_tokens=5,
        temperature=0,
        seed=42,
        stream=stream,
    )
    if stream:
        # We currently return a generator, so
        # the types aren't the same.
        original_chunks = []
        async for chunk in original:
            original_chunks.append(chunk)
        patched_chunks = []
        async for chunk in patched:
            patched_chunks.append(chunk)
        assert len(original_chunks) == len(patched_chunks)
        assert [o.choices == p.choices for o, p in zip(original_chunks, patched_chunks)]
        assert original.response
        assert patched.response
    else:
        assert type(original) == type(patched)
        assert original.choices == patched.choices
    # Give the thread a chance.
    for _ in range(10):
        time.sleep(0.1)
        if mock_session.return_value.request.call_count >= 1:
            break
    assert mock_session.return_value.request.call_count >= 1
    for call in mock_session.return_value.request.call_args_list[1:]:
        assert call[0][0].upper() == "POST"


class Collect:
    """
    Collects the runs for inspection.
    """

    def __init__(self):
        self.run = None

    def __call__(self, run):
        self.run = run


def _collect_requests(mock_session: mock.MagicMock, filename: str):
    dir_path = Path(__file__).resolve().parent.parent / "test_data"
    file_path = dir_path / f"{filename}.json"
    all_requests = []
    for call in mock_session.return_value.request.call_args_list:
        json_bytes = call.kwargs.get("data")
        if json_bytes:
            json_str = json_bytes.decode("utf-8")
            data_dict = json.loads(json_str)
            all_requests.append(data_dict)

    with open(file_path, "w") as f:
        json.dump(all_requests, f, indent=2)
    mock_session.return_value.request.call_args_list.clear()


test_cases = [
    {
        "description": "stream usage",
        "params": {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "howdy"}],
            "stream": True,
            "stream_options": {"include_usage": True},
        },
        "expect_usage_metadata": True,
    },
    {
        "description": "stream no usage",
        "params": {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "howdy"}],
            "stream": True,
        },
        "expect_usage_metadata": False,
    },
    {
        "description": "non-stream usage",
        "params": {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "howdy"}],
        },
        "expect_usage_metadata": True,
    },
    {
        "description": "complex usage",
        "params": {
            "model": "o1-mini",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Write a bash script that takes a matrix represented "
                        "as a string with format '[1,2],[3,4],[5,6]' and prints the "
                        "transpose in the same format."
                    ),
                }
            ],
        },
        "expect_usage_metadata": True,
        "check_reasoning_tokens": True,
    },
]


@pytest.mark.parametrize("test_case", test_cases)
@mock.patch("langsmith.client.requests.Session")
def test_wrap_openai_chat(mock_session: mock.MagicMock, test_case):
    import openai
    from openai.types.chat import ChatCompletion, ChatCompletionChunk

    oai_client = openai.Client()
    ls_client = langsmith.Client(session=mock_session())
    wrapped_oai_client = wrap_openai(oai_client, tracing_extra={"client": ls_client})

    collect = Collect()
    run_id_to_usage_metadata = {}
    with langsmith.tracing_context(enabled=True):
        params: dict[str, Any] = test_case["params"].copy()
        params["langsmith_extra"] = {"on_end": collect}
        res = wrapped_oai_client.chat.completions.create(**params)

        if params.get("stream"):
            for chunk in res:
                assert isinstance(chunk, ChatCompletionChunk)
                if test_case.get("expect_usage_metadata") and hasattr(chunk, "usage"):
                    oai_usage = chunk.usage
        else:
            assert isinstance(res, ChatCompletion)
            oai_usage = res.usage

        if test_case["expect_usage_metadata"]:
            usage_metadata = collect.run.outputs["usage_metadata"]
            assert usage_metadata["input_tokens"] == oai_usage.prompt_tokens
            assert usage_metadata["output_tokens"] == oai_usage.completion_tokens
            assert usage_metadata["total_tokens"] == oai_usage.total_tokens
            if test_case.get("check_reasoning_tokens"):
                assert (
                    usage_metadata["output_token_details"]["reasoning"]
                    == oai_usage.completion_tokens_details.reasoning_tokens
                )
        else:
            assert collect.run.outputs.get("usage_metadata") is None
            assert collect.run.outputs.get("usage") is None

        run_id_to_usage_metadata[collect.run.id] = collect.run.outputs.get(
            "usage_metadata"
        )

    time.sleep(0.1)
    filename = f"wrap_openai_chat_{test_case['description'].replace(' ', '_')}"
    _collect_requests(mock_session, filename)


@pytest.mark.asyncio
@pytest.mark.parametrize("test_case", test_cases)
@mock.patch("langsmith.client.requests.Session")
async def test_wrap_openai_chat_async(mock_session: mock.MagicMock, test_case):
    import openai
    from openai.types.chat import ChatCompletion, ChatCompletionChunk

    oai_client = openai.AsyncClient()
    ls_client = langsmith.Client(session=mock_session())
    wrapped_oai_client = wrap_openai(oai_client, tracing_extra={"client": ls_client})

    collect = Collect()
    run_id_to_usage_metadata = {}
    with langsmith.tracing_context(enabled=True):
        params: dict[str, Any] = test_case["params"].copy()
        params["langsmith_extra"] = {"on_end": collect}
        res = await wrapped_oai_client.chat.completions.create(**params)

        if params.get("stream"):
            oai_usage = None
            async for chunk in res:
                assert isinstance(chunk, ChatCompletionChunk)
                if test_case.get("expect_usage_metadata") and hasattr(chunk, "usage"):
                    oai_usage = chunk.usage
        else:
            assert isinstance(res, ChatCompletion)
            oai_usage = res.usage

        if test_case["expect_usage_metadata"]:
            usage_metadata = collect.run.outputs["usage_metadata"]
            assert usage_metadata["input_tokens"] == oai_usage.prompt_tokens
            assert usage_metadata["output_tokens"] == oai_usage.completion_tokens
            assert usage_metadata["total_tokens"] == oai_usage.total_tokens
            if test_case.get("check_reasoning_tokens"):
                assert (
                    usage_metadata["output_token_details"]["reasoning"]
                    == oai_usage.completion_tokens_details.reasoning_tokens
                )
        else:
            assert collect.run.outputs.get("usage_metadata") is None
            assert collect.run.outputs.get("usage") is None

        run_id_to_usage_metadata[collect.run.id] = collect.run.outputs.get(
            "usage_metadata"
        )

    await asyncio.sleep(0.1)
    filename = f"wrap_openai_chat_async_{test_case['description'].replace(' ', '_')}"
    _collect_requests(mock_session, filename)
