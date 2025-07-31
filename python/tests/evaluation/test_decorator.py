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
    metadata={"test_type": "metadata_test_async", "custom_key": "custom_value_async"}
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


@pytest.mark.langsmith(cached_hosts=["https://api.openai.com"])
def test_cached_hosts_parameter():
    """Test that cached_hosts parameter is properly passed to the decorator."""
    from unittest.mock import Mock, patch

    import requests

    # Mock response
    mock_response = Mock()
    mock_response.json.return_value = {"choices": [{"message": {"content": "Hello"}}]}
    mock_response.status_code = 200

    with patch("requests.post", return_value=mock_response) as mock_post:
        # Make calls to api.openai.com that should be cached
        response1 = requests.post(
            "https://api.openai.com/v1/chat/completions", json={"test": "data"}
        )
        response2 = requests.post(
            "https://api.openai.com/v1/chat/completions", json={"test": "data"}
        )

        result1 = response1.json()
        result2 = response2.json()

        t.log_inputs({"mock_call_count": mock_post.call_count})
        t.log_outputs({"result1": result1, "result2": result2})
        t.log_reference_outputs({"expected_calls": 1})  # Should be 1 if cached

        # If caching works, mock should only be called once
        t.log_feedback(key="caching_test", score=1 if mock_post.call_count == 1 else 0)

        assert result1 == result2, "Results should be identical"
        assert mock_post.call_count == 1, (
            f"Expected 1 HTTP call due to caching, got {mock_post.call_count}"
        )


@pytest.mark.langsmith(cached_hosts=["api.anthropic.com", "https://api.openai.com"])
async def test_cached_hosts_parameter_async():
    """Test that cached_hosts parameter works with async tests."""
    from unittest.mock import AsyncMock, patch

    import aiohttp

    # Mock async response
    mock_response = AsyncMock()
    mock_response.json.return_value = {"content": [{"text": "Hello async!"}]}
    mock_response.status = 200
    mock_response.__aenter__.return_value = mock_response
    mock_response.__aexit__.return_value = None

    mock_session = AsyncMock()
    mock_session.post.return_value = mock_response

    with patch(
        "aiohttp.ClientSession", return_value=mock_session
    ) as mock_session_class:
        async with aiohttp.ClientSession() as session:
            # Make calls to both hosts that should be cached
            response1 = await session.post(
                "https://api.openai.com/v1/chat/completions", json={"test": "data"}
            )
            response2 = await session.post(
                "https://api.openai.com/v1/chat/completions", json={"test": "data"}
            )
            response3 = await session.post(
                "https://api.anthropic.com/v1/messages", json={"test": "data"}
            )
            response4 = await session.post(
                "https://api.anthropic.com/v1/messages", json={"test": "data"}
            )

            result1 = await response1.json()
            result2 = await response2.json()
            result3 = await response3.json()
            result4 = await response4.json()

            t.log_inputs({"total_mock_calls": mock_session.post.call_count})
            t.log_outputs(
                {
                    "openai_results": [result1, result2],
                    "anthropic_results": [result3, result4],
                }
            )
            t.log_reference_outputs(
                {"expected_calls": 2}
            )  # Should be 2 if both hosts cached (1 each)

            # If caching works, should only have 2 calls total (1 per host)
            t.log_feedback(
                key="async_caching_test",
                score=1 if mock_session.post.call_count == 2 else 0,
            )

            assert result1 == result2, "OpenAI results should be identical"
            assert result3 == result4, "Anthropic results should be identical"
            assert mock_session.post.call_count == 2, (
                f"Expected 2 HTTP calls due to caching, got {mock_session.post.call_count}"
            )
