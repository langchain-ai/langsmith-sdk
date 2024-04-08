from __future__ import annotations

import atexit
import datetime
import functools
import inspect
import logging
import os
import threading
import uuid
import weakref
from typing import Any, Callable, Optional, Sequence, Tuple, TypeVar, overload

from typing_extensions import TypedDict

from langsmith import client as ls_client
from langsmith import env as ls_env
from langsmith import run_helpers as rh
from langsmith import schemas as ls_schemas
from langsmith import utils as ls_utils

logger = logging.getLogger(__name__)


def _get_experiment_name() -> str:
    # TODO Make more easily configurable
    prefix = ls_utils.get_tracer_project(False) or "TestSuite"
    name = f"{prefix}:{uuid.uuid4().hex[:8]}"
    return name


def _get_test_suite_name() -> str:
    # TODO: This naming stuff is inelegant
    test_suite_name = os.environ.get("LANGCHAIN_TEST_SUITE")
    if test_suite_name:
        return test_suite_name
    if __package__:
        return __package__
    git_info = ls_env.get_git_info()
    if git_info:
        if git_info["remote_url"]:
            repo_name = git_info["remote_url"].split("/")[-1].split(".")[0]
            if repo_name:
                return repo_name
    raise ValueError("Please set the LANGCHAIN_TEST_SUITE environment variable.")


def _get_test_suite(client: ls_client.Client) -> ls_schemas.Dataset:
    test_suite_name = _get_test_suite_name()

    if client.has_dataset(dataset_name=test_suite_name):
        return client.read_dataset(dataset_name=test_suite_name)
    else:
        return client.create_dataset(dataset_name=test_suite_name)


def _start_experiment(
    client: ls_client.Client,
    test_suite: ls_schemas.Dataset,
) -> ls_schemas.TracerSessionResult:
    experiment_name = _get_experiment_name()
    return client.create_project(experiment_name, reference_dataset_id=test_suite.id)


def _get_id(func: Callable) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"{func.__module__}.{func.__name__}")


def _end_tests(
    client: ls_client.Client,
    experiment: ls_schemas.TracerSessionResult,
    get_version: Callable[[], Optional[datetime.datetime]],
):
    return client.update_project(
        experiment.id,
        end_time=datetime.datetime.now(datetime.timezone.utc),
        metadata={"dataset_version": get_version()},
    )


class _LangSmithTestSuite:
    _instance = None
    _lock = threading.RLock()

    def __init__(
        self,
        client: Optional[ls_client.Client],
        experiment: ls_schemas.TracerSessionResult,
        dataset: ls_schemas.Dataset,
    ):
        self._client = client or ls_client.Client()
        self._experiment = experiment
        self._dataset = dataset
        self._version: Optional[datetime.datetime] = None
        weakref.finalize(
            self, _end_tests, self._client, self._experiment, self.get_version
        )
        atexit.register(_end_tests, self._client, self._experiment, self.get_version)

    @property
    def id(self):
        return self._dataset.id

    @classmethod
    def get_singleton(cls, client: Optional[ls_client.Client]):
        client = client or ls_client.Client()
        with cls._lock:
            if not cls._instance:
                test_suite = _get_test_suite(client)
                experiment = _start_experiment(client, test_suite)
                cls._instance = cls(client, experiment, test_suite)
        return cls._instance

    @property
    def name(self):
        return self._experiment.name

    def update_version(self, version: datetime.datetime) -> None:
        if self._version is None or version > self._version:
            self._version = version

    def get_version(self) -> Optional[datetime.datetime]:
        return self._version


T = TypeVar("T")
U = TypeVar("U")


class _UTExtra(TypedDict, total=False):
    client: Optional[ls_client.Client]
    id: Optional[uuid.UUID]
    output_keys: Optional[Sequence[str]]
    test_suite_name: Optional[str]


def _ensure_example(
    func: Callable, *args: Any, langtest_extra: _UTExtra, **kwargs: Any
) -> Tuple[ls_schemas.TracerSession, ls_schemas.Example]:
    # 1. check if the id exists.
    # TODOs: Local cache + prefer a peek operation
    client = langtest_extra["client"] or ls_client.Client()
    example_id = langtest_extra["id"] or _get_id(func)
    output_keys = langtest_extra["output_keys"]
    signature = inspect.signature(func)
    # TODO: Support multiple test suites
    test_suite = _LangSmithTestSuite.get_singleton(client)
    try:
        example = client.read_example(example_id=example_id)
    except ls_utils.LangSmithNotFoundError:
        # TODO: support
        # 2. Create the example
        inputs = rh._get_inputs_safe(signature, args, kwargs)
        outputs = {}
        if output_keys:
            for k in output_keys:
                outputs[k] = inputs.pop(k, None)
        example = client.create_example(
            example_id=example_id,
            inputs=inputs,
            # TODO: Handle output_keys
            outputs=outputs,
            dataset_id=test_suite.id,
        )
    test_suite.update_version(example.modified_at)
    return test_suite, example


def _run_test(func, *test_args, langtest_extra: _UTExtra, **test_kwargs):
    test_suite, example = _ensure_example(
        func, *test_args, **test_kwargs, langtest_extra=langtest_extra
    )
    run_id = uuid.uuid4()

    try:
        func_ = func if rh.is_traceable_function(func) else rh.traceable(func)
        func_(
            *test_args,
            **test_kwargs,
            langsmith_extra={
                "run_id": run_id,
                "reference_example_id": example.id,
                "project_name": test_suite.name,
            },
        )
    except BaseException as e:
        client = test_kwargs.get("client") or ls_client.Client()
        client.create_feedback(
            run_id,
            key="pass",
            score=0,
            comment=f"Error: {repr(e)}",
        )
        raise e
    try:
        client = test_kwargs.get("client") or ls_client.Client()
        client.create_feedback(
            run_id,
            key="pass",
            score=1,
        )
    except BaseException as e:
        logger.warning(f"Failed to create feedback for run_id {run_id}: {e}")


@overload
def test_case(
    func: Callable,
) -> Callable: ...


@overload
def test_case(
    *,
    id: uuid.UUID,
    output_keys: Optional[Sequence[str]] = None,
    client: Optional[ls_client.Client] = None,
    # TODO: naming should be consistent probably
    # It's a dataset in the background
    test_suite_name: Optional[str] = None,
) -> Callable[[Callable], Callable]: ...


def test_case(*args, **kwargs):
    """Decorator for defining a LangSmith test case.

    This decorator is used to mark a function as a test case for LangSmith. It ensures
    that the necessary example data is created and associated with the test function.
    The decorated function will be executed as a test case, and the results will be
    recorded and reported by LangSmith.

    Args:
        *args: Positional arguments.
            - If a single callable is provided as a positional argument, it will be
              treated as the test function to be decorated.
        **kwargs: Keyword arguments.
            - id (Optional[uuid.UUID]): A unique identifier for the test case. If not
              provided, an ID will be generated based on the test function's module
              and name.
            - output_keys (Optional[Sequence[str]]): A list of keys to be considered as
              the output keys for the test case. These keys will be extracted from the
              test function's inputs and stored as the expected outputs.
            - client (Optional[ls_client.Client]): An instance of the LangSmith client
              to be used for communication with the LangSmith service. If not provided,
              a default client will be used.
            - test_suite_name (Optional[str]): The name of the test suite to which the
              test case belongs. If not provided, the test suite name will be determined
              based on the environment or the package name.

    Returns:
        Callable: The decorated test function.

    Example:
        To define a test case using the decorator:

        >>> @test_case
        ... def test_addition(a: int, b: int, expected: int):
        ...     assert a + b == expected

        To define a test case with a specific ID and output keys:

        >>> @test_case(id=uuid.uuid4(), output_keys=["result"])
        ... def test_multiplication(a: int, b: int, result: int):
        ...     assert a * b == result

        Using the decorator with pytest fixtures and OpenAI:

        >>> import openai
        >>> import pytest
        >>> from langsmith import test_case
        >>> from langsmith.wrappers import wrap_openai
        >>>
        >>> @test_case
        ... def test_example():
        ...     assert True
        >>>
        >>> @pytest.fixture
        ... def some_input():
        ...     return "Some input"
        >>>
        >>> @test_case
        ... def test_other_example(some_input: str):
        ...     assert "input" in some_input
        >>>
        >>> @test_case
        ... def test_openai_says_hello():
        ...     # Traced code will be included in the test case
        ...     oai_client = wrap_openai(openai.Client())
        ...     response = oai_client.chat.completions.create(
        ...         model="gpt-3.5-turbo",
        ...         messages=[
        ...             {"role": "system", "content": "You are a helpful assistant."},
        ...             {"role": "user", "content": "Say hello!"},
        ...         ],
        ...     )
        ...     assert "hello" in response.choices[0].message.content.lower()


        Run in pytest, or directly run the test functions.

        >>> test_example()
        >>> test_other_example("Some input")
        >>> test_openai_says_hello()
    """
    langtest_extra = _UTExtra(
        id=kwargs.get("id"),
        output_keys=kwargs.get("output_keys "),
        client=kwargs.get("client"),
        test_suite_name=kwargs.get("test_suite_name"),
    )
    if args and callable(args[0]):
        func = args[0]

        @functools.wraps(func)
        def wrapper(*test_args, **test_kwargs):
            _run_test(
                func,
                *test_args,
                **test_kwargs,
                langtest_extra=langtest_extra,
            )

        return wrapper

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*test_args, **test_kwargs):
            _run_test(func, *test_args, **test_kwargs, langtest_extra=langtest_extra)

        return wrapper

    return decorator
