# mypy: disable-error-code="attr-defined, union-attr, arg-type, call-overload"
from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from langsmith import Client
from langsmith.wrappers import wrap_gemini
from langsmith.wrappers._gemini import _process_generate_content_response
from tests.unit_tests.test_run_helpers import _get_calls

if TYPE_CHECKING:
    from google import genai

model_name = "gemini-2.0-flash-001"
prompt = "Say 'foo'"


LS_TEST_CLIENT_INFO = {
    "batch_ingest_config": {
        "use_multipart_endpoint": False,
        "scale_up_qsize_trigger": 1000,
        "scale_up_nthreads_limit": 16,
        "scale_down_nempty_trigger": 4,
        "size_limit": 100,
        "size_limit_bytes": 20971520,
    },
}


@pytest.fixture
def original_client() -> genai.Client:
    """Create an original Gemini client."""
    from google import genai

    return genai.Client()


@pytest.fixture
def mock_ls_client() -> Client:
    """Create a mock LangSmith client."""
    mock_session = mock.MagicMock()
    return Client(session=mock_session, info=LS_TEST_CLIENT_INFO)


@pytest.fixture
def patched_client(mock_ls_client: Client) -> genai.Client:
    """Create a patched Gemini client with tracing."""
    from google import genai

    return wrap_gemini(genai.Client(), tracing_extra={"client": mock_ls_client})


def test_generate_content_sync(
    original_client: genai.Client,
    patched_client: genai.Client,
    mock_ls_client: Client,
):
    """Test non-streaming generate_content."""
    original = original_client.models.generate_content(
        model=model_name,
        contents=prompt,
    )
    patched = patched_client.models.generate_content(
        model=model_name,
        contents=prompt,
    )

    # Verify responses are similar
    assert isinstance(patched, type(original))
    assert original.text == patched.text

    # Give the thread a chance to post traces
    time.sleep(0.1)

    # Verify tracing calls were made
    calls = _get_calls(mock_ls_client, minimum=1)
    assert calls
    datas = [json.loads(call.kwargs["data"]) for call in calls]

    # Check that outputs were captured
    outputs = None
    for data in datas:
        if data.get("post"):
            if outputs := data["post"][0].get("outputs"):
                break
        if data.get("patch"):
            outputs = data["patch"][0].get("outputs")
            break
    assert outputs


def test_generate_content_stream_sync(
    original_client: genai.Client,
    patched_client: genai.Client,
    mock_ls_client: Client,
):
    """Test streaming generate_content_stream."""
    original_chunks = []
    for chunk in original_client.models.generate_content_stream(
        model=model_name,
        contents=prompt,
    ):
        if chunk.text:
            original_chunks.append(chunk.text)

    patched_chunks = []
    for chunk in patched_client.models.generate_content_stream(
        model=model_name,
        contents=prompt,
    ):
        if chunk.text:
            patched_chunks.append(chunk.text)

    # Verify responses are similar
    assert len(original_chunks) == len(patched_chunks)
    assert "".join(original_chunks) == "".join(patched_chunks)

    # Give the thread a chance to post traces
    time.sleep(0.1)

    # Verify tracing calls were made
    calls = _get_calls(mock_ls_client, minimum=1)
    assert calls
    datas = [json.loads(call.kwargs["data"]) for call in calls]

    # Check that outputs were captured
    outputs = None
    for data in datas:
        if data.get("post"):
            if outputs := data["post"][0].get("outputs"):
                break
        if data.get("patch"):
            outputs = data["patch"][0].get("outputs")
            break
    assert outputs


@pytest.mark.asyncio
async def test_generate_content_async():
    """Test async generate_content."""
    from google import genai

    mock_session = mock.MagicMock()
    client = Client(session=mock_session)

    # Create async client
    original_client = genai.Client()
    patched_client = wrap_gemini(genai.Client(), tracing_extra={"client": client})

    # Test non-streaming async
    original = await original_client.aio.models.generate_content(
        model=model_name,
        contents=prompt,
    )
    patched = await patched_client.aio.models.generate_content(
        model=model_name,
        contents=prompt,
    )

    # Verify responses are similar
    assert isinstance(patched, type(original))
    assert original.text == patched.text

    # Give the thread a chance to post traces
    time.sleep(0.1)

    # Verify tracing calls were made
    calls = _get_calls(client, minimum=1)
    assert calls


@pytest.mark.asyncio
async def test_generate_content_stream_async():
    """Test async streaming generate_content_stream."""
    from google import genai

    mock_session = mock.MagicMock()
    client = Client(session=mock_session)

    # Create async client
    original_client = genai.Client()
    patched_client = wrap_gemini(genai.Client(), tracing_extra={"client": client})

    # Test streaming async
    original_chunks = []
    async for chunk in await original_client.aio.models.generate_content_stream(
        model=model_name,
        contents=prompt,
    ):
        if chunk.text:
            original_chunks.append(chunk.text)

    patched_chunks = []
    async for chunk in await patched_client.aio.models.generate_content_stream(
        model=model_name,
        contents=prompt,
    ):
        if chunk.text:
            patched_chunks.append(chunk.text)

    # Verify responses are similar
    assert len(original_chunks) == len(patched_chunks)
    assert "".join(original_chunks) == "".join(patched_chunks)

    # Give the thread a chance to post traces
    time.sleep(0.1)

    # Verify tracing calls were made
    calls = _get_calls(client, minimum=1)
    assert calls


def test_custom_config(patched_client: genai.Client, mock_ls_client: Client):
    """Test with custom configuration."""
    from google.genai import types

    config = types.GenerateContentConfig(
        temperature=0.5,
        max_output_tokens=100,
        stop_sequences=["END"],
    )

    response = patched_client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=config,
    )

    assert response.text

    # Give the thread a chance to post traces
    time.sleep(0.1)

    # Verify tracing calls were made
    calls = _get_calls(mock_ls_client, minimum=1)
    assert calls


def test_finish_reason(patched_client: genai.Client, mock_ls_client: Client):
    """Test finish reason."""
    from google.genai.types import FinishReason

    response = patched_client.models.generate_content(
        model=model_name,
        contents=prompt,
    )
    assert response.candidates[0].finish_reason == FinishReason.STOP


def test_multimodal_image_generation(
    patched_client: genai.Client, mock_ls_client: Client
):
    """Test multimodal response with both text and image output."""
    multimodal_prompt = (
        "Create a picture of a nano banana dish in a fancy restaurant "
        "with a Gemini theme"
    )

    response = patched_client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=[multimodal_prompt],
    )

    # Verify response contains expected parts
    assert response.candidates
    assert response.candidates[0].content.parts

    # Check that we got both text and image parts
    has_text = False
    has_image = False

    for part in response.candidates[0].content.parts:
        if part.text is not None:
            has_text = True
        elif part.inline_data is not None:
            has_image = True
            # Verify inline_data has the expected structure
            assert part.inline_data.data
            assert part.inline_data.mime_type

    # For this specific prompt, we expect both text and image
    assert has_text or has_image, "Response should contain text or image"

    # Give the thread a chance to post traces
    time.sleep(0.1)

    # Verify tracing calls were made
    calls = _get_calls(mock_ls_client, minimum=1)
    assert calls

    # Verify that multimodal content was properly traced
    datas = [json.loads(call.kwargs["data"]) for call in calls]
    outputs = None
    for data in datas:
        if data.get("post"):
            if outputs := data["post"][0].get("outputs"):
                break
        if data.get("patch"):
            outputs = data["patch"][0].get("outputs")
            break

    assert outputs
    # Output should have content (our chat-like format)
    assert "content" in outputs or "role" in outputs


def test_multimodal_input_with_text_only(
    patched_client: genai.Client, mock_ls_client: Client
):
    """Test that multimodal input structure (list of contents) works correctly."""
    # Use list format for contents (multimodal structure) but only with text
    multimodal_input = [{"role": "user", "parts": [{"text": "What is AI in 5 words?"}]}]

    response = patched_client.models.generate_content(
        model=model_name,
        contents=multimodal_input,
    )

    assert response.text
    assert len(response.text) > 0

    # Give the thread a chance to post traces
    time.sleep(0.1)

    # Verify tracing calls were made
    calls = _get_calls(mock_ls_client, minimum=1)
    assert calls

    # Verify input was normalized to messages format
    datas = [json.loads(call.kwargs["data"]) for call in calls]
    for data in datas:
        if data.get("post"):
            inputs = data["post"][0].get("inputs")
            if inputs:
                # Our _process_gemini_inputs should convert to messages format
                assert "messages" in inputs
                assert isinstance(inputs["messages"], list)
                assert len(inputs["messages"]) > 0
                assert inputs["messages"][0]["role"] == "user"
                break


def test_function_calling(patched_client: genai.Client, mock_ls_client: Client):
    """Test function calling with manual function declaration."""
    from google.genai import types

    # Manually define the function declaration
    get_weather_func = types.FunctionDeclaration(
        name="get_current_weather",
        description="Get the current weather in a given location",
        parameters={
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state, e.g. San Francisco, CA",
                }
            },
            "required": ["location"],
        },
    )

    response = patched_client.models.generate_content(
        model=model_name,
        contents="What is the weather like in Boston?",
        config=types.GenerateContentConfig(
            tools=[types.Tool(function_declarations=[get_weather_func])],
        ),
    )

    # Test the processing function
    result = _process_generate_content_response(response)

    # Check that function call was made
    assert response.candidates
    assert response.candidates[0].content.parts

    # Verify the function call is present in result
    assert "tool_calls" in result, f"Expected tool_calls, got: {result.keys()}"
    assert len(result["tool_calls"]) >= 1

    tool_call = result["tool_calls"][0]
    assert tool_call["type"] == "function"
    assert tool_call["function"]["name"] == "get_current_weather"
    assert "location" in json.loads(tool_call["function"]["arguments"])
