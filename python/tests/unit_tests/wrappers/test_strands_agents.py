"""Unit tests for Strands Agents integration."""

import json
from unittest.mock import MagicMock, patch

from langsmith.integrations.strands_agents import (
    LangSmithSpanExporter,
    create_langsmith_exporter,
)


class TestLangSmithSpanExporter:
    """Tests for the LangSmithSpanExporter class."""

    def _make_span(
        self,
        name: str = "test_span",
        attributes: dict | None = None,
        events: list | None = None,
    ):
        """Create a mock ReadableSpan for testing."""
        from opentelemetry.sdk.trace import ReadableSpan

        span = MagicMock(spec=ReadableSpan)
        span.name = name
        span.attributes = attributes or {}
        span.events = events or []
        span.context = MagicMock()
        span.parent = None
        span.resource = MagicMock()
        span.links = []
        span.kind = MagicMock()
        span.status = MagicMock()
        span.start_time = 0
        span.end_time = 0
        span.instrumentation_scope = None
        return span

    def _make_event(self, name: str, attributes: dict | None = None):
        """Create a mock span event."""
        event = MagicMock()
        event.name = name
        event.attributes = attributes or {}
        return event

    def test_export_transforms_spans(self):
        """Test that export transforms spans before delegating."""
        delegate = MagicMock()
        delegate.export.return_value = 0  # SpanExportResult.SUCCESS

        exporter = LangSmithSpanExporter(delegate=delegate)

        # Create a span with a user message event
        event = self._make_event(
            "gen_ai.user.message",
            {"content": json.dumps([{"text": "Hello"}])},
        )
        span = self._make_span(
            name="chat",
            attributes={"gen_ai.operation.name": "chat"},
            events=[event],
        )

        result = exporter.export([span])

        assert result == 0
        delegate.export.assert_called_once()
        # Verify the span was transformed
        transformed_spans = delegate.export.call_args[0][0]
        assert len(transformed_spans) == 1

    def test_transform_user_message(self):
        """Test transformation of user message events."""
        delegate = MagicMock()
        delegate.export.return_value = 0

        exporter = LangSmithSpanExporter(delegate=delegate)

        event = self._make_event(
            "gen_ai.user.message",
            {"content": json.dumps([{"text": "Hello, world!"}])},
        )
        span = self._make_span(
            name="chat",
            attributes={"gen_ai.operation.name": "chat"},
            events=[event],
        )

        exporter.export([span])
        transformed = delegate.export.call_args[0][0][0]

        # Check that gen_ai.prompt was created
        assert "gen_ai.prompt" in transformed.attributes
        prompt_data = json.loads(transformed.attributes["gen_ai.prompt"])
        assert "messages" in prompt_data
        assert len(prompt_data["messages"]) == 1
        assert prompt_data["messages"][0]["role"] == "user"

    def test_transform_assistant_message(self):
        """Test transformation of assistant message events."""
        delegate = MagicMock()
        delegate.export.return_value = 0

        exporter = LangSmithSpanExporter(delegate=delegate)

        event = self._make_event(
            "gen_ai.assistant.message",
            {"content": json.dumps([{"text": "Hi there!"}])},
        )
        span = self._make_span(
            name="chat",
            attributes={"gen_ai.operation.name": "chat"},
            events=[event],
        )

        exporter.export([span])
        transformed = delegate.export.call_args[0][0][0]

        prompt_data = json.loads(transformed.attributes["gen_ai.prompt"])
        assert prompt_data["messages"][0]["role"] == "assistant"

    def test_transform_choice_event(self):
        """Test that gen_ai.choice events become completions."""
        delegate = MagicMock()
        delegate.export.return_value = 0

        exporter = LangSmithSpanExporter(delegate=delegate)

        choice_event = self._make_event(
            "gen_ai.choice",
            {"message": json.dumps([{"text": "Final response"}])},
        )
        span = self._make_span(
            name="chat",
            attributes={"gen_ai.operation.name": "chat"},
            events=[choice_event],
        )

        exporter.export([span])
        transformed = delegate.export.call_args[0][0][0]

        # Choice should be in completion, not prompt
        assert "gen_ai.completion" in transformed.attributes
        completion_data = json.loads(transformed.attributes["gen_ai.completion"])
        assert completion_data["role"] == "assistant"

    def test_run_type_mapping_chat(self):
        """Test that chat operations map to llm run type."""
        delegate = MagicMock()
        delegate.export.return_value = 0

        exporter = LangSmithSpanExporter(delegate=delegate)

        span = self._make_span(
            name="chat",
            attributes={"gen_ai.operation.name": "chat"},
            events=[],
        )

        exporter.export([span])
        transformed = delegate.export.call_args[0][0][0]

        assert transformed.attributes["langsmith.span.kind"] == "llm"

    def test_run_type_mapping_invoke_agent(self):
        """Test that invoke_agent operations map to chain run type."""
        delegate = MagicMock()
        delegate.export.return_value = 0

        exporter = LangSmithSpanExporter(delegate=delegate)

        span = self._make_span(
            name="invoke_agent",
            attributes={"gen_ai.operation.name": "invoke_agent"},
            events=[],
        )

        exporter.export([span])
        transformed = delegate.export.call_args[0][0][0]

        assert transformed.attributes["langsmith.span.kind"] == "chain"

    def test_run_type_mapping_execute_tool(self):
        """Test that execute_tool operations map to tool run type."""
        delegate = MagicMock()
        delegate.export.return_value = 0

        exporter = LangSmithSpanExporter(delegate=delegate)

        span = self._make_span(
            name="execute_tool",
            attributes={"gen_ai.operation.name": "execute_tool"},
            events=[],
        )

        exporter.export([span])
        transformed = delegate.export.call_args[0][0][0]

        assert transformed.attributes["langsmith.span.kind"] == "tool"

    def test_convert_content_block_text(self):
        """Test conversion of text content blocks."""
        block = {"text": "Hello"}
        result = LangSmithSpanExporter._convert_content_block(block)

        assert result == {"type": "text", "text": "Hello"}

    def test_convert_content_block_tool_use(self):
        """Test conversion of toolUse content blocks."""
        block = {"toolUse": {"toolUseId": "123", "name": "my_tool", "input": {"x": 1}}}
        result = LangSmithSpanExporter._convert_content_block(block)

        assert result == {
            "type": "tool_use",
            "id": "123",
            "name": "my_tool",
            "input": {"x": 1},
        }

    def test_convert_content_block_tool_result(self):
        """Test conversion of toolResult content blocks."""
        block = {
            "toolResult": {
                "toolUseId": "123",
                "status": "success",
                "content": [{"text": "result"}],
            }
        }
        result = LangSmithSpanExporter._convert_content_block(block)

        assert result["type"] == "tool_result"
        assert result["tool_use_id"] == "123"
        assert result["status"] == "success"
        assert result["content"] == [{"type": "text", "text": "result"}]

    def test_flatten_tool_result_message(self):
        """Test flattening of Bedrock tool result messages."""
        content_blocks = [
            {
                "toolResult": {
                    "toolUseId": "tool-123",
                    "status": "success",
                    "content": [{"text": "Result text"}],
                }
            }
        ]

        result = LangSmithSpanExporter._flatten_tool_result_message(
            content_blocks, tool_id_to_name={"tool-123": "my_tool"}
        )

        assert result["role"] == "tool"
        assert result["name"] == "my_tool"
        assert result["tool_call_id"] == "tool-123"
        assert result["content"] == "Result text"

    def test_shutdown_delegates(self):
        """Test that shutdown is delegated to the underlying exporter."""
        delegate = MagicMock()
        exporter = LangSmithSpanExporter(delegate=delegate)

        exporter.shutdown()

        delegate.shutdown.assert_called_once()

    def test_force_flush_delegates(self):
        """Test that force_flush is delegated to the underlying exporter."""
        delegate = MagicMock()
        delegate.force_flush.return_value = True
        exporter = LangSmithSpanExporter(delegate=delegate)

        result = exporter.force_flush(timeout_millis=5000)

        assert result is True
        delegate.force_flush.assert_called_once_with(5000)


class TestCreateLangsmithExporter:
    """Tests for the create_langsmith_exporter factory function."""

    @patch("langsmith.integrations.strands_agents.exporter.OTLPSpanExporter")
    def test_creates_exporter_with_defaults(self, mock_otlp_cls):
        """Test that exporter is created with default settings."""
        mock_otlp = MagicMock()
        mock_otlp_cls.return_value = mock_otlp

        exporter = create_langsmith_exporter()

        assert isinstance(exporter, LangSmithSpanExporter)
        mock_otlp_cls.assert_called_once()

    @patch("langsmith.integrations.strands_agents.exporter.OTLPSpanExporter")
    def test_forwards_kwargs(self, mock_otlp_cls):
        """Test that kwargs are forwarded to OTLPSpanExporter."""
        mock_otlp = MagicMock()
        mock_otlp_cls.return_value = mock_otlp

        create_langsmith_exporter(
            endpoint="https://custom.endpoint.com",
            headers={"Authorization": "Bearer test"},
        )

        mock_otlp_cls.assert_called_once_with(
            endpoint="https://custom.endpoint.com",
            headers={"Authorization": "Bearer test"},
        )


class TestSetupLangsmithTelemetry:
    """Tests for the setup_langsmith_telemetry function."""

    @patch("langsmith.integrations.strands_agents.exporter.StrandsTelemetry")
    @patch("langsmith.integrations.strands_agents.exporter.BatchSpanProcessor")
    @patch("langsmith.integrations.strands_agents.exporter.create_langsmith_exporter")
    def test_setup_adds_processor(
        self, mock_create_exporter, mock_batch_processor, mock_strands_telemetry
    ):
        """Test that setup adds the batch processor to the tracer provider."""
        from langsmith.integrations.strands_agents import setup_langsmith_telemetry

        mock_exporter = MagicMock()
        mock_create_exporter.return_value = mock_exporter

        mock_processor = MagicMock()
        mock_batch_processor.return_value = mock_processor

        mock_telemetry = MagicMock()
        mock_strands_telemetry.return_value = mock_telemetry

        setup_langsmith_telemetry()

        mock_create_exporter.assert_called_once()
        mock_batch_processor.assert_called_once_with(mock_exporter)
        mock_telemetry.tracer_provider.add_span_processor.assert_called_once_with(
            mock_processor
        )

    @patch("langsmith.integrations.strands_agents.exporter.StrandsTelemetry")
    @patch("langsmith.integrations.strands_agents.exporter.SimpleSpanProcessor")
    @patch("langsmith.integrations.strands_agents.exporter.ConsoleSpanExporter")
    @patch("langsmith.integrations.strands_agents.exporter.BatchSpanProcessor")
    @patch("langsmith.integrations.strands_agents.exporter.create_langsmith_exporter")
    def test_setup_with_console(
        self,
        mock_create_exporter,
        mock_batch_processor,
        mock_console_exporter,
        mock_simple_processor,
        mock_strands_telemetry,
    ):
        """Test that console=True adds a console exporter."""
        from langsmith.integrations.strands_agents import setup_langsmith_telemetry

        mock_telemetry = MagicMock()
        mock_strands_telemetry.return_value = mock_telemetry

        mock_console = MagicMock()
        mock_console_exporter.return_value = mock_console

        mock_simple = MagicMock()
        mock_simple_processor.return_value = mock_simple

        setup_langsmith_telemetry(console=True)

        # Should add both batch and console processors
        assert mock_telemetry.tracer_provider.add_span_processor.call_count == 2

    @patch("langsmith.integrations.strands_agents.exporter.StrandsTelemetry")
    @patch("langsmith.integrations.strands_agents.exporter.BatchSpanProcessor")
    @patch("langsmith.integrations.strands_agents.exporter.create_langsmith_exporter")
    @patch("opentelemetry.trace.get_tracer")
    def test_usage_example_wrapper_span(
        self,
        mock_get_tracer,
        mock_create_exporter,
        mock_batch_processor,
        mock_strands_telemetry,
    ):
        """Test the documented setup and optional wrapper span usage."""
        from opentelemetry import trace

        from langsmith.integrations.strands_agents import setup_langsmith_telemetry

        class Agent:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def __call__(self, prompt):
                self.prompt = prompt
                response = MagicMock()
                response.output = "Looks good."
                return response

        mock_create_exporter.return_value = MagicMock()
        mock_batch_processor.return_value = MagicMock()
        mock_strands_telemetry.return_value = MagicMock()

        span = MagicMock()
        span_context = MagicMock()
        span_context.__enter__.return_value = span
        tracer = MagicMock()
        tracer.start_as_current_span.return_value = span_context
        mock_get_tracer.return_value = tracer

        setup_langsmith_telemetry()

        agent = Agent(
            tools=[],
            system_prompt="You are an Expert Software Developer.",
            model="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
        )

        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("call_strands") as span:
            input_ = "Do a short review of otel_strands_share.py."
            span.set_attribute("gen_ai.prompt.0.content", input_)
            span.set_attribute("gen_ai.prompt.0.role", "user")
            response = agent(input_)
            output_text = getattr(response, "output", str(response))
            span.set_attribute("gen_ai.completion.0.content", output_text)
            span.set_attribute("gen_ai.completion.0.role", "ai")

        mock_strands_telemetry.assert_called_once()
        tracer.start_as_current_span.assert_called_once_with("call_strands")
        assert agent.prompt == "Do a short review of otel_strands_share.py."
        span.set_attribute.assert_any_call("gen_ai.prompt.0.content", agent.prompt)
        span.set_attribute.assert_any_call("gen_ai.prompt.0.role", "user")
        span.set_attribute.assert_any_call("gen_ai.completion.0.content", "Looks good.")
        span.set_attribute.assert_any_call("gen_ai.completion.0.role", "ai")
