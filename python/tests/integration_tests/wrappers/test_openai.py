# mypy: disable-error-code="attr-defined, union-attr, arg-type, call-overload"
import json
import os
import time
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from pydantic import BaseModel

import langsmith
from langsmith.wrappers import wrap_openai


@pytest.mark.parametrize("stream", [False, True])
def test_chat_sync_api(stream: bool):
    import openai  # noqa

    mock_session = mock.MagicMock()
    client = langsmith.Client(session=mock_session)
    original_client = openai.Client()
    patched_client = wrap_openai(openai.Client(), tracing_extra={"client": client})
    messages = [{"role": "user", "content": "Say 'foo'"}]
    original = original_client.chat.completions.create(
        messages=messages,
        stream=stream,
        temperature=0,
        seed=42,
        model="gpt-3.5-turbo",
    )
    patched = patched_client.chat.completions.create(
        messages=messages,
        stream=stream,
        temperature=0,
        seed=42,
        model="gpt-3.5-turbo",
    )
    if stream:
        # We currently return a generator, so
        # the types aren't the same.
        original_chunks = list(original)
        patched_chunks = list(patched)
        assert len(original_chunks) == len(patched_chunks)
        assert [o.choices == p.choices for o, p in zip(original_chunks, patched_chunks)]
    else:
        assert type(original) is type(patched)
        assert original.choices == patched.choices
    # Give the thread a chance.
    time.sleep(0.01)
    for call in mock_session.request.call_args_list[1:]:
        assert call[0][0].upper() == "POST"


@pytest.mark.parametrize("stream", [False, True])
async def test_chat_async_api(stream: bool):
    import openai  # noqa

    mock_session = mock.MagicMock()
    client = langsmith.Client(session=mock_session)
    original_client = openai.AsyncClient()
    patched_client = wrap_openai(openai.AsyncClient(), tracing_extra={"client": client})
    messages = [{"role": "user", "content": "Say 'foo'"}]
    original = await original_client.chat.completions.create(
        messages=messages, stream=stream, temperature=0, seed=42, model="gpt-3.5-turbo"
    )
    patched = await patched_client.chat.completions.create(
        messages=messages, stream=stream, temperature=0, seed=42, model="gpt-3.5-turbo"
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
    else:
        assert type(original) is type(patched)
        assert original.choices == patched.choices
    # Give the thread a chance.
    time.sleep(0.1)
    for call in mock_session.request.call_args_list[1:]:
        assert call[0][0].upper() == "POST"


@pytest.mark.parametrize("stream", [False, True])
def test_completions_sync_api(stream: bool):
    import openai

    mock_session = mock.MagicMock()
    client = langsmith.Client(session=mock_session)
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
        assert type(original) is type(patched)
        assert original.choices == patched.choices
    # Give the thread a chance.
    time.sleep(0.1)
    for call in mock_session.request.call_args_list[1:]:
        assert call[0][0].upper() == "POST"


@pytest.mark.parametrize("stream", [False, True])
async def test_completions_async_api(stream: bool):
    import openai

    mock_session = mock.MagicMock()
    client = langsmith.Client(session=mock_session)

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
        assert type(original) is type(patched)
        assert original.choices == patched.choices
    # Give the thread a chance.
    for _ in range(10):
        time.sleep(0.1)
        if mock_session.request.call_count >= 1:
            break
    assert mock_session.request.call_count >= 1
    for call in mock_session.request.call_args_list[1:]:
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
    mock_requests = mock_session.request.call_args_list
    collected_requests = {}
    for _ in range(10):
        time.sleep(0.1)
        for call in mock_requests:
            if json_bytes := call.kwargs.get("data"):
                json_str = json_bytes.decode("utf-8")
                collected_requests.update(json.loads(json_str))
        all_events = [
            *collected_requests.get("post", []),
            *collected_requests.get("patch", []),
        ]
        # if end_time has been set, we can stop collecting as the background
        # thread has finished processing the run
        if any(event.get("end_time") for event in all_events):
            break
        mock_session.request.call_args_list.clear()

    if os.environ.get("WRITE_TOKEN_COUNTING_TEST_DATA") == "1":
        dir_path = Path(__file__).resolve().parent.parent / "test_data"
        file_path = dir_path / f"{filename}.json"
        with open(file_path, "w") as f:
            json.dump(collected_requests, f, indent=2)


LS_TEST_CLIENT_INFO = {
    "batch_ingest_config": {
        "use_multipart_endpoint": False,
        "scale_up_qsize_trigger": 1000,
        "scale_up_nthreads_limit": 16,
        "scale_down_nempty_trigger": 4,
        "size_limit": 100,
        "size_limit_bytes": 20971520,
    },
}


test_cases = [
    {
        "description": "stream",
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
        "description": "",
        "params": {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "howdy"}],
        },
        "expect_usage_metadata": True,
    },
    {
        "description": "reasoning",
        "params": {
            "model": "o4-mini",
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
    # just test flex as priority can randomly downgrade
    {
        "description": "flex service tier",
        "params": {
            "model": "gpt-5-nano",
            "messages": [{"role": "user", "content": "howdy"}],
            "service_tier": "flex",
        },
        "expect_usage_metadata": True,
        "check_service_tier": "flex",
    },
]


@pytest.mark.parametrize("test_case", test_cases)
def test_wrap_openai_chat_tokens(test_case):
    import openai
    from openai.types.chat import ChatCompletion, ChatCompletionChunk

    oai_client = openai.Client()
    mock_session = mock.MagicMock()
    ls_client = langsmith.Client(
        session=mock_session,
        info=LS_TEST_CLIENT_INFO,
    )
    wrapped_oai_client = wrap_openai(oai_client, tracing_extra={"client": ls_client})

    collect = Collect()
    run_id_to_usage_metadata = {}
    with langsmith.tracing_context(enabled=True):
        params: dict[str, Any] = test_case["params"].copy()
        params["langsmith_extra"] = {"on_end": collect}
        try:
            res = wrapped_oai_client.chat.completions.create(**params)
        except openai.APIConnectionError as e:
            pytest.skip("Openai is having some issues: " + str(e))

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
            if test_case.get("check_service_tier"):
                service_tier = test_case["check_service_tier"]
                assert service_tier in usage_metadata["input_token_details"]
                assert service_tier in usage_metadata["output_token_details"]
                assert usage_metadata["input_token_details"][service_tier] > 0
                assert usage_metadata["output_token_details"][service_tier] > 0
        else:
            assert collect.run.outputs.get("usage_metadata") is None
            assert collect.run.outputs.get("usage") is None

        run_id_to_usage_metadata[collect.run.id] = collect.run.outputs.get(
            "usage_metadata"
        )

    filename = f"langsmith_py_wrap_openai_{test_case['description'].replace(' ', '_')}"
    _collect_requests(mock_session, filename)


@pytest.mark.asyncio
@pytest.mark.parametrize("test_case", test_cases)
async def test_wrap_openai_chat_async_tokens(test_case):
    import openai
    from openai.types.chat import ChatCompletion, ChatCompletionChunk

    oai_client = openai.AsyncClient()
    mock_session = mock.MagicMock()
    ls_client = langsmith.Client(
        session=mock_session,
        info=LS_TEST_CLIENT_INFO,
    )
    wrapped_oai_client = wrap_openai(oai_client, tracing_extra={"client": ls_client})

    collect = Collect()
    run_id_to_usage_metadata = {}
    with langsmith.tracing_context(enabled=True):
        params: dict[str, Any] = test_case["params"].copy()
        params["langsmith_extra"] = {"on_end": collect}
        try:
            res = await wrapped_oai_client.chat.completions.create(**params)
        except openai.APIConnectionError:
            pytest.skip("Openai is having some issues.")

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
            if test_case.get("check_service_tier"):
                service_tier = test_case["check_service_tier"]
                assert service_tier in usage_metadata["input_token_details"]
                assert service_tier in usage_metadata["output_token_details"]
                assert usage_metadata["input_token_details"][service_tier] > 0
                assert usage_metadata["output_token_details"][service_tier] > 0
        else:
            assert collect.run.outputs.get("usage_metadata") is None
            assert collect.run.outputs.get("usage") is None

        run_id_to_usage_metadata[collect.run.id] = collect.run.outputs.get(
            "usage_metadata"
        )

    filename = f"langsmith_py_wrap_openai_{test_case['description'].replace(' ', '_')}"
    _collect_requests(mock_session, filename)


def test_parse_sync_api():
    """Test that the sync parse method can be traced without errors."""
    import openai  # noqa

    mock_session = mock.MagicMock()
    ls_client = langsmith.Client(
        session=mock_session,
        info=LS_TEST_CLIENT_INFO,
    )

    original_client = openai.Client()
    patched_client = wrap_openai(openai.Client(), tracing_extra={"client": ls_client})

    messages = [{"role": "user", "content": "Say 'foo' then stop."}]

    # beta parse
    original_beta = original_client.beta.chat.completions.parse(
        messages=messages, model="gpt-3.5-turbo", temperature=0, seed=42, max_tokens=3
    )
    patched_beta = patched_client.beta.chat.completions.parse(
        messages=messages, model="gpt-3.5-turbo", temperature=0, seed=42, max_tokens=3
    )
    # chat parse
    original = original_client.chat.completions.parse(
        messages=messages, model="gpt-3.5-turbo", temperature=0, seed=42, max_tokens=3
    )
    patched = patched_client.chat.completions.parse(
        messages=messages, model="gpt-3.5-turbo", temperature=0, seed=42, max_tokens=3
    )

    assert type(original_beta) is type(patched_beta)
    assert original_beta.choices == patched_beta.choices
    assert type(original) is type(patched)
    assert original.choices == patched.choices

    time.sleep(0.1)
    for call in mock_session.request.call_args_list:
        assert call[0][0].upper() in ["POST", "GET", "PATCH"]

    _collect_requests(mock_session, "test_parse_sync_api")


@pytest.mark.asyncio
async def test_parse_async_api():
    """Test that the async parse method can be traced without errors."""
    import openai  # noqa

    mock_session = mock.MagicMock()
    ls_client = langsmith.Client(
        session=mock_session,
        info=LS_TEST_CLIENT_INFO,
    )

    original_client = openai.AsyncClient()
    patched_client = wrap_openai(
        openai.AsyncClient(), tracing_extra={"client": ls_client}
    )

    messages = [{"role": "user", "content": "Say 'foo' then stop."}]

    original_beta = await original_client.beta.chat.completions.parse(
        messages=messages, model="gpt-3.5-turbo", temperature=0, seed=42, max_tokens=3
    )
    patched_beta = await patched_client.beta.chat.completions.parse(
        messages=messages, model="gpt-3.5-turbo", temperature=0, seed=42, max_tokens=3
    )
    original = await original_client.chat.completions.parse(
        messages=messages, model="gpt-3.5-turbo", temperature=0, seed=42, max_tokens=3
    )
    patched = await patched_client.chat.completions.parse(
        messages=messages, model="gpt-3.5-turbo", temperature=0, seed=42, max_tokens=3
    )

    assert type(original_beta) is type(patched_beta)
    assert original_beta.choices == patched_beta.choices
    assert original.choices == patched.choices
    assert type(original) is type(patched)

    time.sleep(0.1)
    for call in mock_session.request.call_args_list:
        assert call[0][0].upper() in ["POST", "GET", "PATCH"]

    _collect_requests(mock_session, "test_parse_async_api")


def test_parse_tokens():
    """
    Test that usage tokens are captured for parse calls
    """
    import openai
    from openai.types.chat import ChatCompletion

    mock_session = mock.MagicMock()
    ls_client = langsmith.Client(
        session=mock_session,
        info=LS_TEST_CLIENT_INFO,
    )
    wrapped_oai_client = wrap_openai(
        openai.Client(), tracing_extra={"client": ls_client}
    )

    collect = Collect()
    messages = [{"role": "user", "content": "Check usage"}]

    with langsmith.tracing_context(enabled=True):
        res = wrapped_oai_client.beta.chat.completions.parse(
            messages=messages,
            model="gpt-3.5-turbo",
            langsmith_extra={"on_end": collect},
        )
        assert isinstance(res, ChatCompletion)

    usage_metadata = collect.run.outputs.get("usage_metadata")

    if usage_metadata:
        assert usage_metadata["input_tokens"] >= 0
        assert usage_metadata["output_tokens"] >= 0
        assert usage_metadata["total_tokens"] >= 0

    time.sleep(0.1)
    for call in mock_session.request.call_args_list:
        assert call[0][0].upper() in ["POST", "GET", "PATCH"]

    _collect_requests(mock_session, "test_parse_tokens")


def test_responses_sync_api():
    """Test that the sync responses methods can be traced without errors."""
    import openai  # noqa

    mock_session = mock.MagicMock()
    ls_client = langsmith.Client(
        session=mock_session,
        info=LS_TEST_CLIENT_INFO,
    )

    original_client = openai.Client()
    patched_client = wrap_openai(openai.Client(), tracing_extra={"client": ls_client})

    # Test create
    original_create = original_client.responses.create(
        input="Say 'foo' then stop.",
        model="gpt-4o-mini",
        temperature=0,
        max_output_tokens=16,
    )
    patched_create = patched_client.responses.create(
        input="Say 'foo' then stop.",
        model="gpt-4o-mini",
        temperature=0,
        max_output_tokens=16,
    )
    assert type(original_create) is type(patched_create)
    assert original_create.output_text.lower().strip(
        " ."
    ) == patched_create.output_text.lower().strip(" .")

    # Test create(stream=True)
    original_create_stream = original_client.responses.create(
        input="Say 'foo' then stop.",
        model="gpt-4o-mini",
        temperature=0,
        max_output_tokens=16,
        stream=True,
    )
    patched_create_stream = patched_client.responses.create(
        input="Say 'foo' then stop.",
        model="gpt-4o-mini",
        temperature=0,
        max_output_tokens=16,
        stream=True,
    )
    originals, patched = [], []
    for original_event, patched_event in zip(
        original_create_stream, patched_create_stream
    ):
        originals.append(original_event)
        patched.append(patched_event)
    assert len(originals) == len(patched)

    class Format(BaseModel):
        speech: str

    # Test parse
    original_parse = original_client.responses.parse(
        input="Say 'foo' then stop.",
        model="gpt-4o-mini",
        temperature=0,
        max_output_tokens=32,
        text_format=Format,
    )
    patched_parse = patched_client.responses.parse(
        input="Say 'foo' then stop.",
        model="gpt-4o-mini",
        temperature=0,
        max_output_tokens=32,
        text_format=Format,
    )

    assert isinstance(original_parse.output[0].content[0].parsed, Format)
    assert isinstance(patched_parse.output[0].content[0].parsed, Format)
    assert (
        original_parse.output[0].content[0].parsed
        == patched_parse.output[0].content[0].parsed
    )

    time.sleep(0.1)
    for call in mock_session.request.call_args_list:
        assert call[0][0].upper() in ["POST", "GET", "PATCH"]

    _collect_requests(mock_session, "test_responses_sync_api")


@pytest.mark.asyncio
async def test_responses_async_api():
    """Test that the async responses methods can be traced without errors."""
    import openai  # noqa

    mock_session = mock.MagicMock()
    ls_client = langsmith.Client(
        session=mock_session,
        info=LS_TEST_CLIENT_INFO,
    )

    original_client = openai.AsyncClient()
    patched_client = wrap_openai(
        openai.AsyncClient(), tracing_extra={"client": ls_client}
    )

    # Test create
    original_create = await original_client.responses.create(
        input="Say 'foo' then stop.",
        model="gpt-4o-mini",
        temperature=0,
        max_output_tokens=16,
    )
    patched_create = await patched_client.responses.create(
        input="Say 'foo' then stop.",
        model="gpt-4o-mini",
        temperature=0,
        max_output_tokens=16,
    )
    assert type(original_create) is type(patched_create)
    assert original_create.output_text.lower().strip(
        " ."
    ) == patched_create.output_text.lower().strip(" .")

    # Test stream
    original_stream = await original_client.responses.create(
        input="Say 'foo' then stop.",
        model="gpt-4o-mini",
        stream=True,
        temperature=0,
        max_output_tokens=16,
    )
    patched_stream = await patched_client.responses.create(
        input="Say 'foo' then stop.",
        model="gpt-4o-mini",
        stream=True,
        temperature=0,
        max_output_tokens=16,
    )
    original_chunks = []
    async for chunk in original_stream:
        original_chunks.append(chunk)
    patched_chunks = []
    async for chunk in patched_stream:
        patched_chunks.append(chunk)
    assert len(original_chunks) == len(patched_chunks)
    for orig, patched in zip(original_chunks, patched_chunks):
        assert orig.type == patched.type

    # Test parse
    class Format(BaseModel):
        speech: str

    # Test parse
    original_parse = await original_client.responses.parse(
        input="Say 'foo' then stop.",
        model="gpt-4o-mini",
        temperature=0,
        max_output_tokens=1024,
        text_format=Format,
    )
    patched_parse = await patched_client.responses.parse(
        input="Say 'foo' then stop.",
        model="gpt-4o-mini",
        temperature=0,
        max_output_tokens=1024,
        text_format=Format,
    )

    assert isinstance(original_parse.output[0].content[0].parsed, Format)
    assert isinstance(patched_parse.output[0].content[0].parsed, Format)
    assert (
        original_parse.output[0].content[0].parsed
        == patched_parse.output[0].content[0].parsed
    )

    time.sleep(0.1)
    for call in mock_session.request.call_args_list:
        assert call[0][0].upper() in ["POST", "GET", "PATCH"]

    _collect_requests(mock_session, "test_responses_sync_api")


def test_responses_stream_sync_api():
    """Test that the sync responses methods can be traced without errors."""
    import openai  # noqa

    mock_session = mock.MagicMock()
    ls_client = langsmith.Client(
        session=mock_session,
        info=LS_TEST_CLIENT_INFO,
    )
    original_client = openai.Client()
    patched_client = wrap_openai(openai.Client(), tracing_extra={"client": ls_client})

    # Test stream
    with original_client.responses.stream(
        input="Say 'foo' then stop.",
        model="gpt-5-nano",
        max_output_tokens=1024,
    ) as original_stream:
        for _ in original_stream:
            pass
        original_full = original_stream.get_final_response()
    with patched_client.responses.stream(
        input="Say 'foo' then stop.",
        model="gpt-5-nano",
        max_output_tokens=1024,
    ) as patched_stream:
        for _ in patched_stream:
            pass
        patched_full = patched_stream.get_final_response()
    original_chunks = list(original_stream)
    patched_chunks = list(patched_stream)
    assert len(original_chunks) == len(patched_chunks)
    for orig, patched in zip(original_chunks, patched_chunks):
        assert orig.output_text == patched.output_text
    assert original_full.output_text == patched_full.output_text

    time.sleep(0.5)
    for call in mock_session.request.call_args_list:
        assert call[0][0].upper() in ["POST", "GET", "PATCH"]

    _collect_requests(mock_session, "test_responses_stream_sync_api")


async def test_responses_stream_async_api():
    """Test that the async responses methods can be traced without errors."""
    import openai  # noqa

    mock_session = mock.MagicMock()
    ls_client = langsmith.Client(
        session=mock_session,
        info=LS_TEST_CLIENT_INFO,
    )
    original_client = openai.AsyncClient()
    patched_client = wrap_openai(
        openai.AsyncClient(), tracing_extra={"client": ls_client}
    )
    original_chunks = []
    patched_chunks = []
    async with original_client.responses.stream(
        input="Say 'foo' then stop.",
        model="gpt-5-nano",
        max_output_tokens=1024,
    ) as original_stream:
        async for chunk in original_stream:
            original_chunks.append(chunk)
            pass
        original_full = await original_stream.get_final_response()
    async with patched_client.responses.stream(
        input="Say 'foo' then stop.",
        model="gpt-5-nano",
        max_output_tokens=1024,
    ) as patched_stream:
        async for chunk in patched_stream:
            patched_chunks.append(chunk)
            pass
        patched_full = await patched_stream.get_final_response()
    assert len(original_chunks) == len(patched_chunks)
    assert original_full.output_text == patched_full.output_text

    time.sleep(0.5)
    for call in mock_session.request.call_args_list:
        assert call[0][0].upper() in ["POST", "GET", "PATCH"]

    _collect_requests(mock_session, "test_responses_stream_async_api")


@pytest.mark.asyncio
async def test_tool_call_chunking():
    """Test that wrap_openai can reduce tool call chunks when streaming."""
    import openai
    from openai.types.chat import ChatCompletionChunk

    mock_session = mock.MagicMock()
    ls_client = langsmith.Client(
        session=mock_session,
        info=LS_TEST_CLIENT_INFO,
    )

    client = wrap_openai(openai.AsyncClient(), tracing_extra={"client": ls_client})

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather in a given city.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city to get the weather for",
                        }
                    },
                    "required": ["location"],
                },
            },
        }
    ]

    # Simulate a user message
    messages = [{"role": "user", "content": "What's the weather like in Paris?"}]

    collect = Collect()
    with langsmith.tracing_context(enabled=True):
        chunks = await client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            stream=True,
            langsmith_extra={"on_end": collect},
        )

        tool_call_chunks = []
        tool_call_ids = set()
        async for chunk in chunks:
            assert isinstance(chunk, ChatCompletionChunk)
            # Collect chunks that contain tool calls
            for choice in chunk.choices:
                if choice.delta.tool_calls:
                    tool_call_chunks.append(chunk)
                    for tool_call in choice.delta.tool_calls:
                        if tool_call.id:
                            tool_call_ids.add(tool_call.id)

        # Verify that we have tool call chunks
        assert len(tool_call_chunks) > 0
        # Verify that there are tool call IDs
        assert len(tool_call_ids) > 0

        # Verify that the run has the expected data
        assert collect.run
        assert collect.run.outputs["choices"][0]["finish_reason"] == "tool_calls"
        assert collect.run.outputs["choices"][0]["message"]["tool_calls"]
        assert (
            collect.run.outputs["choices"][0]["message"]["tool_calls"][0]["function"][
                "name"
            ]
            == "get_weather"
        )

    # Allow time for background threads to complete
    time.sleep(0.1)
    for call in mock_session.request.call_args_list:
        assert call[0][0].upper() in ["POST", "GET", "PATCH"]
