from __future__ import annotations

import atexit
import contextlib
import contextvars
import datetime
import functools
import importlib
import inspect
import logging
import os
import threading
import time
import uuid
import warnings
from collections import defaultdict
from concurrent.futures import Future
from pathlib import Path
from typing import (
    Any,
    Callable,
    Generator,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    cast,
    overload,
)

from typing_extensions import TypedDict

from langsmith import client as ls_client
from langsmith import env as ls_env
from langsmith import run_helpers as rh
from langsmith import run_trees
from langsmith import run_trees as rt
from langsmith import schemas as ls_schemas
from langsmith import utils as ls_utils
from langsmith._internal import _orjson
from langsmith._internal._beta_decorator import warn_beta
from langsmith._internal._serde import dumps_json
from langsmith.client import ID_TYPE

try:
    import pytest  # type: ignore

    SkipException = pytest.skip.Exception
except ImportError:

    class SkipException(Exception):  # type: ignore[no-redef]
        pass


logger = logging.getLogger(__name__)


T = TypeVar("T")
U = TypeVar("U")


@overload
def test(
    func: Callable,
) -> Callable: ...


@overload
def test(
    *,
    id: Optional[uuid.UUID] = None,
    output_keys: Optional[Sequence[str]] = None,
    client: Optional[ls_client.Client] = None,
    test_suite_name: Optional[str] = None,
) -> Callable[[Callable], Callable]: ...


def test(*args: Any, **kwargs: Any) -> Callable:
    """Trace a pytest test case in LangSmith.

    This decorator is used to trace a pytest test to LangSmith. It ensures
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

    Environment:
        - LANGSMITH_TEST_CACHE: If set, API calls will be cached to disk to
            save time and costs during testing. Recommended to commit the
            cache files to your repository for faster CI/CD runs.
            Requires the 'langsmith[vcr]' package to be installed.
        - LANGSMITH_TEST_TRACKING: Set this variable to the path of a directory
            to enable caching of test results. This is useful for re-running tests
             without re-executing the code. Requires the 'langsmith[vcr]' package.

    Example:
        For basic usage, simply decorate a test function with `@pytest.mark.langsmith`.
        Under the hood this will call the `test` method:

        >>> import pytest
        >>>
        >>> # Equivalently can decorate with `test` directly:
        >>> # from langsmith import test
        >>> # @test
        >>> @pytest.mark.langsmith
        ... def test_addition():
        ...     assert 3 + 4 == 7


        Any code that is traced (such as those traced using `@traceable`
        or `wrap_*` functions) will be traced within the test case for
        improved visibility and debugging.

        >>> import pytest
        >>> from langsmith import traceable
        >>>
        >>> @traceable
        ... def generate_numbers():
        ...     return 3, 4

        >>> @pytest.mark.langsmith
        ... def test_nested():
        ...     # Traced code will be included in the test case
        ...     a, b = generate_numbers()
        ...     assert a + b == 7

        LLM calls are expensive! Cache requests by setting
        `LANGSMITH_TEST_CACHE=path/to/cache`. Check in these files to speed up
        CI/CD pipelines, so your results only change when your prompt or requested
        model changes.

        Note that this will require that you install langsmith with the `vcr` extra:

        `pip install -U "langsmith[vcr]"`

        Caching is faster if you install libyaml. See
        https://vcrpy.readthedocs.io/en/latest/installation.html#speed for more details.

        >>> # os.environ["LANGSMITH_TEST_CACHE"] = "tests/cassettes"
        >>> import openai
        >>> import pytest
        >>> from langsmith import wrappers
        >>>
        >>> oai_client = wrappers.wrap_openai(openai.Client())
        >>> @pytest.mark.langsmith
        ... def test_openai_says_hello():
        ...     # Traced code will be included in the test case
        ...     response = oai_client.chat.completions.create(
        ...         model="gpt-3.5-turbo",
        ...         messages=[
        ...             {"role": "system", "content": "You are a helpful assistant."},
        ...             {"role": "user", "content": "Say hello!"},
        ...         ],
        ...     )
        ...     assert "hello" in response.choices[0].message.content.lower()

        LLMs are stochastic. Naive assertions are flakey. You can use langsmith's
        `expect` to score and make approximate assertions on your results.

        >>> import pytest
        >>> from langsmith import expect
        >>>
        >>> @pytest.mark.langsmith
        ... def test_output_semantically_close():
        ...     response = oai_client.chat.completions.create(
        ...         model="gpt-3.5-turbo",
        ...         messages=[
        ...             {"role": "system", "content": "You are a helpful assistant."},
        ...             {"role": "user", "content": "Say hello!"},
        ...         ],
        ...     )
        ...     # The embedding_distance call logs the embedding distance to LangSmith
        ...     expect.embedding_distance(
        ...         prediction=response.choices[0].message.content,
        ...         reference="Hello!",
        ...         # The following optional assertion logs a
        ...         # pass/fail score to LangSmith
        ...         # and raises an AssertionError if the assertion fails.
        ...     ).to_be_less_than(1.0)
        ...     # Compute damerau_levenshtein distance
        ...     expect.edit_distance(
        ...         prediction=response.choices[0].message.content,
        ...         reference="Hello!",
        ...         # And then log a pass/fail score to LangSmith
        ...     ).to_be_less_than(1.0)

        The `@test` decorator works natively with pytest fixtures.
        The values will populate the "inputs" of the corresponding example in LangSmith.

        >>> import pytest
        >>>
        >>> @pytest.fixture
        ... def some_input():
        ...     return "Some input"
        >>>
        >>> @pytest.mark.langsmith
        ... def test_with_fixture(some_input: str):
        ...     assert "input" in some_input
        >>>

        You can still use pytest.parametrize() as usual to run multiple test cases
        using the same test function.

        >>> import pytest
        >>>
        >>> @pytest.mark.langsmith(output_keys=["expected"])
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
        >>> import pytest
        >>> import uuid
        >>>
        >>> example_id = uuid.uuid4()
        >>> @pytest.mark.langsmith(id=str(example_id))
        ... def test_multiplication():
        ...     assert 3 * 4 == 12

        By default, all test inputs are saved as "inputs" to a dataset.
        You can specify the `output_keys` argument to persist those keys
        within the dataset's "outputs" fields.

        >>> import pytest
        >>>
        >>> @pytest.fixture
        ... def expected_output():
        ...     return "input"
        >>>
        >>> @pytest.mark.langsmith(output_keys=["expected_output"])
        ... def test_with_expected_output(some_input: str, expected_output: str):
        ...     assert expected_output in some_input


        To run these tests, use the pytest CLI. Or directly run the test functions.
        >>> test_output_semantically_close()
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
        cache=ls_utils.get_cache_dir(kwargs.pop("cache", None)),
    )
    if kwargs:
        warnings.warn(f"Unexpected keyword arguments: {kwargs.keys()}")
    disable_tracking = ls_utils.test_tracking_is_disabled()
    if disable_tracking:
        warnings.warn(
            "LANGSMITH_TEST_TRACKING is set to 'false'."
            " Skipping LangSmith test tracking."
        )

    def decorator(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*test_args: Any, **test_kwargs: Any):
                if disable_tracking:
                    return await func(*test_args, **test_kwargs)
                await _arun_test(
                    func, *test_args, **test_kwargs, langtest_extra=langtest_extra
                )

            return async_wrapper

        @functools.wraps(func)
        def wrapper(*test_args: Any, request: Any, **test_kwargs: Any):
            if disable_tracking:
                return func(*test_args, **test_kwargs)
            _run_test(
                func,
                *test_args,
                request=request,
                **test_kwargs,
                langtest_extra=langtest_extra,
            )

        return wrapper

    if args and callable(args[0]):
        return decorator(args[0])

    return decorator


## Private functions


def _get_experiment_name(test_suite_name: str) -> str:
    # If this is a pytest-xdist multi-process run then we need to create the same
    # experiment name across processes. We can do this by accessing the
    # PYTEST_XDIST_TESTRUNID env var.
    if os.environ.get("PYTEST_XDIST_TESTRUNUID") and importlib.util.find_spec("xdist"):
        id_name = test_suite_name + os.environ["PYTEST_XDIST_TESTRUNUID"]
        id_ = str(uuid.uuid5(uuid.NAMESPACE_DNS, id_name).hex[:8])
    else:
        id_ = str(uuid.uuid4().hex[:8])

    if os.environ.get("LANGSMITH_EXPERIMENT"):
        prefix = os.environ["LANGSMITH_EXPERIMENT"]
    else:
        prefix = ls_utils.get_tracer_project(False) or "TestSuiteResult"
    name = f"{prefix}:{id_}"
    return name


def _get_test_suite_name(func: Callable) -> str:
    test_suite_name = ls_utils.get_env_var("TEST_SUITE")
    if test_suite_name:
        return test_suite_name
    repo_name = ls_env.get_git_info()["repo_name"]
    try:
        mod = inspect.getmodule(func)
        if mod:
            return f"{repo_name}.{mod.__name__}"
    except BaseException:
        logger.debug("Could not determine test suite name from file path.")

    raise ValueError("Please set the LANGSMITH_TEST_SUITE environment variable.")


def _get_test_suite(
    client: ls_client.Client, test_suite_name: str
) -> ls_schemas.Dataset:
    if client.has_dataset(dataset_name=test_suite_name):
        return client.read_dataset(dataset_name=test_suite_name)
    else:
        repo = ls_env.get_git_info().get("remote_url") or ""
        description = "Test suite"
        if repo:
            description += f" for {repo}"
        try:
            return client.create_dataset(
                dataset_name=test_suite_name, description=description
            )
        except ls_utils.LangSmithConflictError:
            return client.read_dataset(dataset_name=test_suite_name)


def _start_experiment(
    client: ls_client.Client,
    test_suite: ls_schemas.Dataset,
) -> ls_schemas.TracerSession:
    experiment_name = _get_experiment_name(test_suite.name)
    try:
        return client.create_project(
            experiment_name,
            reference_dataset_id=test_suite.id,
            description="Test Suite Results.",
            metadata={
                "revision_id": ls_env.get_langchain_env_var_metadata().get(
                    "revision_id"
                )
            },
        )
    except ls_utils.LangSmithConflictError:
        return client.read_project(project_name=experiment_name)


def _get_example_id(
    func: Callable, inputs: dict, suite_id: uuid.UUID
) -> Tuple[uuid.UUID, str]:
    try:
        file_path = str(Path(inspect.getfile(func)).relative_to(Path.cwd()))
    except ValueError:
        # Fall back to module name if file path is not available
        file_path = func.__module__
    identifier = f"{suite_id}{file_path}::{func.__name__}"
    # If parametrized test, need to add inputs to identifier:
    if hasattr(func, "pytestmark") and any(
        m.name == "parametrize" for m in func.pytestmark
    ):
        identifier += _stringify(inputs)
    return uuid.uuid5(uuid.NAMESPACE_DNS, identifier), identifier[len(str(suite_id)) :]


def _end_tests(test_suite: _LangSmithTestSuite):
    git_info = ls_env.get_git_info() or {}
    test_suite.client.update_project(
        test_suite.experiment_id,
        end_time=datetime.datetime.now(datetime.timezone.utc),
        metadata={
            **git_info,
            "dataset_version": test_suite.get_version(),
            "revision_id": ls_env.get_langchain_env_var_metadata().get("revision_id"),
        },
    )
    test_suite.shutdown()


VT = TypeVar("VT", bound=Optional[dict])


def _serde_example_values(values: VT) -> VT:
    if values is None:
        return values
    bts = ls_client._dumps_json(values)
    return _orjson.loads(bts)


class _LangSmithTestSuite:
    _instances: Optional[dict] = None
    _lock = threading.RLock()

    def __init__(
        self,
        client: Optional[ls_client.Client],
        experiment: ls_schemas.TracerSession,
        dataset: ls_schemas.Dataset,
    ):
        self.client = client or rt.get_cached_client()
        self._experiment = experiment
        self._dataset = dataset
        self._version: Optional[datetime.datetime] = None
        self._executor = ls_utils.ContextThreadPoolExecutor(max_workers=1)
        self._example_futures: dict[ID_TYPE, list[Future]] = defaultdict(list)
        atexit.register(_end_tests, self)

    @property
    def id(self):
        return self._dataset.id

    @property
    def experiment_id(self):
        return self._experiment.id

    @property
    def experiment(self):
        return self._experiment

    @classmethod
    def from_test(
        cls,
        client: Optional[ls_client.Client],
        func: Callable,
        test_suite_name: Optional[str] = None,
    ) -> _LangSmithTestSuite:
        client = client or rt.get_cached_client()
        test_suite_name = test_suite_name or _get_test_suite_name(func)
        with cls._lock:
            if not cls._instances:
                cls._instances = {}
            if test_suite_name not in cls._instances:
                test_suite = _get_test_suite(client, test_suite_name)
                experiment = _start_experiment(client, test_suite)
                cls._instances[test_suite_name] = cls(client, experiment, test_suite)
        return cls._instances[test_suite_name]

    @property
    def name(self):
        return self._experiment.name

    def update_version(self, version: datetime.datetime) -> None:
        with self._lock:
            if self._version is None or version > self._version:
                self._version = version

    def get_version(self) -> Optional[datetime.datetime]:
        with self._lock:
            return self._version

    def submit_result(
        self,
        run_id: uuid.UUID,
        error: Optional[str] = None,
        skipped: bool = False,
        plugin=None,
        nodeid=None,
    ) -> None:
        self._executor.submit(
            self._submit_result,
            run_id,
            error,
            skipped=skipped,
            plugin=plugin,
            nodeid=nodeid,
        )

    def _submit_result(
        self,
        run_id: uuid.UUID,
        error: Optional[str] = None,
        skipped: bool = False,
        plugin=None,
        nodeid=None,
    ) -> None:
        if error:
            if skipped:
                self.client.create_feedback(
                    run_id,
                    key="pass",
                    # Don't factor into aggregate score
                    score=None,
                    comment=f"Skipped: {repr(error)}",
                )
                status = "skipped"
            else:
                self.client.create_feedback(
                    run_id, key="pass", score=0, comment=f"Error: {repr(error)}"
                )
                status = "failed"
        else:
            self.client.create_feedback(
                run_id,
                key="pass",
                score=1,
            )
            status = "passed"
        if plugin and nodeid:
            plugin.update_process_status(nodeid, {"status": status})

    def sync_example(
        self,
        example_id: uuid.UUID,
        *,
        inputs: Optional[dict] = None,
        outputs: Optional[dict] = None,
        metadata: Optional[dict] = None,
        plugin=None,
        nodeid=None,
    ) -> None:
        future = self._executor.submit(
            self._sync_example,
            example_id,
            inputs,
            outputs,
            metadata.copy() if metadata else metadata,
            plugin,
            nodeid,
        )
        with self._lock:
            self._example_futures[example_id].append(future)

    def _sync_example(
        self,
        example_id: uuid.UUID,
        inputs: Optional[dict],
        outputs: Optional[dict],
        metadata: Optional[dict],
        plugin: Any,
        nodeid: Any,
    ) -> None:
        inputs_ = _serde_example_values(inputs) if inputs else inputs
        outputs_ = _serde_example_values(outputs) if outputs else outputs
        try:
            example = self.client.read_example(example_id=example_id)
        except ls_utils.LangSmithNotFoundError:
            example = self.client.create_example(
                example_id=example_id,
                inputs=inputs_,
                outputs=outputs_,
                dataset_id=self.id,
                metadata=metadata,
                created_at=self._experiment.start_time,
            )
        else:
            if (
                inputs_ != example.inputs
                or outputs_ != example.outputs
                or str(example.dataset_id) != str(self.id)
            ):
                self.client.update_example(
                    example_id=example.id,
                    inputs=inputs_,
                    outputs=outputs_,
                    metadata=metadata,
                    dataset_id=self.id,
                )
        if example.modified_at:
            self.update_version(example.modified_at)

        if plugin and nodeid:
            update = {"inputs": inputs, "reference_outputs": outputs}
            update = {k: v for k, v in update.items() if v is not None}
            plugin.update_process_status(nodeid, update)

    def _submit_feedback(
        self, run_id: ID_TYPE, feedback: Union[dict, list], **kwargs: Any
    ):
        feedback = feedback if isinstance(feedback, list) else [feedback]
        for fb in feedback:
            self._executor.submit(
                self._create_feedback, run_id=run_id, feedback=fb, **kwargs
            )

    def _create_feedback(
        self, run_id: ID_TYPE, feedback: dict, plugin=None, nodeid=None, **kwargs: Any
    ) -> None:
        trace_id = self.client.read_run(run_id).trace_id
        self.client.create_feedback(trace_id, **feedback, **kwargs)
        if plugin and nodeid:
            val = feedback["score"] if "score" in feedback else feedback["val"]
            plugin.update_process_status(nodeid, {"feedback": {feedback["key"]: val}})

    def shutdown(self):
        self._executor.shutdown(wait=True)

    def wait_example_updates(self, example_id: ID_TYPE):
        """Wait for all example updates to complete."""
        while self._example_futures[example_id]:
            self._example_futures[example_id].pop().result()

    def end_run(self, run_tree, example_id, outputs) -> Future:
        return self._executor.submit(
            self._end_run, run_tree=run_tree, example_id=example_id, outputs=outputs
        )

    def _end_run(self, run_tree, example_id, outputs) -> None:
        # Ensure example is fully updated
        self.wait_example_updates(example_id)
        # Ensure that run end time is after example modified at.
        end_time = cast(
            datetime.datetime, self.client.read_example(example_id).modified_at
        ) + datetime.timedelta(seconds=0.01)
        run_tree.end(outputs=outputs, end_time=end_time)
        run_tree.patch()


class _TestCase:
    def __init__(
        self,
        test_suite: _LangSmithTestSuite,
        example_id: uuid.UUID,
        plugin=None,
        nodeid=None,
    ) -> None:
        self.test_suite = test_suite
        self.example_id = example_id
        self.plugin = plugin
        self.nodeid = nodeid

    def sync_example(
        self, *, inputs: Optional[dict] = None, outputs: Optional[dict] = None
    ) -> None:
        self.test_suite.sync_example(
            self.example_id,
            inputs=inputs,
            outputs=outputs,
            plugin=self.plugin,
            nodeid=self.nodeid,
        )

    def submit_feedback(self, *args, **kwargs: Any):
        self.test_suite._submit_feedback(
            *args, **kwargs, plugin=self.plugin, nodeid=self.nodeid
        )

    def log_outputs(self, outputs: dict) -> None:
        if self.plugin and self.nodeid:
            self.plugin.update_process_status(self.nodeid, {"outputs": outputs})


_TEST_CASE = contextvars.ContextVar[Optional[_TestCase]]("_TEST_CASE", default=None)


class _UTExtra(TypedDict, total=False):
    client: Optional[ls_client.Client]
    id: Optional[uuid.UUID]
    output_keys: Optional[Sequence[str]]
    test_suite_name: Optional[str]
    cache: Optional[str]


def _get_test_repr(func: Callable, sig: inspect.Signature) -> str:
    name = getattr(func, "__name__", None) or ""
    description = getattr(func, "__doc__", None) or ""
    if description:
        description = f" - {description.strip()}"
    return f"{name}{sig}{description}"


def _ensure_example(
    func: Callable, *args: Any, langtest_extra: _UTExtra, **kwargs: Any
) -> Tuple[_LangSmithTestSuite, uuid.UUID]:
    client = langtest_extra["client"] or rt.get_cached_client()
    output_keys = langtest_extra["output_keys"]
    signature = inspect.signature(func)
    inputs: dict = rh._get_inputs_safe(signature, *args, **kwargs)
    outputs = {}
    if output_keys:
        for k in output_keys:
            outputs[k] = inputs.pop(k, None)
    test_suite = _LangSmithTestSuite.from_test(
        client, func, langtest_extra.get("test_suite_name")
    )
    example_id, example_name = _get_example_id(func, inputs, test_suite.id)
    example_id = langtest_extra["id"] or example_id
    test_suite.sync_example(
        example_id,
        inputs=inputs,
        outputs=outputs,
        metadata={"signature": _get_test_repr(func, signature), "name": example_name},
    )
    return test_suite, example_id


def _run_test(
    func: Callable,
    *test_args: Any,
    request: Any,
    langtest_extra: _UTExtra,
    **test_kwargs: Any,
) -> None:
    test_suite, example_id = _ensure_example(
        func, *test_args, **test_kwargs, langtest_extra=langtest_extra, request=request
    )
    plugin = request.config.pluginmanager.get_plugin("custom_output_plugin")
    _TEST_CASE.set(
        _TestCase(test_suite, example_id, plugin=plugin, nodeid=request.node.nodeid)
    )
    run_id = uuid.uuid4()
    # Get the plugin instance

    def _test():
        func_inputs = rh._get_inputs_safe(
            inspect.signature(func), *test_args, **test_kwargs
        )
        # Make sure example is created before creating a run that references it.
        with rh.trace(
            name=getattr(func, "__name__", "Test"),
            run_id=run_id,
            reference_example_id=example_id,
            inputs=func_inputs,
            project_name=test_suite.name,
            exceptions_to_handle=(SkipException,),
        ) as run_tree:
            if plugin and request.node.nodeid:
                plugin.update_process_status(
                    request.node.nodeid, {"start_time": time.time()}
                )
            try:
                result = func(*test_args, **test_kwargs)
            except SkipException as e:
                test_suite.submit_result(
                    run_id,
                    error=repr(e),
                    skipped=True,
                    plugin=plugin,
                    nodeid=request.node.nodeid,
                )
                outputs = {"skipped_reason": repr(e)}
                test_suite.end_run(run_tree, example_id, outputs)
                raise e
            except BaseException as e:
                test_suite.submit_result(
                    run_id, error=repr(e), plugin=plugin, nodeid=request.node.nodeid
                )
                raise e
            else:
                outputs = (
                    result
                    if result is None or isinstance(result, dict)
                    else {"output": result}
                )
                test_suite.end_run(run_tree, example_id, outputs)
            finally:
                if plugin and request.node.nodeid:
                    plugin.update_process_status(
                        request.node.nodeid, {"end_time": time.time()}
                    )
        try:
            test_suite.submit_result(
                run_id, error=None, plugin=plugin, nodeid=request.node.nodeid
            )
        except BaseException as e:
            logger.warning(f"Failed to create feedback for run_id {run_id}: {e}")

    cache_path = (
        Path(langtest_extra["cache"]) / f"{test_suite.id}.yaml"
        if langtest_extra["cache"]
        else None
    )
    current_context = rh.get_tracing_context()
    metadata = {
        **(current_context["metadata"] or {}),
        **{
            "experiment": test_suite.experiment.name,
            "reference_example_id": str(example_id),
        },
    }
    with rh.tracing_context(
        **{**current_context, "metadata": metadata}
    ), ls_utils.with_optional_cache(
        cache_path, ignore_hosts=[test_suite.client.api_url]
    ):
        _test()


async def _arun_test(
    func: Callable, *test_args: Any, langtest_extra: _UTExtra, **test_kwargs: Any
) -> None:
    test_suite, example_id = _ensure_example(
        func, *test_args, **test_kwargs, langtest_extra=langtest_extra
    )
    _TEST_CASE.set(_TestCase(test_suite, example_id))
    run_id = uuid.uuid4()

    async def _test():
        func_inputs = rh._get_inputs_safe(
            inspect.signature(func), *test_args, **test_kwargs
        )
        with rh.trace(
            name=getattr(func, "__name__", "Test"),
            run_id=run_id,
            reference_example_id=example_id,
            inputs=func_inputs,
            project_name=test_suite.name,
            exceptions_to_handle=(SkipException,),
        ) as run_tree:
            try:
                result = await func(*test_args, **test_kwargs)
            except SkipException as e:
                test_suite.submit_result(run_id, error=repr(e), skipped=True)
                outputs = {"skipped_reason": repr(e)}
                test_suite.end_run(run_tree, example_id, outputs)
                raise e
            except BaseException as e:
                test_suite.submit_result(run_id, error=repr(e))
                raise e
            else:
                outputs = (
                    result
                    if result is None or isinstance(result, dict)
                    else {"output": result}
                )
                test_suite.end_run(run_tree, example_id, outputs)
        try:
            test_suite.submit_result(run_id, error=None)
        except BaseException as e:
            logger.warning(f"Failed to create feedback for run_id {run_id}: {e}")

    cache_path = (
        Path(langtest_extra["cache"]) / f"{test_suite.id}.yaml"
        if langtest_extra["cache"]
        else None
    )
    current_context = rh.get_tracing_context()
    metadata = {
        **(current_context["metadata"] or {}),
        **{
            "experiment": test_suite.experiment.name,
            "reference_example_id": str(example_id),
        },
    }
    with rh.tracing_context(
        **{**current_context, "metadata": metadata}
    ), ls_utils.with_optional_cache(
        cache_path, ignore_hosts=[test_suite.client.api_url]
    ):
        await _test()


# For backwards compatibility
unit = test


@warn_beta
def log_inputs(inputs: dict, /) -> None:
    """Log run inputs from within a pytest test run.

    Should only be used in pytest tests decorated with @pytest.mark.langsmith.

    Args:
        inputs: Inputs to log.

    Example:
        >>> from langsmith import testing
        >>>
        >>> @pytest.mark.langsmith
        ... def test_foo() -> None:
        ...     x = 0
        ...     y = 1
        ...     testing.log_inputs({"x": x, "y": y})
        ...     assert foo(x, y) == 2
    """
    run_tree = rh.get_current_run_tree()
    test_case = _TEST_CASE.get()
    if not run_tree or not test_case:
        msg = (
            "log_inputs should only be called within a pytest test decorated with "
            "@pytest.mark.langsmith, and with tracing enabled (by setting the "
            "LANGSMITH_TRACING environment variable to 'true')."
        )
        raise ValueError(msg)
    run_tree.add_inputs(inputs)
    test_case.sync_example(inputs=inputs)


@warn_beta
def log_outputs(outputs: dict, /) -> None:
    """Log run outputs from within a pytest test run.

    Should only be used in pytest tests decorated with @pytest.mark.langsmith.

    Args:
        outputs: Outputs to log.

    Example:
        >>> from langsmith import testing
        >>>
        >>> @pytest.mark.langsmith
        ... def test_foo() -> None:
        ...     x = 0
        ...     y = 1
        ...     result = foo(x, y)
        ...     testing.log_outputs({"foo": result})
        ...     assert result == 2
    """
    run_tree = rh.get_current_run_tree()
    test_case = _TEST_CASE.get()
    if not run_tree or not test_case:
        msg = (
            "log_outputs should only be called within a pytest test decorated with "
            "@pytest.mark.langsmith, and with tracing enabled (by setting the "
            "LANGSMITH_TRACING environment variable to 'true')."
        )
        raise ValueError(msg)
    run_tree.add_outputs(outputs)
    test_case.log_outputs(outputs)


@warn_beta
def log_reference_outputs(outputs: dict, /) -> None:
    """Log example reference outputs from within a pytest test run.

    Should only be used in pytest tests decorated with @pytest.mark.langsmith.

    Args:
        outputs: Reference outputs to log.

    Example:
        >>> from langsmith import testing
        >>>
        >>> @pytest.mark.langsmith
        ... def test_foo() -> None:
        ...     x = 0
        ...     y = 1
        ...     expected = 2
        ...     testing.log_reference_outputs({"foo": expected})
        ...     assert foo(x, y) == expected
    """
    test_case = _TEST_CASE.get()
    if not test_case:
        msg = (
            "log_reference_outputs should only be called within a pytest test "
            "decorated with @pytest.mark.langsmith."
        )
        raise ValueError(msg)
    test_case.sync_example(outputs=outputs)


@warn_beta
def log_feedback(
    feedback: Optional[Union[dict, list[dict]]] = None,
    /,
    *,
    key: str,
    score: Optional[Union[int, bool, float]] = None,
    value: Optional[Union[str, int, float, bool]] = None,
    **kwargs: Any,
) -> None:
    """Log run feedback from within a pytest test run.

    Should only be used in pytest tests decorated with @pytest.mark.langsmith.

    Args:
        key: Feedback name.
        score: Numerical feedback value.
        value: Categorical feedback value
        kwargs: Any other Client.create_feedback args.

    Example:
        >>> import pytest
        >>> from langsmith import testing
        >>>
        >>> @pytest.mark.langsmith
        ... def test_foo() -> None:
        ...     x = 0
        ...     y = 1
        ...     expected = 2
        ...     result = foo(x, y)
        ...     testing.log_feedback(key="right_type", score=isinstance(result, int))
        ...     assert result == expected
    """
    if feedback and any((key, score, value)):
        msg = "Must specify one of 'feedback' and ('key', 'score', 'value'), not both."
        raise ValueError(msg)
    elif not (feedback or key):
        msg = "Must specify at least one of 'feedback' or ('key', 'score', value')."
        raise ValueError(msg)
    elif key:
        feedback = {"key": key}
        if score is not None:
            feedback["score"] = score
        if value is not None:
            feedback["value"] = value
    else:
        pass

    run_tree = rh.get_current_run_tree()
    test_case = _TEST_CASE.get()
    if not run_tree or not test_case:
        msg = (
            "log_feedback should only be called within a pytest test decorated with "
            "@pytest.mark.langsmith, and with tracing enabled (by setting the "
            "LANGSMITH_TRACING environment variable to 'true')."
        )
        raise ValueError(msg)
    if run_tree.session_name == "evaluators" and run_tree.metadata.get(
        "reference_run_id"
    ):
        run_id = run_tree.metadata["reference_run_id"]
        run_tree.add_outputs(
            feedback if isinstance(feedback, dict) else {"feedback": feedback}
        )
        kwargs["source_run_id"] = run_tree.id
    else:
        run_id = run_tree.trace_id
    test_case.submit_feedback(run_id, cast(Union[list, dict], feedback), **kwargs)


@warn_beta
@contextlib.contextmanager
def trace_feedback(
    *, name: str = "Feedback"
) -> Generator[run_trees.RunTree, None, None]:
    """Trace the computation of a pytest run feedback as its own run.

    Args:
        name: Feedback run name. Defaults to "Feedback".

    Example:
        .. code-block:: python

            import openai
            import pytest

            from langsmith import testing, wrappers

            oai_client = wrappers.wrap_openai(openai.Client())


            @pytest.mark.langsmith
            def test_openai_says_hello():
                # Traced code will be included in the test case
                text = "Say hello!"
                response = oai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": text},
                    ],
                )
                testing.log_inputs({"text": text})
                testing.log_outputs({"response": response.choices[0].message.content})
                testing.log_reference_outputs({"response": "hello!"})

                # Use this context manager to trace any steps used for generating evaluation
                # feedback separately from the main application logic
                with testing.trace_feedback():
                    grade = oai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "system",
                                "content": "Return 1 if 'hello' is in the user message and 0 otherwise.",
                            },
                            {
                                "role": "user",
                                "content": response.choices[0].message.content,
                            },
                        ],
                    )
                    testing.log_feedback(
                        key="llm_judge", score=float(grade.choices[0].message.content)
                    )

                assert "hello" in response.choices[0].message.content.lower()
    """  # noqa: E501
    parent_run = rh.get_current_run_tree()
    test_case = _TEST_CASE.get()
    if not parent_run or not test_case:
        msg = (
            "trace_feedback should only be called within a pytest test decorated with "
            "@pytest.mark.langsmith, and with tracing enabled (by setting the "
            "LANGSMITH_TRACING environment variable to 'true')."
        )
        raise ValueError(msg)
    metadata = {
        "experiment": test_case.test_suite.experiment.name,
        "reference_example_id": test_case.example_id,
        "reference_run_id": parent_run.id,
    }
    with rh.trace(
        name=name,
        inputs=parent_run.outputs,
        parent="ignore",
        project_name="evaluators",
        metadata=metadata,
    ) as run_tree:
        yield run_tree


def _stringify(x: Any) -> str:
    try:
        return dumps_json(x).decode("utf-8", errors="surrogateescape")
    except Exception:
        return str(x)
