import asyncio
import functools
import inspect
import json
import sys
import time
import uuid
import warnings
from typing import Any, AsyncGenerator, Generator, Optional, cast
from unittest.mock import MagicMock, patch

import pytest

import langsmith
from langsmith import Client
from langsmith.run_helpers import (
    _get_inputs,
    as_runnable,
    is_traceable_function,
    traceable,
    tracing_context,
)
from langsmith.run_trees import RunTree


def test__get_inputs_with_no_args() -> None:
    def foo() -> None:
        pass

    signature = inspect.signature(foo)
    inputs = _get_inputs(signature)
    assert inputs == {}


def test__get_inputs_with_args() -> None:
    def foo(a: int, b: int, c: int) -> None:
        pass

    signature = inspect.signature(foo)
    inputs = _get_inputs(signature, 1, 2, 3)
    assert inputs == {"a": 1, "b": 2, "c": 3}


def test__get_inputs_with_defaults() -> None:
    def foo(a: int, b: int, c: int = 3) -> None:
        pass

    signature = inspect.signature(foo)
    inputs = _get_inputs(signature, 1, 2)
    assert inputs == {"a": 1, "b": 2, "c": 3}


def test__get_inputs_with_var_args() -> None:
    # Mis-named args as kwargs to check that it's mapped correctly
    def foo(a: int, b: int, *kwargs: Any) -> None:
        pass

    signature = inspect.signature(foo)
    inputs = _get_inputs(signature, 1, 2, 3, 4)
    assert inputs == {"a": 1, "b": 2, "kwargs": (3, 4)}


def test__get_inputs_with_var_kwargs() -> None:
    def foo(a: int, b: int, **kwargs: Any) -> None:
        pass

    signature = inspect.signature(foo)
    inputs = _get_inputs(signature, 1, 2, c=3, d=4)
    assert inputs == {"a": 1, "b": 2, "c": 3, "d": 4}


def test__get_inputs_with_var_kwargs_and_varargs() -> None:
    def foo(a: int, b: int, *args: Any, **kwargs: Any) -> None:
        pass

    signature = inspect.signature(foo)
    inputs = _get_inputs(signature, 1, 2, 3, 4, c=5, d=6)
    assert inputs == {"a": 1, "b": 2, "args": (3, 4), "c": 5, "d": 6}


def test__get_inputs_with_class_method() -> None:
    class Foo:
        @classmethod
        def bar(cls, a: int, b: int) -> None:
            pass

    signature = inspect.signature(Foo.bar)
    inputs = _get_inputs(signature, 1, 2)
    assert inputs == {"a": 1, "b": 2}


def test__get_inputs_with_static_method() -> None:
    class Foo:
        @staticmethod
        def bar(a: int, b: int) -> None:
            pass

    signature = inspect.signature(Foo.bar)
    inputs = _get_inputs(signature, 1, 2)
    assert inputs == {"a": 1, "b": 2}


def test__get_inputs_with_self() -> None:
    class Foo:
        def bar(self, a: int, b: int) -> None:
            pass

    signature = inspect.signature(Foo.bar)
    inputs = _get_inputs(signature, Foo(), 1, 2)
    assert inputs == {"a": 1, "b": 2}


def test__get_inputs_with_kwargs_and_var_kwargs() -> None:
    def foo(a: int, b: int, **kwargs: Any) -> None:
        pass

    signature = inspect.signature(foo)
    inputs = _get_inputs(signature, 1, 2, c=3, **{"d": 4})
    assert inputs == {"a": 1, "b": 2, "c": 3, "d": 4}


def test__get_inputs_with_var_kwargs_and_other_kwargs() -> None:
    def foo(a: int, b: int, **kwargs: Any) -> None:
        pass

    signature = inspect.signature(foo)
    inputs = _get_inputs(signature, 1, 2, c=3, other_kwargs={"d": 4})
    assert inputs == {"a": 1, "b": 2, "c": 3, "other_kwargs": {"d": 4}}


def test__get_inputs_with_keyword_only_args() -> None:
    def foo(a: int, *, b: int, c: int) -> None:
        pass

    signature = inspect.signature(foo)
    inputs = _get_inputs(signature, 1, b=2, c=3)
    assert inputs == {"a": 1, "b": 2, "c": 3}


def test__get_inputs_with_keyword_only_args_and_defaults() -> None:
    def foo(a: int, *, b: int = 2, c: int = 3) -> None:
        pass

    signature = inspect.signature(foo)
    inputs = _get_inputs(signature, 1)
    assert inputs == {"a": 1, "b": 2, "c": 3}


def test__get_inputs_misnamed_and_required_keyword_only_args() -> None:
    def foo(kwargs: int, *, b: int, c: int, **some_other_kwargs: Any) -> None:
        pass

    signature = inspect.signature(foo)
    inputs = _get_inputs(signature, 1, b=2, c=3, d=4, e=5, other_kwargs={"f": 6})
    assert inputs == {
        "kwargs": 1,
        "b": 2,
        "c": 3,
        "d": 4,
        "e": 5,
        "other_kwargs": {"f": 6},
    }


def _get_mock_client() -> Client:
    mock_session = MagicMock()
    client = Client(session=mock_session, api_key="test")
    return client


@pytest.fixture
def mock_client() -> Client:
    return _get_mock_client()


@pytest.mark.parametrize("use_next", [True, False])
def test_traceable_iterator(use_next: bool, mock_client: Client) -> None:
    with tracing_context(enabled=True):

        @traceable(client=mock_client)
        def my_iterator_fn(a, b, d):
            for i in range(a + b + d):
                yield i

        expected = [0, 1, 2, 3, 4, 5]
        genout = my_iterator_fn(1, 2, 3)
        if use_next:
            results = []
            while True:
                try:
                    results.append(next(genout))
                except StopIteration:
                    break
        else:
            results = list(genout)
        assert results == expected
    # Wait for batcher
    time.sleep(0.25)
    # check the mock_calls
    mock_calls = mock_client.session.request.mock_calls  # type: ignore
    assert 1 <= len(mock_calls) <= 2

    call = mock_calls[0]
    assert call.args[0] == "POST"
    assert call.args[1].startswith("https://api.smith.langchain.com")
    body = json.loads(mock_calls[0].kwargs["data"])
    assert body["post"]
    assert body["post"][0]["outputs"]["output"] == expected


@pytest.mark.parametrize("use_next", [True, False])
async def test_traceable_async_iterator(use_next: bool, mock_client: Client) -> None:
    with tracing_context(enabled=True):

        def filter_inputs(kwargs: dict):
            return {"a": "FOOOOOO", "b": kwargs["b"], "d": kwargs["d"]}

        @traceable(client=mock_client, process_inputs=filter_inputs)
        async def my_iterator_fn(a, b, d):
            for i in range(a + b + d):
                yield i

        expected = [0, 1, 2, 3, 4, 5]
        genout = my_iterator_fn(1, 2, 3)
        if use_next:
            results = []
            async for item in genout:
                results.append(item)
        else:
            results = [item async for item in genout]
        assert results == expected
        # Wait for batcher
        await asyncio.sleep(0.25)
        # check the mock_calls
        mock_calls = mock_client.session.request.mock_calls  # type: ignore
        assert 1 <= len(mock_calls) <= 2

        call = mock_calls[0]
        assert call.args[0] == "POST"
        assert call.args[1].startswith("https://api.smith.langchain.com")
        body = json.loads(call.kwargs["data"])
        assert body["post"]
        assert body["post"][0]["outputs"]["output"] == expected
        # Assert the inputs are filtered as expected
        assert body["post"][0]["inputs"] == {"a": "FOOOOOO", "b": 2, "d": 3}


@patch("langsmith.run_trees.Client", autospec=True)
def test_traceable_iterator_noargs(_: MagicMock) -> None:
    @traceable
    def my_iterator_fn(a, b, d):
        for i in range(a + b + d):
            yield i

    assert list(my_iterator_fn(1, 2, 3)) == [0, 1, 2, 3, 4, 5]


@patch("langsmith.run_trees.Client", autospec=True)
async def test_traceable_async_iterator_noargs(_: MagicMock) -> None:
    # Check that it's callable without the parens
    @traceable
    async def my_iterator_fn(a, b, d):
        for i in range(a + b + d):
            yield i

    assert [i async for i in my_iterator_fn(1, 2, 3)] == [0, 1, 2, 3, 4, 5]


@patch("langsmith.client.requests.Session", autospec=True)
def test_as_runnable(_: MagicMock, mock_client: Client) -> None:
    @traceable(client=mock_client)
    def my_function(a, b, d):
        return a + b + d

    with tracing_context(enabled=False):
        runnable = as_runnable(my_function)
        assert runnable.invoke({"a": 1, "b": 2, "d": 3}) == 6


@patch("langsmith.client.requests.Session", autospec=True)
def test_as_runnable_batch(mock_client: Client) -> None:
    @traceable(client=mock_client)
    def my_function(a, b, d):
        return a + b + d

    with tracing_context(enabled=False):
        runnable = as_runnable(my_function)
        assert runnable.batch(
            [
                {"a": 1, "b": 2, "d": 3},
                {"a": 1, "b": 2, "d": 4},
            ]
        ) == [6, 7]


@patch("langsmith.client.requests.Session", autospec=True)
async def test_as_runnable_async(_: MagicMock) -> None:
    @traceable()
    async def my_function(a, b, d):
        return a + b + d

    runnable = as_runnable(my_function)
    with tracing_context(enabled=False):
        result = await runnable.ainvoke({"a": 1, "b": 2, "d": 3})
        assert result == 6


@patch("langsmith.client.requests.Session", autospec=True)
async def test_as_runnable_async_batch(_: MagicMock) -> None:
    @traceable()
    async def my_function(a, b, d):
        return a + b + d

    runnable = as_runnable(my_function)
    with tracing_context(enabled=False):
        result = await runnable.abatch(
            [
                {"a": 1, "b": 2, "d": 3},
                {"a": 1, "b": 2, "d": 4},
            ]
        )
        assert result == [6, 7]


def test_traceable_parent_from_runnable_config() -> None:
    try:
        from langchain.callbacks.tracers import LangChainTracer
        from langchain.schema.runnable import RunnableLambda
    except ImportError:
        pytest.skip("Skipping test that requires langchain")
    with tracing_context(enabled=True):
        mock_client_ = _get_mock_client()

        @traceable()
        def my_function(a: int) -> int:
            return a * 2

        my_function_runnable = RunnableLambda(my_function)

        assert (
            my_function_runnable.invoke(
                1, {"callbacks": [LangChainTracer(client=mock_client_)]}
            )
            == 2
        )
        time.sleep(1)
        # Inspect the mock_calls and assert that 2 runs were created,
        # one for the parent and one for the child
        mock_calls = mock_client_.session.request.mock_calls  # type: ignore
        posts = []
        for call in mock_calls:
            if call.args:
                assert call.args[0] == "POST"
                assert call.args[1].startswith("https://api.smith.langchain.com")
                body = json.loads(call.kwargs["data"])
                assert body["post"]
                posts.extend(body["post"])
        assert len(posts) == 2
        parent = next(p for p in posts if p["parent_run_id"] is None)
        child = next(p for p in posts if p["parent_run_id"] is not None)
        assert child["parent_run_id"] == parent["id"]


def test_traceable_parent_from_runnable_config_accepts_config() -> None:
    try:
        from langchain.callbacks.tracers import LangChainTracer
        from langchain.schema.runnable import RunnableLambda
    except ImportError:
        pytest.skip("Skipping test that requires langchain")
    with tracing_context(enabled=True):
        mock_client_ = _get_mock_client()

        @traceable()
        def my_function(a: int, config: dict) -> int:
            assert isinstance(config, dict)
            return a * 2

        my_function_runnable = RunnableLambda(my_function)

        assert (
            my_function_runnable.invoke(
                1, {"callbacks": [LangChainTracer(client=mock_client_)]}
            )
            == 2
        )
        time.sleep(1)
        # Inspect the mock_calls and assert that 2 runs were created,
        # one for the parent and one for the child
        mock_calls = mock_client_.session.request.mock_calls  # type: ignore
        posts = []
        for call in mock_calls:
            if call.args:
                assert call.args[0] == "POST"
                assert call.args[1].startswith("https://api.smith.langchain.com")
                body = json.loads(call.kwargs["data"])
                assert body["post"]
                posts.extend(body["post"])
        assert len(posts) == 2
        parent = next(p for p in posts if p["parent_run_id"] is None)
        child = next(p for p in posts if p["parent_run_id"] is not None)
        assert child["parent_run_id"] == parent["id"]


def test_traceable_project_name() -> None:
    with tracing_context(enabled=True):
        mock_client_ = _get_mock_client()

        @traceable(client=mock_client_, project_name="my foo project")
        def my_function(a: int, b: int, d: int) -> int:
            return a + b + d

        my_function(1, 2, 3)
        time.sleep(0.25)
        # Inspect the mock_calls and asser tthat "my foo project" is in
        # the session_name arg of the body
        mock_calls = mock_client_.session.request.mock_calls  # type: ignore
        assert 1 <= len(mock_calls) <= 2
        call = mock_calls[0]
        assert call.args[0] == "POST"
        assert call.args[1].startswith("https://api.smith.langchain.com")
        body = json.loads(call.kwargs["data"])
        assert body["post"]
        assert body["post"][0]["session_name"] == "my foo project"

        # reset
        mock_client_ = _get_mock_client()

        @traceable(client=mock_client_, project_name="my bar project")
        def my_other_function(run_tree) -> int:
            return my_function(1, 2, 3)

        my_other_function()  # type: ignore
        time.sleep(0.25)
        # Inspect the mock_calls and assert that "my bar project" is in
        # both all POST runs in the single request. We want to ensure
        # all runs in a trace are associated with the same project.
        mock_calls = mock_client_.session.request.mock_calls  # type: ignore
        assert 1 <= len(mock_calls) <= 2
        call = mock_calls[0]
        assert call.args[0] == "POST"
        assert call.args[1].startswith("https://api.smith.langchain.com")
        body = json.loads(call.kwargs["data"])
        assert body["post"]
        assert body["post"][0]["session_name"] == "my bar project"
        assert body["post"][1]["session_name"] == "my bar project"


def test_is_traceable_function(mock_client: Client) -> None:
    @traceable(client=mock_client)
    def my_function(a: int, b: int, d: int) -> int:
        return a + b + d

    assert is_traceable_function(my_function)


def test_is_traceable_partial_function(mock_client: Client) -> None:
    @traceable(client=mock_client)
    def my_function(a: int, b: int, d: int) -> int:
        return a + b + d

    partial_function = functools.partial(my_function, 1, 2)

    assert is_traceable_function(partial_function)


def test_is_not_traceable_function() -> None:
    def my_function(a: int, b: int, d: int) -> int:
        return a + b + d

    assert not is_traceable_function(my_function)


def test_is_traceable_class_call(mock_client: Client) -> None:
    class Foo:
        @traceable(client=mock_client)
        def __call__(self, a: int, b: int) -> None:
            pass

    assert is_traceable_function(Foo())


def test_is_not_traceable_class_call() -> None:
    class Foo:
        def __call__(self, a: int, b: int) -> None:
            pass

    assert not is_traceable_function(Foo())


def test_traceable_warning() -> None:
    with warnings.catch_warnings(record=True) as warning_records:
        warnings.simplefilter("always")

        @traceable(run_type="invalid_run_type")  # type: ignore
        def my_function() -> None:
            pass

        assert len(warning_records) == 1
        assert issubclass(warning_records[0].category, UserWarning)
        assert "Unrecognized run_type: invalid_run_type" in str(
            warning_records[0].message
        )
        assert "Did you mean @traceable(name='invalid_run_type')?" in str(
            warning_records[0].message
        )


def test_traceable_wrong_run_type_pos_arg() -> None:
    with warnings.catch_warnings(record=True) as warning_records:
        warnings.simplefilter("always")

        @traceable("my_run_type")  # type: ignore
        def my_function() -> None:
            pass

        assert len(warning_records) == 1
        assert issubclass(warning_records[0].category, UserWarning)
        assert "Unrecognized run_type: my_run_type" in str(warning_records[0].message)
        assert "Did you mean @traceable(name='my_run_type')?" in str(
            warning_records[0].message
        )


def test_traceable_too_many_pos_args() -> None:
    with warnings.catch_warnings(record=True) as warning_records:
        warnings.simplefilter("always")

        @traceable("chain", "my_function")  # type: ignore
        def my_function() -> None:
            pass

        assert len(warning_records) == 1
        assert issubclass(warning_records[0].category, UserWarning)
        assert "only accepts one positional argument" in str(warning_records[0].message)


# Really hard to get contextvar propagation right for async generators
# prior to Python 3.10
@pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="Skipping for Python 3.10 or earlier",
)
async def test_async_generator():
    @traceable
    def some_sync_func(query: str) -> list:
        return [query, query]

    @traceable
    async def some_async_func(queries: list) -> AsyncGenerator[list, None]:
        await asyncio.sleep(0.01)
        for query in queries:
            yield query

    @traceable
    async def another_async_func(query: str) -> str:
        rid = uuid.uuid4()
        with langsmith.trace(
            name="zee-cm", inputs={"query": query}, run_id=rid
        ) as run_tree:
            run_tree.end(outputs={"query": query})
            assert run_tree.id == rid
        return query

    @traceable
    async def create_document_context(documents: list) -> str:
        await asyncio.sleep(0.01)
        return "\n".join(documents)

    @traceable
    async def summarize_answers(
        query: str, document_context: str
    ) -> AsyncGenerator[str, None]:
        await asyncio.sleep(0.01)
        for i in range(3):
            yield f"Answer {i}"

    @traceable(run_type="chain", name="expand_and_answer_questions")
    async def my_answer(
        query: str,
    ) -> AsyncGenerator[Any, None]:
        expanded_terms = some_sync_func(query=query)
        docs_gen = some_async_func(
            queries=expanded_terms,
        )
        documents = []
        async for document in docs_gen:
            documents.append(document)
            break

        await another_async_func(query=query)

        for document in documents:
            yield document
        async for document in docs_gen:
            documents.append(document)
            yield document

        document_context = await create_document_context(
            documents=documents,
        )

        final_answer = summarize_answers(query=query, document_context=document_context)
        async for chunk in final_answer:
            yield chunk

    run: Optional[RunTree] = None  # type: ignore

    def _get_run(r: RunTree) -> None:
        nonlocal run
        run = r

    mock_client_ = _get_mock_client()
    with tracing_context(enabled=True):
        chunks = my_answer(
            "some_query", langsmith_extra={"on_end": _get_run, "client": mock_client_}
        )
        all_chunks = []
        async for chunk in chunks:
            all_chunks.append(chunk)

    assert all_chunks == [
        "some_query",
        "some_query",
        "Answer 0",
        "Answer 1",
        "Answer 2",
    ]
    assert run is not None
    run = cast(RunTree, run)
    assert run.name == "expand_and_answer_questions"
    child_runs = run.child_runs
    assert child_runs and len(child_runs) == 5
    names = [run.name for run in child_runs]
    assert names == [
        "some_sync_func",
        "some_async_func",
        "another_async_func",
        "create_document_context",
        "summarize_answers",
    ]
    assert len(child_runs[2].child_runs) == 1  # type: ignore


def test_generator():
    @traceable
    def some_sync_func(query: str) -> list:
        return [query, query]

    @traceable
    def some_func(queries: list) -> Generator[list, None, None]:
        for query in queries:
            yield query

    @traceable
    def another_func(query: str) -> str:
        with langsmith.trace(name="zee-cm", inputs={"query": query}) as run_tree:
            run_tree.end(outputs={"query": query})
        return query

    @traceable
    def create_document_context(documents: list) -> str:
        return "\n".join(documents)

    @traceable
    def summarize_answers(
        query: str, document_context: str
    ) -> Generator[str, None, None]:
        for i in range(3):
            yield f"Answer {i}"

    @traceable(run_type="chain", name="expand_and_answer_questions")
    def my_answer(
        query: str,
    ) -> Generator[Any, None, None]:
        expanded_terms = some_sync_func(query=query)
        docs_gen = some_func(
            queries=expanded_terms,
        )
        documents = []
        for document in docs_gen:
            documents.append(document)
            break

        another_func(query=query)

        for document in documents:
            yield document
        for document in docs_gen:
            documents.append(document)
            yield document

        document_context = create_document_context(
            documents=documents,
        )

        final_answer = summarize_answers(query=query, document_context=document_context)
        for chunk in final_answer:
            yield chunk

    run: Optional[RunTree] = None  # type: ignore

    def _get_run(r: RunTree) -> None:
        nonlocal run
        run = r

    mock_client_ = _get_mock_client()

    with tracing_context(enabled=True):
        chunks = my_answer(
            "some_query", langsmith_extra={"on_end": _get_run, "client": mock_client_}
        )
        all_chunks = []
        for chunk in chunks:
            all_chunks.append(chunk)

    assert all_chunks == [
        "some_query",
        "some_query",
        "Answer 0",
        "Answer 1",
        "Answer 2",
    ]
    assert run is not None
    run = cast(RunTree, run)
    assert run.name == "expand_and_answer_questions"
    child_runs = run.child_runs
    assert child_runs and len(child_runs) == 5
    names = [run.name for run in child_runs]
    assert names == [
        "some_sync_func",
        "some_func",
        "another_func",
        "create_document_context",
        "summarize_answers",
    ]
    assert len(child_runs[2].child_runs) == 1  # type: ignore


def test_traceable_regular():
    @traceable
    def some_sync_func(query: str) -> list:
        return [query, query]

    @traceable
    def some_func(queries: list) -> list:
        return queries

    @traceable
    def another_func(query: str) -> str:
        with langsmith.trace(name="zee-cm", inputs={"query": query}) as run_tree:
            run_tree.end(outputs={"query": query})
        return query

    @traceable
    def create_document_context(documents: list) -> str:
        return "\n".join(documents)

    @traceable
    def summarize_answers(query: str, document_context: str) -> list:
        return [f"Answer {i}" for i in range(3)]

    @traceable(run_type="chain", name="expand_and_answer_questions")
    def my_answer(
        query: str,
    ) -> list:
        expanded_terms = some_sync_func(query=query)
        documents = some_func(
            queries=expanded_terms,
        )

        another_func(query=query)

        document_context = create_document_context(
            documents=documents,
        )

        final_answer = summarize_answers(query=query, document_context=document_context)
        return documents + final_answer

    run: Optional[RunTree] = None  # type: ignore

    def _get_run(r: RunTree) -> None:
        nonlocal run
        run = r

    mock_client_ = _get_mock_client()
    with tracing_context(enabled=True):
        all_chunks = my_answer(
            "some_query", langsmith_extra={"on_end": _get_run, "client": mock_client_}
        )

    assert all_chunks == [
        "some_query",
        "some_query",
        "Answer 0",
        "Answer 1",
        "Answer 2",
    ]
    assert run is not None
    run = cast(RunTree, run)
    assert run.name == "expand_and_answer_questions"
    child_runs = run.child_runs
    assert child_runs and len(child_runs) == 5
    names = [run.name for run in child_runs]
    assert names == [
        "some_sync_func",
        "some_func",
        "another_func",
        "create_document_context",
        "summarize_answers",
    ]
    assert len(child_runs[2].child_runs) == 1  # type: ignore


async def test_traceable_async():
    @traceable
    def some_sync_func(query: str) -> list:
        return [query, query]

    @traceable
    async def some_async_func(queries: list) -> list:
        await asyncio.sleep(0.01)
        return queries

    @traceable
    async def another_async_func(query: str) -> str:
        with langsmith.trace(name="zee-cm", inputs={"query": query}) as run_tree:
            run_tree.end(outputs={"query": query})
        return query

    @traceable
    async def create_document_context(documents: list) -> str:
        await asyncio.sleep(0.01)
        return "\n".join(documents)

    @traceable
    async def summarize_answers(query: str, document_context: str) -> list:
        await asyncio.sleep(0.01)
        return [f"Answer {i}" for i in range(3)]

    @traceable(run_type="chain", name="expand_and_answer_questions")
    async def my_answer(
        query: str,
    ) -> list:
        expanded_terms = some_sync_func(query=query)
        documents = await some_async_func(
            queries=expanded_terms,
        )

        await another_async_func(query=query)

        document_context = await create_document_context(
            documents=documents,
        )

        final_answer = await summarize_answers(
            query=query, document_context=document_context
        )
        return documents + final_answer

    run: Optional[RunTree] = None  # type: ignore

    def _get_run(r: RunTree) -> None:
        nonlocal run
        run = r

    mock_client_ = _get_mock_client()
    with tracing_context(enabled=True):
        all_chunks = await my_answer(
            "some_query", langsmith_extra={"on_end": _get_run, "client": mock_client_}
        )

    assert all_chunks == [
        "some_query",
        "some_query",
        "Answer 0",
        "Answer 1",
        "Answer 2",
    ]
    assert run is not None
    run = cast(RunTree, run)
    assert run.name == "expand_and_answer_questions"
    child_runs = run.child_runs
    assert child_runs and len(child_runs) == 5
    names = [run.name for run in child_runs]
    assert names == [
        "some_sync_func",
        "some_async_func",
        "another_async_func",
        "create_document_context",
        "summarize_answers",
    ]
    assert len(child_runs[2].child_runs) == 1  # type: ignore


def test_traceable_to_trace():
    @traceable
    def parent_fn(a: int, b: int) -> int:
        with langsmith.trace(name="child_fn", inputs={"a": a, "b": b}) as run_tree:
            result = a + b
            run_tree.end(outputs={"result": result})
        return result

    run: Optional[RunTree] = None  # type: ignore

    def _get_run(r: RunTree) -> None:
        nonlocal run
        run = r

    with tracing_context(enabled=True):
        result = parent_fn(
            1, 2, langsmith_extra={"on_end": _get_run, "client": _get_mock_client()}
        )

    assert result == 3
    assert run is not None
    run = cast(RunTree, run)
    assert run.name == "parent_fn"
    assert run.outputs == {"output": 3}
    assert run.inputs == {"a": 1, "b": 2}
    child_runs = run.child_runs
    assert child_runs
    assert len(child_runs) == 1
    assert child_runs[0].name == "child_fn"
    assert child_runs[0].inputs == {"a": 1, "b": 2}


def test_trace_to_traceable():
    @traceable
    def child_fn(a: int, b: int) -> int:
        return a + b

    mock_client_ = _get_mock_client()
    with tracing_context(enabled=True):
        rid = uuid.uuid4()
        with langsmith.trace(
            name="parent_fn", inputs={"a": 1, "b": 2}, client=mock_client_, run_id=rid
        ) as run:
            result = child_fn(1, 2)
            run.end(outputs={"result": result})
            assert run.id == rid

    assert result == 3
    assert run.name == "parent_fn"
    assert run.outputs == {"result": 3}
    assert run.inputs == {"a": 1, "b": 2}
    child_runs = run.child_runs
    assert child_runs
    assert len(child_runs) == 1
    assert child_runs[0].name == "child_fn"
    assert child_runs[0].inputs == {"a": 1, "b": 2}
