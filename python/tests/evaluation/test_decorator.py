import importlib
import os
import random
import time

import pytest

from langsmith import testing as t
from langsmith import traceable

pytestmark = pytest.mark.skipif(
    not os.getenv("LANGSMITH_TRACING"),
    reason="LANGSMITH_TRACING environment variable not set",
)


@pytest.mark.langsmith
@pytest.mark.parametrize("c", list(range(10)))
async def test_addition_single(c):
    x = 3
    y = 4
    t.log_inputs({"x": x, "y": y, "c": c})

    expected = 7 + c
    t.log_reference_outputs({"sum": expected})

    actual = x + y + c
    t.log_outputs({"sum": actual})

    t.log_feedback(key="foo", score=1)

    assert actual == expected


async def my_app():
    return "hello"


@pytest.mark.langsmith
async def test_openai_says_hello():
    # Traced code will be included in the test case
    text = "Say hello!"
    response = await my_app()
    t.log_inputs({"text": text})
    t.log_outputs({"response": response})
    t.log_reference_outputs({"response": "hello!"})

    # Use this context manager to trace any steps used for generating evaluation
    # feedback separately from the main application logic
    with t.trace_feedback():
        grade = 1 if "hello" in response else 0
        t.log_feedback(key="llm_judge", score=grade)

    assert "hello" in response.lower()


@pytest.mark.langsmith
async def test_composite_evaluator():
    # Traced code will be included in the test case
    text = "Say hello!"
    response = await my_app()
    t.log_inputs({"text": text})
    t.log_outputs({"response": response})
    t.log_reference_outputs({"response": "hello!"})

    @traceable
    def my_composite_evaluator(response):
        with t.trace_feedback():
            grade = 1 if "hello" in response else 0
            t.log_feedback(key="composite_judge", score=grade)
            return grade

    my_composite_evaluator(response)

    assert "hello" in response.lower()


@pytest.mark.xfail(reason="Test failure output case")
@pytest.mark.langsmith(output_keys=["expected"])
@pytest.mark.parametrize(
    "a, b, expected",
    [
        (1, 2, 3),
        (3, 4, 7),
    ],
)
async def test_addition_parametrized(a: int, b: int, expected: int):
    t.log_outputs({"sum": a + b})
    assert a + b != expected


@pytest.mark.langsmith
@pytest.mark.parametrize("a,b", [[i, i] for i in range(20)])
def test_param(a, b):
    t.log_outputs({"sum": a + b})
    t.log_reference_outputs({"sum": a + b})
    assert a + b == a + b


@pytest.fixture
def inputs() -> int:
    return 5


@pytest.fixture
def reference_outputs() -> int:
    return 10


@pytest.mark.langsmith(output_keys=["reference_outputs"])
def test_fixture(inputs: int, reference_outputs: int):
    result = 2 * inputs
    t.log_outputs({"d": result})
    assert result == reference_outputs


@pytest.mark.langsmith
def test_slow_test():
    t.log_inputs({"slow": "I am slow"})
    time.sleep(5)
    t.log_outputs({"slow_result": "I am slow"})
    t.log_reference_outputs({"slow_result": "I am not fast"})


@pytest.mark.skipif(
    not importlib.util.find_spec("langchain_core"),
    reason="langchain-core not installed",
)
@pytest.mark.langsmith
def test_log_langchain_outputs() -> None:
    from langchain_core.messages import AIMessage

    t.log_inputs({"question": "foo"})
    t.log_outputs({"answer": AIMessage("bar")})


@pytest.mark.langsmith(
    metadata={"test_type": "metadata_test", "custom_key": "custom_value"}
)
def test_metadata_parameter():
    """Test that metadata parameter is properly passed to the decorator."""
    x = 5
    y = 10
    t.log_inputs({"x": x, "y": y})

    result = x + y
    t.log_outputs({"sum": result})
    t.log_reference_outputs({"sum": 15})

    assert result == 15


@pytest.mark.langsmith(
    metadata={"test_type": "metadata_test_asyncy", "custom_key": "custom_value_async"}
)
async def test_metadata_parameter_async():
    """Test that metadata parameter is properly passed to the decorator."""
    x = 5
    y = 10
    t.log_inputs({"x": x, "y": y})

    result = x + y
    t.log_outputs({"sum": result})
    t.log_reference_outputs({"sum": 15})

    assert result == 15


@pytest.mark.langsmith(repetitions=2)
def test_repetitions_parameter():
    """Test that repetitions parameter causes test to run multiple times."""
    x = 5
    y = 10
    t.log_inputs({"x": x, "y": y})

    result = x + y
    t.log_outputs({"sum": result, "random": random.random()})
    t.log_reference_outputs({"sum": 15})

    assert result == 15


@pytest.mark.langsmith(split="test_split")
def test_split_parameter():
    """Test that split parameter causes test to run multiple times."""
    x = "test_split"
    t.log_inputs({"split": x})

    t.log_outputs({"foo": "foo"})
    t.log_reference_outputs({"foo": "foo"})

    assert x == "test_split"


@pytest.mark.langsmith(repetitions=3)
async def test_repetitions_parameter_async():
    """Test that repetitions parameter causes async test to run multiple times."""
    x = 5
    y = 10
    t.log_inputs({"x": x, "y": y})

    result = x + y
    t.log_outputs({"sum": result, "random": random.random()})
    t.log_reference_outputs({"sum": 15})

    assert result == 15
