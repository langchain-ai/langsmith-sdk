"""Unit tests for Gemini wrapper processing functions."""

from langsmith.wrappers._gemini import (
    _create_usage_metadata,
    _infer_invocation_params,
    _process_gemini_inputs,
    _process_generate_content_response,
    _reduce_generate_content_chunks,
    _strip_none,
)


class TestStripNone:
    """Test _strip_none utility function."""

    def test_removes_none_values(self):
        input_dict = {"a": 1, "b": None, "c": "test", "d": None}
        result = _strip_none(input_dict)
        assert result == {"a": 1, "c": "test"}

    def test_empty_dict(self):
        result = _strip_none({})
        assert result == {}

    def test_no_none_values(self):
        input_dict = {"a": 1, "b": "test", "c": [1, 2, 3]}
        result = _strip_none(input_dict)
        assert result == input_dict


class TestProcessGeminiInputs:
    """Test _process_gemini_inputs function."""

    def test_string_input(self):
        inputs = {"contents": "Hello world", "model": "gemini-pro"}
        result = _process_gemini_inputs(inputs)

        expected = {
            "messages": [{"role": "user", "content": "Hello world"}],
            "model": "gemini-pro",
        }
        assert result == expected

    def test_list_input(self):
        inputs = {"contents": ["one", "two"], "model": "gemini-pro"}
        result = _process_gemini_inputs(inputs)

        expected = {
            "messages": [
                {"role": "user", "content": "one"},
                {"role": "user", "content": "two"},
            ],
            "model": "gemini-pro",
        }
        assert result == expected

    def test_empty_contents(self):
        inputs = {"model": "gemini-pro"}
        result = _process_gemini_inputs(inputs)
        assert result == inputs

    def test_none_contents(self):
        inputs = {"contents": None, "model": "gemini-pro"}
        result = _process_gemini_inputs(inputs)
        assert result == inputs

    def test_multimodal_text_only(self):
        inputs = {
            "contents": [{"role": "user", "parts": [{"text": "What is AI?"}]}],
            "model": "gemini-pro",
        }
        result = _process_gemini_inputs(inputs)

        expected = {
            "messages": [{"role": "user", "content": "What is AI?"}],
            "model": "gemini-pro",
        }
        assert result == expected

    def test_multimodal_list_of_texts(self):
        inputs = {
            "contents": [
                {"role": "user", "parts": [{"text": "What is AI?"}]},
                {"role": "user", "parts": [{"text": "What is computer?"}]},
            ],
            "model": "gemini-pro",
        }
        result = _process_gemini_inputs(inputs)
        expected = {
            "messages": [
                {"role": "user", "content": "What is AI?"},
                {"role": "user", "content": "What is computer?"},
            ],
            "model": "gemini-pro",
        }
        assert result == expected

    def test_multimodal_with_image(self):
        inputs = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": "Describe this image"},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": "base64data",
                            }
                        },
                    ],
                }
            ],
            "model": "gemini-pro",
        }
        result = _process_gemini_inputs(inputs)

        assert result["model"] == "gemini-pro"
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "user"

        # Content should be a list with text and image
        content = result["messages"][0]["content"]
        assert isinstance(content, list)
        assert len(content) == 2
        assert content[0]["type"] == "text"
        assert content[0]["text"] == "Describe this image"
        assert content[1]["type"] == "image_url"
        assert "data:image/jpeg;base64,base64data" in content[1]["image_url"]["url"]

    def test_string_parts(self):
        inputs = {
            "contents": [{"role": "user", "parts": ["Hello", "world"]}],
            "model": "gemini-pro",
        }
        result = _process_gemini_inputs(inputs)

        expected = {
            "messages": [{"role": "user", "content": "Hello\nworld"}],
            "model": "gemini-pro",
        }
        assert result == expected

    def test_function_call_input_passthrough(self):
        # Function calls in input can occur when including conversation history
        # The normal flow is: user input → model function call → user function response
        inputs = {
            "contents": [
                {
                    "role": "model",
                    "parts": [
                        {
                            "functionCall": {
                                "name": "get_weather",
                                "args": {"location": "Boston"},
                            }
                        }
                    ],
                }
            ],
            "model": "gemini-pro",
        }
        result = _process_gemini_inputs(inputs)

        # Should convert to structured format with function_call
        expected = {
            "messages": [
                {
                    "role": "model",
                    "content": [
                        {
                            "type": "function_call",
                            "function_call": {
                                "id": None,
                                "name": "get_weather",
                                "arguments": {"location": "Boston"},
                            },
                        }
                    ],
                }
            ],
            "model": "gemini-pro",
        }
        assert result == expected

    def test_function_response_input(self):
        inputs = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "functionResponse": {
                                "name": "get_weather",
                                "response": {
                                    "temperature": "72°F",
                                    "condition": "sunny",
                                },
                            }
                        }
                    ],
                }
            ],
            "model": "gemini-pro",
        }
        result = _process_gemini_inputs(inputs)

        expected = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "function_response",
                            "function_response": {
                                "name": "get_weather",
                                "response": {
                                    "temperature": "72°F",
                                    "condition": "sunny",
                                },
                            },
                        }
                    ],
                }
            ],
            "model": "gemini-pro",
        }
        assert result == expected


class TestProcessGenerateContentResponse:
    """Test _process_generate_content_response function."""

    def test_basic_response(self):
        # Mock response with to_dict method
        class MockResponse:
            def to_dict(self):
                return {
                    "candidates": [
                        {
                            "content": {"parts": [{"text": "Hello world"}]},
                            "finish_reason": "STOP",
                        }
                    ],
                    "usage_metadata": {
                        "prompt_token_count": 5,
                        "candidates_token_count": 10,
                    },
                }

        result = _process_generate_content_response(MockResponse())
        # For simple text responses, should return minimal structure
        assert result["content"] == "Hello world"
        assert result["finish_reason"] == "STOP"
        # usage_metadata is in both run.extra AND result
        assert "usage_metadata" in result
        assert result["usage_metadata"]["input_tokens"] == 5

    def test_text_attribute_fallback(self):
        # Mock response with direct text attribute
        class MockResponse:
            text = "Direct text response"

        result = _process_generate_content_response(MockResponse())

        # For simple text responses, should return minimal structure
        assert result["content"] == "Direct text response"
        # usage_metadata is in both run.extra AND result
        assert "usage_metadata" in result

    def test_exception_handling(self):
        # Mock response that raises exception
        class MockResponse:
            def to_dict(self):
                raise ValueError("Test error")

            def __str__(self):
                return "String representation"

        result = _process_generate_content_response(MockResponse())

        # Should fallback to generic output format
        assert "output" in result

    def test_response_with_function_call(self):
        # Mock response with function call
        class MockResponse:
            def to_dict(self):
                return {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "functionCall": {
                                            "name": "get_weather",
                                            "args": {"location": "Boston"},
                                        }
                                    }
                                ]
                            }
                        }
                    ],
                    "usage_metadata": {
                        "prompt_token_count": 10,
                        "candidates_token_count": 5,
                    },
                }

        result = _process_generate_content_response(MockResponse())

        # Should now use OpenAI-compatible tool_calls format
        assert result["content"] is None
        assert result["role"] == "assistant"
        assert "tool_calls" in result
        assert len(result["tool_calls"]) == 1

        tool_call = result["tool_calls"][0]
        assert tool_call["type"] == "function"
        assert tool_call["index"] == 0
        assert tool_call["function"]["name"] == "get_weather"
        assert tool_call["function"]["arguments"] == '{"location": "Boston"}'
        assert result["role"] == "assistant"
        # usage_metadata is in both run.extra AND result
        assert "usage_metadata" in result

    def test_response_with_text_and_function_call(self):
        # Mock response with both text and function call
        class MockResponse:
            def to_dict(self):
                return {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {"text": "I'll help you with that."},
                                    {
                                        "functionCall": {
                                            "name": "get_weather",
                                            "args": {"location": "Boston"},
                                        }
                                    },
                                ]
                            }
                        }
                    ],
                    "usage_metadata": {
                        "prompt_token_count": 15,
                        "candidates_token_count": 20,
                    },
                }

        result = _process_generate_content_response(MockResponse())

        # Should use tool_calls format when function calls are present
        assert result["content"] == "I'll help you with that."
        assert result["role"] == "assistant"
        assert "tool_calls" in result
        assert len(result["tool_calls"]) == 1

        tool_call = result["tool_calls"][0]
        assert tool_call["type"] == "function"
        assert tool_call["index"] == 0
        assert tool_call["function"]["name"] == "get_weather"
        assert tool_call["function"]["arguments"] == '{"location": "Boston"}'
        # usage_metadata is in both run.extra AND result
        assert "usage_metadata" in result

    def test_response_with_image(self):
        # Mock response with inline image data (bytes format like real Gemini API)
        import base64

        # Valid 1x1 red pixel PNG in base64
        test_b64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwA"
            "FBQIAX8jx0gAAAABJRU5ErkJggg=="
        )
        test_image_bytes = base64.b64decode(test_b64)

        class MockResponse:
            def to_dict(self):
                return {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {"text": "Here's your image:"},
                                    {
                                        "inline_data": {
                                            "mime_type": "image/png",
                                            "data": test_image_bytes,
                                        }
                                    },
                                ]
                            }
                        }
                    ],
                    "usage_metadata": {
                        "prompt_token_count": 10,
                        "candidates_token_count": 5,
                    },
                }

        result = _process_generate_content_response(MockResponse())

        # Should use structured content format for mixed content
        assert result["content"] == [
            {"type": "text", "text": "Here's your image:"},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{test_b64}",
                    "detail": "high",
                },
            },
        ]
        assert result["role"] == "assistant"
        # usage_metadata is in both run.extra AND result
        assert "usage_metadata" in result


class TestReduceGenerateContentChunks:
    """Test _reduce_generate_content_chunks function."""

    def test_empty_chunks(self):
        result = _reduce_generate_content_chunks([])
        # Empty content should return minimal structure
        assert result["content"] == ""
        # usage_metadata is in both run.extra AND result
        assert "usage_metadata" in result

    def test_text_chunks(self):
        # Mock chunks
        class MockChunk:
            def __init__(self, text):
                self.text = text

        chunks = [MockChunk("Hello "), MockChunk("world"), MockChunk("!")]
        result = _reduce_generate_content_chunks(chunks)

        # Should return minimal structure with content
        assert result["content"] == "Hello world!"
        # usage_metadata is in both run.extra AND result
        assert "usage_metadata" in result

    def test_chunks_with_usage(self):
        class MockUsageMetadata:
            def to_dict(self):
                return {"prompt_token_count": 5, "candidates_token_count": 10}

        class MockChunk:
            def __init__(self, text, usage=None):
                self.text = text
                self.usage_metadata = usage

        chunks = [MockChunk("Hello"), MockChunk(" world", MockUsageMetadata())]
        result = _reduce_generate_content_chunks(chunks)

        # Should return minimal structure with content and usage metadata
        assert result["content"] == "Hello world"
        # usage_metadata is in both run.extra AND result
        assert "usage_metadata" in result
        assert result["usage_metadata"]["input_tokens"] == 5

    def test_chunks_with_errors(self):
        class MockChunk:
            @property
            def text(self):
                raise ValueError("Error accessing text")

        chunks = [MockChunk()]
        result = _reduce_generate_content_chunks(chunks)

        # Should handle errors gracefully and return empty content
        assert result["content"] == ""
        # usage_metadata is in both run.extra AND result
        assert "usage_metadata" in result


class TestInferInvocationParams:
    """Test _infer_invocation_params function."""

    def test_dict_config(self):
        kwargs = {
            "model": "gemini-pro",
            "config": {
                "temperature": 0.7,
                "max_output_tokens": 1000,
                "stop_sequences": ["END"],
            },
        }
        result = _infer_invocation_params(kwargs)

        expected = {
            "ls_provider": "google",
            "ls_model_type": "chat",
            "ls_model_name": "gemini-pro",
            "ls_temperature": 0.7,
            "ls_max_tokens": 1000,
            "ls_stop": ["END"],
        }
        assert result == expected

    def test_object_config(self):
        # Mock config object
        class MockConfig:
            temperature = 0.5
            max_output_tokens = 2000
            stop_sequences = None

        kwargs = {"model": "gemini-flash", "config": MockConfig()}
        result = _infer_invocation_params(kwargs)

        expected = {
            "ls_provider": "google",
            "ls_model_type": "chat",
            "ls_model_name": "gemini-flash",
            "ls_temperature": 0.5,
            "ls_max_tokens": 2000,
            "ls_stop": None,
        }
        assert result == expected

    def test_empty_config(self):
        kwargs = {"model": "gemini-pro"}
        result = _infer_invocation_params(kwargs)

        expected = {
            "ls_provider": "google",
            "ls_model_type": "chat",
            "ls_model_name": "gemini-pro",
            "ls_temperature": None,
            "ls_max_tokens": None,
            "ls_stop": None,
        }
        assert result == expected


class TestCreateUsageMetadata:
    """Test _create_usage_metadata function."""

    def test_basic_usage(self):
        gemini_usage = {
            "prompt_token_count": 10,
            "candidates_token_count": 20,
            "total_token_count": 30,
        }
        result = _create_usage_metadata(gemini_usage)

        assert result["input_tokens"] == 10
        assert result["output_tokens"] == 20
        assert result["total_tokens"] == 30

    def test_with_cached_tokens(self):
        gemini_usage = {
            "prompt_token_count": 10,
            "candidates_token_count": 20,
            "cached_content_token_count": 5,
            "total_token_count": 30,
        }
        result = _create_usage_metadata(gemini_usage)

        assert result["input_tokens"] == 10
        assert result["output_tokens"] == 20
        assert result["total_tokens"] == 30
        assert result["input_token_details"]["cache_read"] == 5

    def test_with_reasoning_tokens(self):
        gemini_usage = {
            "prompt_token_count": 10,
            "candidates_token_count": 20,
            "thoughts_token_count": 15,
            "total_token_count": 30,
        }
        result = _create_usage_metadata(gemini_usage)

        assert result["input_tokens"] == 10
        assert result["output_tokens"] == 20
        assert result["total_tokens"] == 30
        assert result["output_token_details"]["reasoning"] == 15

    def test_missing_totals(self):
        gemini_usage = {
            "prompt_token_count": 10,
            "candidates_token_count": 20,
        }
        result = _create_usage_metadata(gemini_usage)

        # Should calculate total if missing
        assert result["total_tokens"] == 30
