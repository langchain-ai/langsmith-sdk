from __future__ import annotations

import atexit
import concurrent.futures
import datetime
import functools
import inspect
import json
import logging
import os
import threading
import uuid
import warnings
from pathlib import Path
from typing import Any, Callable, Optional, Sequence, Tuple, TypeVar, overload

from typing_extensions import TypedDict

from langsmith import client as ls_client
from langsmith import env as ls_env
from langsmith import run_helpers as rh
from langsmith import schemas as ls_schemas
from langsmith import utils as ls_utils

logger = logging.getLogger(__name__)


T = TypeVar("T")
U = TypeVar("U")


@overload
def unit(
    func: Callable,
) -> Callable: ...


@overload
def unit(
    *,
    id: Optional[uuid.UUID] = None,
    output_keys: Optional[Sequence[str]] = None,
    client: Optional[ls_client.Client] = None,
    test_suite_name: Optional[str] = None,
) -> Callable[[Callable], Callable]: ...


def unit(*args: Any, **kwargs: Any) -> Callable:
    """Create a unit test case in LangSmith.

    This decorator is used to mark a function as a test case for LangSmith. It ensures
    that the necessary example data is created and associated with the test function.
    The decorated function will be executed as a test case, and the results will be
    recorded and reported by LangSmith.

    Args:
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

    Environment Variables:
        - LANGCHAIN_DISABLE_TEST_TRACKING: Set this variable to 'true' to disable
            LangSmith test tracking. If set to 'true', the test case will be executed
            without any LangSmith-specific functionality.
        - LANGCHAIN_TEST_TRACKING: Set this variable to the path of a directory to enable
            caching of test results. This is useful for re-running tests without
            re-executing the code. Requires the 'langsmith[vcr]' package.

    Example:
        For basic usage, simply decorate a test function with `@unit`:

        >>> @unit
        ... def test_addition():
        ...     assert 3 + 4 == 7


        Any code that is traced (such as those traced using `@traceable`
        or `wrap_*` functions) will be traced within the test case for
        improved visibility and debugging.

        >>> from langsmith import traceable
        >>> @traceable
        ... def generate_numbers():
        ...     return 3, 4

        >>> @unit
        ... def test_nested():
        ...     # Traced code will be included in the test case
        ...     a, b = generate_numbers()
        ...     assert a + b == 7

        LLM calls are expensive! Cache requests by setting
        `LANGCHAIN_TEST_CACHE=path/to/cache`. Check in these files to speed up
        CI/CD pipelines, so your results only change when your prompt or requested
        model changes.

        Note that this will require that you install langsmith with the `vcr` extra:

        `pip install -U "langsmith[vcr]"`

        Caching is faster if you install libyaml. See
        https://vcrpy.readthedocs.io/en/latest/installation.html#speed for more details.

        >>> os.environ["LANGCHAIN_TEST_CACHE"] = "tests/cassettes"
        >>> import openai
        >>> from langsmith.wrappers import wrap_openai
        >>> @unit()
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

        The `@unit` decorator works natively with pytest fixtures.
        The values will populate the "inputs" of the corresponding example in LangSmith.

        >>> import pytest
        >>> @pytest.fixture
        ... def some_input():
        ...     return "Some input"
        >>>
        >>> @unit
        ... def test_with_fixture(some_input: str):
        ...     assert "input" in some_input
        >>>

        You can still use pytest.parametrize() as usual to run multiple test cases
        using the same test function.

        >>> @unit(output_keys=["expected"])
        ... @pytest.mark.parametrize(
        ...     "a, b, expected",
        ...     [
        ...         (1, 2, 3),
        ...         (3, 4, 7),
        ...     ],
        ... )
        ... def test_addition_with_multiple_inputs(a: int, b: int, expected: int):
        ...     assert a + b == expected

        By default, each test case will be assigned a consistent, unique identifier
        based on the function name and module. You can also provide a custom identifier
        using the `id` argument:

        >>> @unit(id=uuid.uuid4())
        ... def test_multiplication():
        ...     assert 3 * 4 == 12

        By default, all unit test inputs are saved as "inputs" to a dataset.
        You can specify the `output_keys` argument to persist those keys
        within the dataset's "outputs" fields.

        >>> @pytest.fixture
        ... def expected_output():
        ...     return "input"
        >>> @unit(output_keys=["expected_output"])
        ... def test_with_expected_output(some_input: str, expected_output: str):
        ...     assert expected_output in some_input


        To run these tests, use the pytest CLI. Or directly run the test functions.
        >>> test_addition()
        >>> test_nested()
        >>> test_with_fixture("Some input")
        >>> test_with_expected_output("Some input", "Some")
        >>> test_multiplication()
        >>> test_openai_says_hello()
        >>> test_addition_with_multiple_inputs(1, 2, 3)
    """
    langtest_extra = _UTExtra(
        id=kwargs.pop("id", None),
        output_keys=kwargs.pop("output_keys", None),
        client=kwargs.pop("client", None),
        test_suite_name=kwargs.pop("test_suite_name", None),
        cache=_get_cache(kwargs.pop("cache", None)),
    )
    if kwargs:
        warnings.warn(f"Unexpected keyword arguments: {kwargs.keys()}")
    if os.environ.get("LANGCHAIN_TEST_TRACKING") == "false":
        warnings.warn(
            "LANGCHAIN_TEST_TRACKING is set to 'false'."
            " Skipping LangSmith test tracking."
        )
        return lambda f: f
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


## Private functions


def _get_experiment_name() -> str:
    # TODO Make more easily configurable
    prefix = ls_utils.get_tracer_project(False) or "TestSuiteResult"
    name = f"{prefix}:{uuid.uuid4().hex[:8]}"
    return name


def _get_test_suite_name() -> str:
    # TODO: This naming stuff is inelegant
    test_suite_name = os.environ.get("LANGCHAIN_TEST_SUITE")
    if test_suite_name:
        return test_suite_name
    if __package__:
        return __package__ + " Test Suite"
    git_info = ls_env.get_git_info()
    if git_info:
        if git_info["remote_url"]:
            repo_name = git_info["remote_url"].split("/")[-1].split(".")[0]
            if repo_name:
                return repo_name + " Test Suite"
    raise ValueError("Please set the LANGCHAIN_TEST_SUITE environment variable.")


def _get_cache(cache: Optional[str]) -> Optional[str]:
    if cache is not None:
        return cache
    return os.environ.get("LANGCHAIN_TEST_CACHE")


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


def _get_id(func: Callable, inputs: dict) -> uuid.UUID:
    file_path = Path(inspect.getfile(func)).relative_to(Path.cwd())
    input_json = json.dumps(inputs, sort_keys=True)
    identifier = f"{file_path}::{func.__name__}{input_json}"
    return uuid.uuid5(uuid.NAMESPACE_DNS, identifier)


def _end_tests(
    test_suite: _LangSmithTestSuite,
):
    git_info = ls_env.get_git_info() or {}
    test_suite.client.update_project(
        test_suite.experiment_id,
        end_time=datetime.datetime.now(datetime.timezone.utc),
        metadata={**git_info, "dataset_version": test_suite.get_version()},
    )
    test_suite.wait()


class _LangSmithTestSuite:
    _instance = None
    _lock = threading.RLock()

    def __init__(
        self,
        client: Optional[ls_client.Client],
        experiment: ls_schemas.TracerSessionResult,
        dataset: ls_schemas.Dataset,
    ):
        self.client = client or ls_client.Client()
        self._experiment = experiment
        self._dataset = dataset
        self._version: Optional[datetime.datetime] = None
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        atexit.register(_end_tests, self)

    @property
    def id(self):
        return self._dataset.id

    @property
    def experiment_id(self):
        return self._experiment.id

    @classmethod
    def get_singleton(cls, client: Optional[ls_client.Client]) -> _LangSmithTestSuite:
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

    def submit_result(self, run_id: uuid.UUID, error: Optional[str] = None) -> None:
        self._executor.submit(self._submit_result, run_id, error)

    def _submit_result(self, run_id: uuid.UUID, error: Optional[str] = None) -> None:
        if error:
            self.client.create_feedback(
                run_id, key="pass", score=0, comment=f"Error: {repr(error)}"
            )
        else:
            self.client.create_feedback(
                run_id,
                key="pass",
                score=1,
            )

    def sync_example(self, example_id: uuid.UUID, inputs: dict, outputs: dict) -> None:
        self._executor.submit(self._sync_example, example_id, inputs, outputs)

    def _sync_example(self, example_id: uuid.UUID, inputs: dict, outputs: dict) -> None:
        try:
            example = self.client.read_example(example_id=example_id)
            if inputs != example.inputs or outputs != example.outputs:
                self.client.update_example(
                    example_id=example.id,
                    inputs=inputs,
                    outputs=outputs,
                )
        except ls_utils.LangSmithNotFoundError:
            example = self.client.create_example(
                example_id=example_id,
                inputs=inputs,
                outputs=outputs,
                dataset_id=self.id,
            )
        if example.modified_at:
            self.update_version(example.modified_at)

    def wait(self):
        self._executor.shutdown(wait=True)


class _UTExtra(TypedDict, total=False):
    client: Optional[ls_client.Client]
    id: Optional[uuid.UUID]
    output_keys: Optional[Sequence[str]]
    test_suite_name: Optional[str]
    cache: Optional[str]


def _ensure_example(
    func: Callable, *args: Any, langtest_extra: _UTExtra, **kwargs: Any
) -> Tuple[_LangSmithTestSuite, uuid.UUID]:
    # 1. check if the id exists.
    # TODOs: Local cache + prefer a peek operation
    client = langtest_extra["client"] or ls_client.Client()
    output_keys = langtest_extra["output_keys"]
    signature = inspect.signature(func)
    # 2. Create the example
    inputs: dict = rh._get_inputs_safe(signature, *args, **kwargs)
    example_id = langtest_extra["id"] or _get_id(func, inputs)
    outputs = {}
    if output_keys:
        for k in output_keys:
            outputs[k] = inputs.pop(k, None)
    # TODO: Support multiple test suites
    test_suite = _LangSmithTestSuite.get_singleton(client)
    test_suite.sync_example(example_id, inputs, outputs)
    return test_suite, example_id


def _run_test(func, *test_args, langtest_extra: _UTExtra, **test_kwargs):
    test_suite, example_id = _ensure_example(
        func, *test_args, **test_kwargs, langtest_extra=langtest_extra
    )
    run_id = uuid.uuid4()

    def _test():
        try:
            func_ = func if rh.is_traceable_function(func) else rh.traceable(func)
            func_(
                *test_args,
                **test_kwargs,
                langsmith_extra={
                    "run_id": run_id,
                    "reference_example_id": example_id,
                    "project_name": test_suite.name,
                },
            )
        except BaseException as e:
            test_suite.submit_result(run_id, error=repr(e))
            raise e
        try:
            test_suite.submit_result(run_id, error=None)
        except BaseException as e:
            logger.warning(f"Failed to create feedback for run_id {run_id}: {e}")

    if langtest_extra["cache"]:
        try:
            import vcr  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                "vcrpy is required to use caching. Install with:"
                'pip install -U "langsmith[vcr]"'
            )
        ignore_hosts = [test_suite.client.api_url]

        def _filter_request_headers(request: Any) -> Any:
            if any(request.url.startswith(host) for host in ignore_hosts):
                return None
            request.headers = {}
            return request

        ls_vcr = vcr.VCR(
            serializer="yaml",
            cassette_library_dir=langtest_extra["cache"],
            # Replay previous requests, record new ones
            # TODO: Support other modes
            record_mode="new_episodes",
            match_on=["uri", "method", "path", "body"],
            filter_headers=["authorization", "Set-Cookie"],
            before_record_request=_filter_request_headers,
        )

        with ls_vcr.use_cassette(f"{test_suite.id}.yaml"):
            _test()
    else:
        _test()
