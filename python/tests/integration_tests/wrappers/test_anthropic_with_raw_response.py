"""Test with_raw_response functionality for Anthropic wrapper."""

from unittest import mock

import pytest

import langsmith
from langsmith.wrappers import wrap_anthropic


class Collector:
    """Helper to collect run information from callbacks."""

    def __init__(self):
        self.run = None

    def __call__(self, run):
        self.run = run


@pytest.mark.parametrize("stream", [False])
def test_messages_with_raw_response_sync(stream: bool):
    import anthropic

    mock_session = mock.MagicMock()
    ls_client = langsmith.Client(session=mock_session)
    patched_client = wrap_anthropic(
        anthropic.Anthropic(), tracing_extra={"client": ls_client}
    )
    messages = [{"role": "user", "content": "Say 'foo'"}]

    collect = Collector()

    with langsmith.tracing_context(enabled=True):
        raw_response = patched_client.messages.with_raw_response.create(
            messages=messages,
            max_tokens=100,
            temperature=0,
            model="claude-3-5-haiku-20241022",
            langsmith_extra={"on_end": collect},
        )

        # Verify we can access headers
        assert raw_response.headers is not None
        assert (
            "content-type" in raw_response.headers
            or "Content-Type" in raw_response.headers
        )

        # Verify we can parse the response
        message = raw_response.parse()
        assert message.content[0].text.lower().strip(" .") == "foo"

    # Verify the run captured the parsed output, not the raw response wrapper
    assert collect.run is not None
    outputs = collect.run.outputs
    assert "message" in outputs
    assert outputs["message"]["content"][0]["text"].lower().strip(" .") == "foo"


@pytest.mark.parametrize("stream", [False])
async def test_messages_with_raw_response_async(stream: bool):
    import anthropic

    mock_session = mock.MagicMock()
    ls_client = langsmith.Client(session=mock_session)
    patched_client = wrap_anthropic(
        anthropic.AsyncAnthropic(), tracing_extra={"client": ls_client}
    )
    messages = [{"role": "user", "content": "Say 'foo'"}]

    collect = Collector()

    with langsmith.tracing_context(enabled=True):
        raw_response = await patched_client.messages.with_raw_response.create(
            messages=messages,
            max_tokens=100,
            temperature=0,
            model="claude-3-5-haiku-20241022",
            langsmith_extra={"on_end": collect},
        )

        # Verify we can access headers
        assert raw_response.headers is not None
        assert (
            "content-type" in raw_response.headers
            or "Content-Type" in raw_response.headers
        )

        # Verify we can parse the response
        message = raw_response.parse()
        assert message.content[0].text.lower().strip(" .") == "foo"

    # Verify the run captured the parsed output, not the raw response wrapper
    assert collect.run is not None
    outputs = collect.run.outputs
    assert "message" in outputs
    assert outputs["message"]["content"][0]["text"].lower().strip(" .") == "foo"
