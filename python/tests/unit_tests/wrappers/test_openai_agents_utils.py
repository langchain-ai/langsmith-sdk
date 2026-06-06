"""Unit tests for OpenAI Agents SDK ls_invocation_params support."""

import sys
import types
from unittest.mock import MagicMock, patch


def _make_agents_mock():
    """Create a minimal mock of the agents.tracing module."""
    tracing_mod = types.ModuleType("agents.tracing")

    class TracingProcessor:
        pass

    class Trace:
        pass

    class Span:
        pass

    class ResponseSpanData:
        type = "response"

    class GenerationSpanData:
        type = "generation"

    class FunctionSpanData:
        type = "function"

    class AgentSpanData:
        type = "agent"

    class HandoffSpanData:
        type = "handoff"

    tracing_mod.TracingProcessor = TracingProcessor
    tracing_mod.Trace = Trace
    tracing_mod.Span = Span
    tracing_mod.ResponseSpanData = ResponseSpanData
    tracing_mod.GenerationSpanData = GenerationSpanData
    tracing_mod.FunctionSpanData = FunctionSpanData
    tracing_mod.AgentSpanData = AgentSpanData
    tracing_mod.HandoffSpanData = HandoffSpanData

    agents_mod = types.ModuleType("agents")
    agents_mod.tracing = tracing_mod
    return agents_mod, tracing_mod


def _build_processor_with_agents(metadata=None):
    """Build an OpenAIAgentsTracingProcessor with mocked agents module."""
    agents_mock, tracing_mock = _make_agents_mock()
    mocked_modules = {
        "agents": agents_mock,
        "agents.tracing": tracing_mock,
    }
    with patch.dict(sys.modules, mocked_modules):
        # Remove cached module so reimport picks up mock
        for mod_name in list(sys.modules.keys()):
            if "openai_agents_sdk" in mod_name:
                del sys.modules[mod_name]

        from langsmith.integrations.openai_agents_sdk._openai_agents import (
            OpenAIAgentsTracingProcessor,
        )

        ls_client_mock = MagicMock()
        processor = OpenAIAgentsTracingProcessor(
            client=ls_client_mock,
            metadata=metadata,
        )
        return processor, tracing_mock


class TestLsInvocationParamsMerging:
    """Tests that ls_invocation_params from metadata are merged into invocation_params."""

    def _make_span(self, tracing_mock, invocation_params=None, metadata_extra=None):
        """Construct a minimal mock Span with ResponseSpanData."""
        span = MagicMock(spec_set=["span_id", "parent_id", "trace_id", "error",
                                   "span_data", "started_at", "ended_at"])
        span.span_id = "span-1"
        span.parent_id = "trace-1"
        span.trace_id = "trace-1"
        span.error = None
        span.started_at = None
        span.ended_at = None
        span.span_data = tracing_mock.ResponseSpanData()
        return span

    def test_auto_extracted_invocation_params_added_to_metadata(self):
        """Auto-extracted invocation_params from response spans appear in metadata."""
        processor, tracing_mock = _build_processor_with_agents(metadata=None)

        # Seed the _runs dict with a mock RunTree
        mock_run = MagicMock()
        mock_run.extra = {}
        processor._runs["span-1"] = mock_run
        processor._unposted_spans = set()

        span = self._make_span(tracing_mock)

        # Patch extract_span_data to return invocation_params
        with patch(
            "langsmith.integrations.openai_agents_sdk._openai_agents.agent_utils"
        ) as mock_utils:
            mock_utils.get_run_name.return_value = "test-span"
            mock_utils.extract_span_data.return_value = {
                "outputs": {"answer": "42"},
                "inputs": {},
                "invocation_params": {"model": "gpt-4o", "temperature": 0.7},
                "metadata": {"ls_model_name": "gpt-4o"},
            }

            processor.on_span_end(span)

        assert mock_run.extra.get("invocation_params") == {
            "model": "gpt-4o",
            "temperature": 0.7,
        }
        assert mock_run.extra["metadata"]["ls_invocation_params"] == {
            "model": "gpt-4o",
            "temperature": 0.7,
        }

    def test_user_supplied_ls_invocation_params_merged(self):
        """User-supplied ls_invocation_params override auto-extracted ones."""
        user_metadata = {"ls_invocation_params": {"seed": 42, "custom_tag": "prod"}}
        processor, tracing_mock = _build_processor_with_agents(metadata=user_metadata)

        mock_run = MagicMock()
        mock_run.extra = {}
        processor._runs["span-1"] = mock_run
        processor._unposted_spans = set()

        span = self._make_span(tracing_mock)

        with patch(
            "langsmith.integrations.openai_agents_sdk._openai_agents.agent_utils"
        ) as mock_utils:
            mock_utils.get_run_name.return_value = "test-span"
            mock_utils.extract_span_data.return_value = {
                "outputs": {},
                "inputs": {},
                "invocation_params": {"model": "gpt-4o", "temperature": 0.5},
                "metadata": {},
            }

            processor.on_span_end(span)

        merged = mock_run.extra.get("invocation_params", {})
        assert merged.get("model") == "gpt-4o"
        assert merged.get("temperature") == 0.5
        # User-supplied params are present
        assert merged.get("seed") == 42
        assert merged.get("custom_tag") == "prod"

        ls_inv = mock_run.extra["metadata"].get("ls_invocation_params", {})
        assert ls_inv.get("seed") == 42
        assert ls_inv.get("model") == "gpt-4o"

    def test_no_invocation_params_with_only_user_metadata(self):
        """User-supplied ls_invocation_params work even with no auto-extracted params."""
        user_metadata = {"ls_invocation_params": {"seed": 99}}
        processor, tracing_mock = _build_processor_with_agents(metadata=user_metadata)

        mock_run = MagicMock()
        mock_run.extra = {}
        processor._runs["span-1"] = mock_run
        processor._unposted_spans = set()

        span = self._make_span(tracing_mock)

        with patch(
            "langsmith.integrations.openai_agents_sdk._openai_agents.agent_utils"
        ) as mock_utils:
            mock_utils.get_run_name.return_value = "test-span"
            mock_utils.extract_span_data.return_value = {
                "outputs": {},
                "inputs": {},
                "metadata": {},
            }

            processor.on_span_end(span)

        assert mock_run.extra["invocation_params"] == {"seed": 99}
        assert mock_run.extra["metadata"]["ls_invocation_params"] == {"seed": 99}

    def test_no_params_when_neither_present(self):
        """No invocation_params set when neither auto-extracted nor user-supplied."""
        processor, tracing_mock = _build_processor_with_agents(metadata=None)

        mock_run = MagicMock()
        mock_run.extra = {}
        processor._runs["span-1"] = mock_run
        processor._unposted_spans = set()

        span = self._make_span(tracing_mock)

        with patch(
            "langsmith.integrations.openai_agents_sdk._openai_agents.agent_utils"
        ) as mock_utils:
            mock_utils.get_run_name.return_value = "test-span"
            mock_utils.extract_span_data.return_value = {
                "outputs": {},
                "inputs": {},
                "metadata": {},
            }

            processor.on_span_end(span)

        assert "invocation_params" not in mock_run.extra
        assert "ls_invocation_params" not in mock_run.extra.get("metadata", {})
