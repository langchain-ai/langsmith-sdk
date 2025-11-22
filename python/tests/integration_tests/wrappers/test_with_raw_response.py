# Test for with_raw_response support
import time
from unittest import mock

import pytest

import langsmith
from langsmith.wrappers import wrap_openai


def test_chat_with_raw_response_sync():
    """Test that with_raw_response returns proper parsed data in traces."""
    import openai

    mock_session = mock.MagicMock()
    ls_client = langsmith.Client(session=mock_session)
    patched_client = wrap_openai(openai.Client(), tracing_extra={"client": ls_client})

    messages = [{"role": "user", "content": "Say 'foo'"}]

    class Collector:
        def __init__(self):
            self.run = None

        def __call__(self, run):
            self.run = run

    collect = Collector()

    with langsmith.tracing_context(enabled=True):
        # Test with_raw_response
        raw_response = patched_client.chat.completions.with_raw_response.create(
            messages=messages,
            temperature=0,
            seed=42,
            model="gpt-4o",
            langsmith_extra={"on_end": collect},
        )

        # Verify we can access headers
        assert raw_response.headers is not None
        assert (
            "content-type" in raw_response.headers
            or "Content-Type" in raw_response.headers
        )

        # Verify we can parse the response
        parsed = raw_response.parse()
        assert parsed.choices[0].message.content

    # Give background thread a chance
    time.sleep(0.1)

    # Verify the trace has proper parsed output, not stringified APIResponse
    assert collect.run is not None
    outputs = collect.run.outputs
    assert "output" not in outputs or not str(outputs.get("output", "")).startswith(
        "<APIResponse"
    )
    # Should have proper chat completion structure
    assert "choices" in outputs
    assert isinstance(outputs["choices"], list)
    assert len(outputs["choices"]) > 0


@pytest.mark.asyncio
async def test_chat_with_raw_response_async():
    """Test that with_raw_response returns proper parsed data in traces (async)."""
    import openai

    mock_session = mock.MagicMock()
    ls_client = langsmith.Client(session=mock_session)
    patched_client = wrap_openai(
        openai.AsyncClient(), tracing_extra={"client": ls_client}
    )

    messages = [{"role": "user", "content": "Say 'foo'"}]

    class Collector:
        def __init__(self):
            self.run = None

        def __call__(self, run):
            self.run = run

    collect = Collector()

    with langsmith.tracing_context(enabled=True):
        # Test with_raw_response
        raw_response = await patched_client.chat.completions.with_raw_response.create(
            messages=messages,
            temperature=0,
            seed=42,
            model="gpt-4o",
            langsmith_extra={"on_end": collect},
        )

        # Verify we can access headers
        assert raw_response.headers is not None
        assert (
            "content-type" in raw_response.headers
            or "Content-Type" in raw_response.headers
        )

        # Verify we can parse the response
        parsed = raw_response.parse()
        assert parsed.choices[0].message.content

    # Give background thread a chance
    time.sleep(0.1)

    # Verify the trace has proper parsed output, not stringified APIResponse
    assert collect.run is not None
    outputs = collect.run.outputs
    assert "output" not in outputs or not str(outputs.get("output", "")).startswith(
        "<APIResponse"
    )
    # Should have proper chat completion structure
    assert "choices" in outputs
    assert isinstance(outputs["choices"], list)
    assert len(outputs["choices"]) > 0
