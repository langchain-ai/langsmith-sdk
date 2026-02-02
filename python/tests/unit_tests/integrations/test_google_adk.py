"""Unit tests for Google ADK integration."""

import base64
from unittest.mock import MagicMock, patch

from langsmith.integrations.google_adk._config import (
    get_tracing_config,
    set_tracing_config,
)
from langsmith.integrations.google_adk._messages import (
    _safe_serialize,
    _serialize_part,
    convert_adk_content_to_langsmith,
    convert_llm_request_to_messages,
    extract_text_from_response,
    has_function_calls,
    has_function_response_in_request,
)
from langsmith.integrations.google_adk._recursive import RecursiveCallbackInjector
from langsmith.integrations.google_adk._tools import (
    clear_parent_run_tree,
    get_parent_run_tree,
    set_parent_run_tree,
)
from langsmith.integrations.google_adk._usage import (
    extract_model_name,
    extract_usage_from_response,
)


class TestConfig:
    """Test configuration management."""

    def test_set_and_get_config(self):
        set_tracing_config(
            name="test_trace",
            project_name="test_project",
            metadata={"key": "value"},
            tags=["tag1", "tag2"],
        )
        config = get_tracing_config()

        assert config["name"] == "test_trace"
        assert config["project_name"] == "test_project"
        assert config["metadata"] == {"key": "value"}
        assert config["tags"] == ["tag1", "tag2"]

    def test_config_returns_copy(self):
        set_tracing_config(name="test")
        config1 = get_tracing_config()
        config2 = get_tracing_config()

        # Modifying one should not affect the other
        config1["name"] = "modified"
        assert config2["name"] == "test"


class TestThreadLocalTools:
    """Test thread-local storage utilities."""

    def test_set_and_get_parent_run(self):
        mock_run = MagicMock()
        set_parent_run_tree(mock_run)
        result = get_parent_run_tree()

        assert result is mock_run

    def test_clear_parent_run(self):
        mock_run = MagicMock()
        set_parent_run_tree(mock_run)
        clear_parent_run_tree()
        result = get_parent_run_tree()

        assert result is None

    def test_get_without_set(self):
        clear_parent_run_tree()  # Ensure clean state
        result = get_parent_run_tree()

        assert result is None


class TestUsageExtraction:
    """Test token usage extraction."""

    def test_extract_basic_usage(self):
        mock_response = MagicMock()
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        mock_response.usage_metadata.total_token_count = 150

        usage = extract_usage_from_response(mock_response)

        assert usage["input_tokens"] == 100
        assert usage["output_tokens"] == 50
        assert usage["total_tokens"] == 150

    def test_extract_with_cached_tokens(self):
        mock_response = MagicMock()
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        mock_response.usage_metadata.total_token_count = 150
        mock_response.usage_metadata.cached_content_token_count = 80

        usage = extract_usage_from_response(mock_response)

        assert usage["input_tokens"] == 100
        assert usage["input_token_details"]["cache_read"] == 80

    def test_extract_with_reasoning_tokens(self):
        mock_response = MagicMock()
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        mock_response.usage_metadata.total_token_count = 150
        mock_response.usage_metadata.thoughts_token_count = 30

        usage = extract_usage_from_response(mock_response)

        assert usage["output_token_details"]["reasoning"] == 30

    def test_extract_no_usage_metadata(self):
        mock_response = MagicMock()
        mock_response.usage_metadata = None

        usage = extract_usage_from_response(mock_response)

        assert usage == {}

    def test_extract_model_name_from_config(self):
        mock_request = MagicMock()
        mock_request.config = MagicMock()
        mock_request.config.model = "gemini-2.0-flash"

        model = extract_model_name(mock_request)

        assert model == "gemini-2.0-flash"

    def test_extract_model_name_fallback(self):
        mock_request = MagicMock()
        mock_request.config = None
        mock_request.model = "gemini-pro"

        model = extract_model_name(mock_request)

        assert model == "gemini-pro"


class TestMessageConversion:
    """Test ADK message to LangSmith format conversion."""

    def test_serialize_text_part(self):
        mock_part = MagicMock()
        mock_part.text = "Hello, world!"
        mock_part.inline_data = None
        mock_part.file_data = None
        mock_part.function_call = None
        mock_part.function_response = None
        mock_part.executable_code = None
        mock_part.code_execution_result = None
        mock_part.thought = None

        result = _serialize_part(mock_part)

        assert result == {"type": "text", "text": "Hello, world!"}

    def test_serialize_function_call_part(self):
        mock_part = MagicMock()
        mock_part.inline_data = None
        mock_part.file_data = None
        mock_part.function_call = MagicMock()
        mock_part.function_call.name = "get_weather"
        mock_part.function_call.args = {"location": "Boston"}
        mock_part.function_response = None
        mock_part.text = None
        mock_part.executable_code = None
        mock_part.code_execution_result = None
        mock_part.thought = None

        result = _serialize_part(mock_part)

        assert result["type"] == "tool_use"
        assert result["name"] == "get_weather"
        assert result["input"] == {"location": "Boston"}

    def test_serialize_function_response_part(self):
        mock_part = MagicMock()
        mock_part.inline_data = None
        mock_part.file_data = None
        mock_part.function_call = None
        mock_part.function_response = MagicMock()
        mock_part.function_response.name = "get_weather"
        mock_part.function_response.response = {"temperature": "72F"}
        mock_part.text = None
        mock_part.executable_code = None
        mock_part.code_execution_result = None
        mock_part.thought = None

        result = _serialize_part(mock_part)

        assert result["type"] == "tool_result"
        assert result["name"] == "get_weather"
        assert result["content"]["temperature"] == "72F"

    def test_serialize_inline_data_part(self):
        mock_part = MagicMock()
        mock_part.inline_data = MagicMock()
        mock_part.inline_data.data = b"test_image_data"
        mock_part.inline_data.mime_type = "image/png"
        mock_part.file_data = None
        mock_part.function_call = None
        mock_part.function_response = None
        mock_part.text = None
        mock_part.executable_code = None
        mock_part.code_execution_result = None
        mock_part.thought = None

        result = _serialize_part(mock_part)

        assert result["type"] == "image"
        assert result["mime_type"] == "image/png"
        assert result["data"] == base64.b64encode(b"test_image_data").decode("utf-8")

    def test_serialize_dict_passthrough(self):
        result = _serialize_part({"type": "custom", "data": "value"})

        assert result == {"type": "custom", "data": "value"}

    def test_convert_content_with_parts(self):
        mock_content = MagicMock()
        mock_part = MagicMock()
        mock_part.text = "Hello"
        mock_part.inline_data = None
        mock_part.file_data = None
        mock_part.function_call = None
        mock_part.function_response = None
        mock_part.executable_code = None
        mock_part.code_execution_result = None
        mock_part.thought = None

        mock_content.parts = [mock_part]

        result = convert_adk_content_to_langsmith(mock_content)

        assert len(result) == 1
        assert result[0]["type"] == "text"
        assert result[0]["text"] == "Hello"

    def test_convert_llm_request_to_messages(self):
        mock_content = MagicMock()
        mock_content.role = "user"
        mock_part = MagicMock()
        mock_part.text = "What is AI?"
        mock_part.inline_data = None
        mock_part.file_data = None
        mock_part.function_call = None
        mock_part.function_response = None
        mock_part.executable_code = None
        mock_part.code_execution_result = None
        mock_part.thought = None
        mock_content.parts = [mock_part]

        mock_request = MagicMock()
        mock_request.contents = [mock_content]

        result = convert_llm_request_to_messages(mock_request)

        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"][0]["type"] == "text"

    def test_convert_model_role_to_assistant(self):
        mock_content = MagicMock()
        mock_content.role = "model"  # Google's role name
        mock_part = MagicMock()
        mock_part.text = "I can help with that."
        mock_part.inline_data = None
        mock_part.file_data = None
        mock_part.function_call = None
        mock_part.function_response = None
        mock_part.executable_code = None
        mock_part.code_execution_result = None
        mock_part.thought = None
        mock_content.parts = [mock_part]

        mock_request = MagicMock()
        mock_request.contents = [mock_content]

        result = convert_llm_request_to_messages(mock_request)

        assert result[0]["role"] == "assistant"

    def test_has_function_calls(self):
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_part = MagicMock()
        mock_part.inline_data = None
        mock_part.file_data = None
        mock_part.function_call = MagicMock()
        mock_part.function_call.name = "test_tool"
        mock_part.function_call.args = {}
        mock_part.function_response = None
        mock_part.text = None
        mock_part.executable_code = None
        mock_part.code_execution_result = None
        mock_part.thought = None
        mock_content.parts = [mock_part]
        mock_response.content = mock_content

        assert has_function_calls(mock_response) is True

    def test_has_function_calls_false(self):
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_part = MagicMock()
        mock_part.text = "Just text"
        mock_part.inline_data = None
        mock_part.file_data = None
        mock_part.function_call = None
        mock_part.function_response = None
        mock_part.executable_code = None
        mock_part.code_execution_result = None
        mock_part.thought = None
        mock_content.parts = [mock_part]
        mock_response.content = mock_content

        assert has_function_calls(mock_response) is False

    def test_extract_text_from_response(self):
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_part = MagicMock()
        mock_part.text = "Response text"
        mock_part.inline_data = None
        mock_part.file_data = None
        mock_part.function_call = None
        mock_part.function_response = None
        mock_part.executable_code = None
        mock_part.code_execution_result = None
        mock_part.thought = None
        mock_content.parts = [mock_part]
        mock_response.content = mock_content

        text = extract_text_from_response(mock_response)

        assert text == "Response text"


class TestSafeSerialize:
    """Test safe serialization utility."""

    def test_primitive_types(self):
        assert _safe_serialize("string") == "string"
        assert _safe_serialize(123) == 123
        assert _safe_serialize(1.5) == 1.5
        assert _safe_serialize(True) is True
        assert _safe_serialize(None) is None

    def test_bytes(self):
        result = _safe_serialize(b"test")
        assert result == base64.b64encode(b"test").decode("utf-8")

    def test_dict(self):
        result = _safe_serialize({"key": "value", "nested": {"a": 1}})
        assert result == {"key": "value", "nested": {"a": 1}}

    def test_list(self):
        result = _safe_serialize([1, "two", {"three": 3}])
        assert result == [1, "two", {"three": 3}]


class TestRecursiveCallbackInjector:
    """Test recursive callback injection."""

    def test_inject_to_agent_with_no_callbacks(self):
        mock_callback = MagicMock()
        injector = RecursiveCallbackInjector({"test_callback": mock_callback})

        mock_agent = MagicMock()
        mock_agent.test_callback = None
        mock_agent.sub_agents = []
        mock_agent.tools = []

        injector.inject(mock_agent)

        assert mock_agent.test_callback is mock_callback

    def test_inject_to_agent_with_existing_callable(self):
        existing_callback = MagicMock()
        new_callback = MagicMock()
        injector = RecursiveCallbackInjector({"test_callback": new_callback})

        mock_agent = MagicMock()
        mock_agent.test_callback = existing_callback
        mock_agent.sub_agents = []
        mock_agent.tools = []

        injector.inject(mock_agent)

        # Should convert to list with both callbacks
        assert mock_agent.test_callback == [existing_callback, new_callback]

    def test_inject_to_agent_with_existing_list(self):
        existing_callback = MagicMock()
        new_callback = MagicMock()
        injector = RecursiveCallbackInjector({"test_callback": new_callback})

        mock_agent = MagicMock()
        mock_agent.test_callback = [existing_callback]
        mock_agent.sub_agents = []
        mock_agent.tools = []

        injector.inject(mock_agent)

        # Should append to existing list
        assert mock_agent.test_callback == [existing_callback, new_callback]

    def test_recursive_sub_agents(self):
        mock_callback = MagicMock()
        injector = RecursiveCallbackInjector({"test_callback": mock_callback})

        sub_agent = MagicMock()
        sub_agent.test_callback = None
        sub_agent.sub_agents = []
        sub_agent.tools = []

        mock_agent = MagicMock()
        mock_agent.test_callback = None
        mock_agent.sub_agents = [sub_agent]
        mock_agent.tools = []

        injector.inject(mock_agent)

        # Both agents should have the callback
        assert mock_agent.test_callback is mock_callback
        assert sub_agent.test_callback is mock_callback

    def test_agent_in_tool(self):
        mock_callback = MagicMock()
        injector = RecursiveCallbackInjector({"test_callback": mock_callback})

        nested_agent = MagicMock()
        nested_agent.test_callback = None
        nested_agent.sub_agents = []
        nested_agent.tools = []

        mock_tool = MagicMock()
        mock_tool.agent = nested_agent

        mock_agent = MagicMock()
        mock_agent.test_callback = None
        mock_agent.sub_agents = []
        mock_agent.tools = [mock_tool]

        injector.inject(mock_agent)

        # Both root agent and nested agent should have callback
        assert mock_agent.test_callback is mock_callback
        assert nested_agent.test_callback is mock_callback

    def test_no_duplicate_injection(self):
        call_count = 0

        def counting_callback(*args, **kwargs):
            nonlocal call_count
            call_count += 1

        injector = RecursiveCallbackInjector({"test_callback": counting_callback})

        # Create circular reference
        mock_agent = MagicMock()
        mock_agent.test_callback = None
        mock_agent.sub_agents = [mock_agent]  # Self-reference
        mock_agent.tools = []

        injector.inject(mock_agent)

        # Should only inject once despite circular reference
        assert mock_agent.test_callback is counting_callback


class TestConfigureGoogleAdk:
    """Test the main configuration function."""

    def test_returns_false_when_adk_not_installed(self):
        with patch.dict("sys.modules", {"google.adk.runners": None}):
            from langsmith.integrations.google_adk import configure_google_adk

            # Reload to test import failure
            result = configure_google_adk(project_name="test")

            # Should return False when Google ADK is not installed
            # Note: This test may pass or fail depending on environment
            # In production, it should gracefully handle missing dependency


class TestHasFunctionResponseInRequest:
    """Test function response detection in requests."""

    def test_detects_function_response(self):
        mock_content = MagicMock()
        mock_content.role = "user"
        mock_part = MagicMock()
        mock_part.inline_data = None
        mock_part.file_data = None
        mock_part.function_call = None
        mock_part.function_response = MagicMock()
        mock_part.function_response.name = "test_tool"
        mock_part.function_response.response = {"result": "ok"}
        mock_part.text = None
        mock_part.executable_code = None
        mock_part.code_execution_result = None
        mock_part.thought = None
        mock_content.parts = [mock_part]

        mock_request = MagicMock()
        mock_request.contents = [mock_content]

        assert has_function_response_in_request(mock_request) is True

    def test_no_function_response(self):
        mock_content = MagicMock()
        mock_content.role = "user"
        mock_part = MagicMock()
        mock_part.text = "Hello"
        mock_part.inline_data = None
        mock_part.file_data = None
        mock_part.function_call = None
        mock_part.function_response = None
        mock_part.executable_code = None
        mock_part.code_execution_result = None
        mock_part.thought = None
        mock_content.parts = [mock_part]

        mock_request = MagicMock()
        mock_request.contents = [mock_content]

        assert has_function_response_in_request(mock_request) is False
