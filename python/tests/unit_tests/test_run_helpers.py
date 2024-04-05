import asyncio
import functools
import inspect
import json
import os
import time
import warnings
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from langsmith import Client
from langsmith.run_helpers import (
    _get_inputs,
    as_runnable,
    is_traceable_function,
    traceable,
)


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
    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "true"}):

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
    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "true"}):

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

    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "false"}):
        runnable = as_runnable(my_function)
        assert runnable.invoke({"a": 1, "b": 2, "d": 3}) == 6


@patch("langsmith.client.requests.Session", autospec=True)
def test_as_runnable_batch(mock_client: Client) -> None:
    @traceable(client=mock_client)
    def my_function(a, b, d):
        return a + b + d

    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "false"}):
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
    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "false"}):
        result = await runnable.ainvoke({"a": 1, "b": 2, "d": 3})
        assert result == 6


@patch("langsmith.client.requests.Session", autospec=True)
async def test_as_runnable_async_batch(_: MagicMock) -> None:
    @traceable()
    async def my_function(a, b, d):
        return a + b + d

    runnable = as_runnable(my_function)
    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "false"}):
        result = await runnable.abatch(
            [
                {"a": 1, "b": 2, "d": 3},
                {"a": 1, "b": 2, "d": 4},
            ]
        )
        assert result == [6, 7]


def test_traceable_project_name() -> None:
    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "true"}):
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

        my_other_function()
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
