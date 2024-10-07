# mypy: disable-error-code="attr-defined, union-attr, arg-type, call-overload"
import time
from datetime import datetime
from unittest import mock
from uuid import uuid4

import pytest

import langsmith
from langsmith.wrappers import wrap_openai


@mock.patch("langsmith.client.requests.Session")
@pytest.mark.parametrize("stream", [False, True])
def test_chat_sync_api(mock_session: mock.MagicMock, stream: bool):
    import openai  # noqa

    client = langsmith.Client(session=mock_session())
    original_client = openai.Client()
    patched_client = wrap_openai(openai.Client(), tracing_extra={"client": client})
    messages = [{"role": "user", "content": "Say 'foo'"}]
    original = original_client.chat.completions.create(
        messages=messages,  # noqa: [arg-type]
        stream=stream,
        temperature=0,
        seed=42,
        model="gpt-3.5-turbo",
    )
    patched = patched_client.chat.completions.create(
        messages=messages,  # noqa: [arg-type]
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
        assert type(original) == type(patched)
        assert original.choices == patched.choices
    # Give the thread a chance.
    time.sleep(0.01)
    for call in mock_session.return_value.request.call_args_list[1:]:
        assert call[0][0].upper() == "POST"


@mock.patch("langsmith.client.requests.Session")
@pytest.mark.parametrize("stream", [False, True])
async def test_chat_async_api(mock_session: mock.MagicMock, stream: bool):
    import openai  # noqa

    client = langsmith.Client(session=mock_session())
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
        assert type(original) == type(patched)
        assert original.choices == patched.choices
    # Give the thread a chance.
    time.sleep(0.1)
    for call in mock_session.return_value.request.call_args_list[1:]:
        assert call[0][0].upper() == "POST"


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


def test_wrap_openai_token_counts():
    import openai

    oai_client = openai.Client()

    wrapped_oai_client = wrap_openai(oai_client)

    project_name = f"__test_wrap_openai_{datetime.now().isoformat()}_{uuid4().hex[:6]}"
    ls_client = langsmith.Client()

    collect = Collect()
    try:
        run_id_to_usage_metadata = {}
        with langsmith.tracing_context(
            enabled=True, project_name=project_name, client=ls_client
        ):
            # stream usage
            res = wrapped_oai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "howdy"}],
                langsmith_extra={"on_end": collect},
                stream=True,
                stream_options={"include_usage": True},
            )

            for _ in res:
                # consume the stream
                pass

            run_id_to_usage_metadata[collect.run.id] = collect.run.outputs[
                "usage_metadata"
            ]

            # stream without usage
            res = wrapped_oai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "howdy"}],
                langsmith_extra={"on_end": collect},
                stream=True,
            )

            for _ in res:
                # consume the stream
                pass

            assert collect.run.outputs.get("usage_metadata") is None
            assert collect.run.outputs.get("usage") is None

            wrapped_oai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "howdy"}],
                langsmith_extra={"on_end": collect},
            )

            run_id_to_usage_metadata[collect.run.id] = collect.run.outputs[
                "usage_metadata"
            ]

            wrapped_oai_client.chat.completions.create(
                model="o1-mini",
                messages=[
                    {
                        "role": "user",
                        "content": "Write a bash script that takes a matrix represented as a string with format '[1,2],[3,4],[5,6]' and prints the transpose in the same format.",
                    }
                ],
                langsmith_extra={"on_end": collect},
            )

            run_id_to_usage_metadata[collect.run.id] = collect.run.outputs[
                "usage_metadata"
            ]

            # handle pending runs
            runs = list(ls_client.list_runs(project_name=project_name))
            assert len(runs) == 4
            for run in runs:
                assert run.outputs.get("usage_metadata") is not None

        # assert collect.run is not None
        # print(collect.run)
        # for call in mock_session.return_value.request.call_args_list:
        #     # assert call[0][0].upper() == "POST"
        #
        #     json_bytes = call.kwargs.get("data")
        #     if json_bytes is not None:
        #         json_str = json_bytes.decode("utf-8")
        #         import json
        #         dict = json.loads(json_str)
        #         print(dict)
    finally:
        ls_client.delete_project(project_name=project_name)
