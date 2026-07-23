import datetime
import uuid
from unittest.mock import MagicMock

from langsmith.testing._internal import (
    _get_example_id,
    _LangSmithTestSuite,
    _serde_example_values,
    _TestCase,
)


def test__serde_example_values():
    class Foo:
        def __init__(self, a, b):
            self.a = a
            self.b = b

    results = _serde_example_values({"foo": Foo(1, 2)})
    assert "foo" in results
    assert isinstance(results["foo"], str)


def test__get_id():
    class Foo:
        bar: str = "baz"  # type: ignore

        def __init__(self, a: int, b: int):
            self.a = a
            self.b = b

    def foo(x: Foo):
        return x

    dataset_id = "4e32bff6-5762-4906-8d74-ee2bd0f1d234"
    inputs = {"x": Foo(1, 2)}
    outputs = {"y": Foo(3, 4)}

    result = _get_example_id(dataset_id, inputs, outputs)
    assert isinstance(result, uuid.UUID)


def test_log_inputs_updates_test_case_inputs():
    """Test that calling log_inputs updates _TestCase.inputs.

    When a test has fixture params (e.g. model: BaseChatModel), the initial
    inputs captured from the function signature include the fixture values.
    Calling log_inputs should update self.inputs so that example ID generation
    in end_run uses the correct inputs.
    """
    mock_test_suite = MagicMock()
    mock_test_suite.id = uuid.uuid4()

    test_case = _TestCase(
        test_suite=mock_test_suite,
        run_id=uuid.uuid4(),
        inputs={"model": "<fixture object>", "db": "<db fixture>"},
    )

    # Before log_inputs, inputs reflect fixtures
    assert test_case.inputs == {"model": "<fixture object>", "db": "<db fixture>"}

    # User calls t.log_inputs({"question": "fix typo"}) inside their test.
    # The global log_inputs merges into run_tree then passes run_tree.inputs
    # to test_case.log_inputs. Simulate that merged result:
    test_case.log_inputs({"question": "fix typo"})

    assert test_case.inputs == {"question": "fix typo"}

    # Verify the example ID is now derived from the logged inputs,
    # not the original fixture-based inputs
    dataset_id = str(mock_test_suite.id)
    expected_id = _get_example_id(dataset_id, {"question": "fix typo"})
    fixture_id = _get_example_id(
        dataset_id, {"model": "<fixture object>", "db": "<db fixture>"}
    )
    # end_run falls back to _get_example_id when no explicit id is set
    actual_id = _get_example_id(dataset_id, test_case.inputs or {})
    assert actual_id == expected_id
    assert actual_id != fixture_id


def test_pytest_feedback_includes_experiment_id_and_run_start_time():
    experiment_id = uuid.uuid4()
    run_id = uuid.uuid4()
    start_time = datetime.datetime.now(datetime.timezone.utc)
    test_suite = object.__new__(_LangSmithTestSuite)
    test_suite.client = MagicMock()
    test_suite._experiment = MagicMock(id=experiment_id)
    test_suite._executor = MagicMock()
    test_suite._executor.submit.side_effect = lambda fn, *args, **kwargs: fn(
        *args, **kwargs
    )

    test_suite._submit_result(run_id, start_time, 1)
    test_suite._submit_feedback(
        run_id,
        {"key": "quality", "score": 0.75},
        start_time=start_time,
    )

    assert test_suite.client.create_feedback.call_count == 2
    for call in test_suite.client.create_feedback.call_args_list:
        assert call.args[0] == run_id
        assert call.kwargs["session_id"] == experiment_id
        assert call.kwargs["start_time"] == start_time
