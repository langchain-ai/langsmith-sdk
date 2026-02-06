"""Unit tests for OpenAIAgentsTracingProcessor memory leak fixes."""

from unittest import mock

import pytest

# Check if agents package is available before defining tests
try:
    from agents import tracing

    HAVE_AGENTS = True
except ImportError:
    HAVE_AGENTS = False


@pytest.mark.skipif(not HAVE_AGENTS, reason="agents package not installed")
class TestMemoryLeakPrevention:
    """Tests for memory leak prevention in OpenAIAgentsTracingProcessor."""

    @pytest.fixture
    def processor(self):
        """Create a processor instance with mocked client."""
        from langsmith.wrappers import OpenAIAgentsTracingProcessor

        mock_client = mock.MagicMock()
        return OpenAIAgentsTracingProcessor(client=mock_client)

    @pytest.fixture
    def mock_trace(self):
        """Create a mock trace object."""
        trace = mock.MagicMock(spec=tracing.Trace)
        trace.trace_id = "trace-123"
        trace.name = "Test Trace"
        trace.export.return_value = {"group_id": "group-1"}
        return trace

    @pytest.fixture
    def mock_span(self):
        """Create a mock span object."""
        span = mock.MagicMock(spec=tracing.Span)
        span.span_id = "span-456"
        span.trace_id = "trace-123"
        span.parent_id = None
        span.started_at = "2024-01-01T00:00:00"
        span.ended_at = "2024-01-01T00:00:01"
        span.error = None
        span.name = "Test Span"
        # Set span_data to a mock that is NOT ResponseSpanData or GenerationSpanData
        span.span_data = mock.MagicMock()
        return span

    def test_runs_dict_grows_without_cleanup(self, processor):
        """Test that _runs dict accumulates entries when traces are started but not ended."""
        with mock.patch(
            "langsmith.integrations.openai_agents_sdk._openai_agents.get_current_run_tree",
            return_value=None,
        ):
            with mock.patch(
                "langsmith.integrations.openai_agents_sdk._openai_agents.rt.RunTree"
            ) as mock_run_tree:
                mock_run = mock.MagicMock()
                mock_run_tree.return_value = mock_run

                # Start 3 traces without ending them
                for i in range(3):
                    trace = mock.MagicMock(spec=tracing.Trace)
                    trace.trace_id = f"trace-{i}"
                    trace.name = f"Test Trace {i}"
                    trace.export.return_value = {}
                    processor.on_trace_start(trace)

        # Verify all 3 entries are in _runs
        assert len(processor._runs) == 3
        assert "trace-0" in processor._runs
        assert "trace-1" in processor._runs
        assert "trace-2" in processor._runs

    def test_on_trace_end_cleans_up_runs(self, processor, mock_trace):
        """Test that on_trace_end properly cleans up _runs dict."""
        with mock.patch(
            "langsmith.integrations.openai_agents_sdk._openai_agents.get_current_run_tree",
            return_value=None,
        ):
            with mock.patch(
                "langsmith.integrations.openai_agents_sdk._openai_agents.rt.RunTree"
            ) as mock_run_tree:
                mock_run = mock.MagicMock()
                mock_run_tree.return_value = mock_run

                processor.on_trace_start(mock_trace)

        assert "trace-123" in processor._runs

        # End the trace
        processor.on_trace_end(mock_trace)

        # Verify cleanup
        assert "trace-123" not in processor._runs

    def test_on_trace_end_cleans_up_response_inputs_outputs(
        self, processor, mock_trace
    ):
        """Test that on_trace_end cleans up _first_response_inputs and _last_response_outputs."""
        with mock.patch(
            "langsmith.integrations.openai_agents_sdk._openai_agents.get_current_run_tree",
            return_value=None,
        ):
            with mock.patch(
                "langsmith.integrations.openai_agents_sdk._openai_agents.rt.RunTree"
            ) as mock_run_tree:
                mock_run = mock.MagicMock()
                mock_run_tree.return_value = mock_run

                processor.on_trace_start(mock_trace)

        # Manually add entries to response dicts (simulating span processing)
        processor._first_response_inputs["trace-123"] = {"input": "test"}
        processor._last_response_outputs["trace-123"] = {"output": "test"}

        assert "trace-123" in processor._first_response_inputs
        assert "trace-123" in processor._last_response_outputs

        # End the trace
        processor.on_trace_end(mock_trace)

        # Verify cleanup
        assert "trace-123" not in processor._first_response_inputs
        assert "trace-123" not in processor._last_response_outputs

    def test_on_span_end_cleans_up_runs(self, processor, mock_trace, mock_span):
        """Test that on_span_end properly cleans up _runs dict for spans."""
        with mock.patch(
            "langsmith.integrations.openai_agents_sdk._openai_agents.get_current_run_tree",
            return_value=None,
        ):
            with mock.patch(
                "langsmith.integrations.openai_agents_sdk._openai_agents.rt.RunTree"
            ) as mock_run_tree:
                mock_run = mock.MagicMock()
                mock_child_run = mock.MagicMock()
                mock_run.create_child.return_value = mock_child_run
                mock_run_tree.return_value = mock_run

                with mock.patch(
                    "langsmith.integrations.openai_agents_sdk._openai_agents.agent_utils"
                ) as mock_utils:
                    mock_utils.get_run_name.return_value = "test"
                    mock_utils.get_run_type.return_value = "chain"
                    mock_utils.extract_span_data.return_value = {"inputs": {}}

                    # Start trace first
                    processor.on_trace_start(mock_trace)
                    # Start span
                    processor.on_span_start(mock_span)

        assert "span-456" in processor._runs

        # End the span
        with mock.patch(
            "langsmith.integrations.openai_agents_sdk._openai_agents.agent_utils"
        ) as mock_utils:
            mock_utils.extract_span_data.return_value = {"inputs": {}, "outputs": {}}
            processor.on_span_end(mock_span)

        # Verify cleanup
        assert "span-456" not in processor._runs

    def test_response_inputs_outputs_accumulate_without_trace_end(
        self, processor, mock_trace
    ):
        """Test that _first_response_inputs and _last_response_outputs accumulate without trace end."""
        with mock.patch(
            "langsmith.integrations.openai_agents_sdk._openai_agents.get_current_run_tree",
            return_value=None,
        ):
            with mock.patch(
                "langsmith.integrations.openai_agents_sdk._openai_agents.rt.RunTree"
            ) as mock_run_tree:
                mock_run = mock.MagicMock()
                mock_child_run = mock.MagicMock()
                mock_run.create_child.return_value = mock_child_run
                mock_run_tree.return_value = mock_run

                with mock.patch(
                    "langsmith.integrations.openai_agents_sdk._openai_agents.agent_utils"
                ) as mock_utils:
                    mock_utils.get_run_name.return_value = "test"
                    mock_utils.get_run_type.return_value = "llm"
                    mock_utils.extract_span_data.return_value = {
                        "inputs": {"message": "hello"},
                        "outputs": {"response": "world"},
                    }

                    # Start trace
                    processor.on_trace_start(mock_trace)

                    # Start and end multiple spans with ResponseSpanData
                    for i in range(3):
                        span = mock.MagicMock(spec=tracing.Span)
                        span.span_id = f"span-{i}"
                        span.trace_id = "trace-123"
                        span.parent_id = None
                        span.started_at = "2024-01-01T00:00:00"
                        span.ended_at = "2024-01-01T00:00:01"
                        span.error = None
                        # Make it a ResponseSpanData type
                        span.span_data = mock.MagicMock(spec=tracing.ResponseSpanData)

                        processor.on_span_start(span)
                        processor.on_span_end(span)

        # Without calling on_trace_end, the entries remain
        assert "trace-123" in processor._first_response_inputs
        assert "trace-123" in processor._last_response_outputs

    def test_cleanup_on_trace_end_with_exception_in_processing(
        self, processor, mock_trace
    ):
        """Test that cleanup happens even if exception occurs during on_trace_end processing."""
        # Setup: Create a trace with associated data
        with mock.patch(
            "langsmith.integrations.openai_agents_sdk._openai_agents.get_current_run_tree",
            return_value=None,
        ):
            with mock.patch(
                "langsmith.integrations.openai_agents_sdk._openai_agents.rt.RunTree"
            ) as mock_run_tree:
                mock_run = mock.MagicMock()
                # Make patch() raise an exception
                mock_run.patch.side_effect = Exception("Network error")
                mock_run_tree.return_value = mock_run

                processor.on_trace_start(mock_trace)

        processor._first_response_inputs["trace-123"] = {"input": "test"}
        processor._last_response_outputs["trace-123"] = {"output": "test"}

        # The current implementation catches exceptions, so cleanup should work
        processor.on_trace_end(mock_trace)

        # After fix: All dictionaries should be cleaned up even with exception
        # The fix should use try/finally to ensure cleanup
        assert "trace-123" not in processor._runs
        assert "trace-123" not in processor._first_response_inputs
        assert "trace-123" not in processor._last_response_outputs

    def test_cleanup_on_span_end_with_exception_in_processing(
        self, processor, mock_trace, mock_span
    ):
        """Test that cleanup happens even if exception occurs during on_span_end processing."""
        with mock.patch(
            "langsmith.integrations.openai_agents_sdk._openai_agents.get_current_run_tree",
            return_value=None,
        ):
            with mock.patch(
                "langsmith.integrations.openai_agents_sdk._openai_agents.rt.RunTree"
            ) as mock_run_tree:
                mock_run = mock.MagicMock()
                mock_child_run = mock.MagicMock()
                # Make patch() raise an exception
                mock_child_run.patch.side_effect = Exception("Network error")
                mock_run.create_child.return_value = mock_child_run
                mock_run_tree.return_value = mock_run

                with mock.patch(
                    "langsmith.integrations.openai_agents_sdk._openai_agents.agent_utils"
                ) as mock_utils:
                    mock_utils.get_run_name.return_value = "test"
                    mock_utils.get_run_type.return_value = "chain"
                    mock_utils.extract_span_data.return_value = {"inputs": {}}

                    processor.on_trace_start(mock_trace)
                    processor.on_span_start(mock_span)

        assert "span-456" in processor._runs

        # End span (which will have an exception during patch())
        with mock.patch(
            "langsmith.integrations.openai_agents_sdk._openai_agents.agent_utils"
        ) as mock_utils:
            mock_utils.extract_span_data.return_value = {"inputs": {}, "outputs": {}}
            processor.on_span_end(mock_span)

        # After fix: span should be cleaned up from _runs even with exception
        assert "span-456" not in processor._runs

    def test_multiple_traces_independent_cleanup(self, processor):
        """Test that multiple traces are cleaned up independently."""
        with mock.patch(
            "langsmith.integrations.openai_agents_sdk._openai_agents.get_current_run_tree",
            return_value=None,
        ):
            with mock.patch(
                "langsmith.integrations.openai_agents_sdk._openai_agents.rt.RunTree"
            ) as mock_run_tree:
                mock_run = mock.MagicMock()
                mock_run_tree.return_value = mock_run

                # Start 3 traces
                traces = []
                for i in range(3):
                    trace = mock.MagicMock(spec=tracing.Trace)
                    trace.trace_id = f"trace-{i}"
                    trace.name = f"Test Trace {i}"
                    trace.export.return_value = {}
                    traces.append(trace)
                    processor.on_trace_start(trace)
                    processor._first_response_inputs[f"trace-{i}"] = {"input": i}
                    processor._last_response_outputs[f"trace-{i}"] = {"output": i}

        assert len(processor._runs) == 3
        assert len(processor._first_response_inputs) == 3
        assert len(processor._last_response_outputs) == 3

        # End only the middle trace
        processor.on_trace_end(traces[1])

        # Verify only trace-1 was cleaned up
        assert "trace-0" in processor._runs
        assert "trace-1" not in processor._runs
        assert "trace-2" in processor._runs

        assert "trace-0" in processor._first_response_inputs
        assert "trace-1" not in processor._first_response_inputs
        assert "trace-2" in processor._first_response_inputs

        assert "trace-0" in processor._last_response_outputs
        assert "trace-1" not in processor._last_response_outputs
        assert "trace-2" in processor._last_response_outputs

    def test_orphan_span_data_cleaned_on_trace_end(self, processor, mock_trace):
        """Test that span data keyed by trace_id is cleaned when trace ends."""
        with mock.patch(
            "langsmith.integrations.openai_agents_sdk._openai_agents.get_current_run_tree",
            return_value=None,
        ):
            with mock.patch(
                "langsmith.integrations.openai_agents_sdk._openai_agents.rt.RunTree"
            ) as mock_run_tree:
                mock_run = mock.MagicMock()
                mock_run_tree.return_value = mock_run

                processor.on_trace_start(mock_trace)

        # Simulate orphaned response data (span ended but data remains)
        processor._first_response_inputs["trace-123"] = {"orphan": "input"}
        processor._last_response_outputs["trace-123"] = {"orphan": "output"}

        # End trace should clean up everything related to this trace_id
        processor.on_trace_end(mock_trace)

        assert "trace-123" not in processor._runs
        assert "trace-123" not in processor._first_response_inputs
        assert "trace-123" not in processor._last_response_outputs

    def test_response_data_cleaned_when_trace_not_in_runs(self, processor, mock_trace):
        """Test that response data is cleaned even when trace was never added to _runs.

        This is the key memory leak scenario: if on_trace_start fails (exception),
        but spans still process and add to response dicts, on_trace_end should still
        clean up those dicts even if no run was found.
        """
        # Don't call on_trace_start - simulate a failed trace start
        # But response data exists (maybe from partial span processing)
        processor._first_response_inputs["trace-123"] = {"input": "orphan"}
        processor._last_response_outputs["trace-123"] = {"output": "orphan"}

        # Verify the run is NOT in _runs (simulating failed trace start)
        assert "trace-123" not in processor._runs

        # End trace - should clean up response data even without run
        processor.on_trace_end(mock_trace)

        # These should be cleaned up even though there was no run
        assert "trace-123" not in processor._first_response_inputs
        assert "trace-123" not in processor._last_response_outputs

    def test_span_runs_cleaned_when_trace_ends(self, processor, mock_trace, mock_span):
        """Test that orphan span entries in _runs are cleaned when trace ends.

        If spans are started but never properly ended, their entries remain in _runs.
        When the parent trace ends, these should be cleaned up.
        """
        with mock.patch(
            "langsmith.integrations.openai_agents_sdk._openai_agents.get_current_run_tree",
            return_value=None,
        ):
            with mock.patch(
                "langsmith.integrations.openai_agents_sdk._openai_agents.rt.RunTree"
            ) as mock_run_tree:
                mock_run = mock.MagicMock()

                # Create unique child runs for each span with proper extra metadata
                def create_child_with_extra(**kwargs):
                    child = mock.MagicMock()
                    # The extra parameter contains the metadata with openai_trace_id
                    child.extra = kwargs.get("extra", {})
                    return child

                mock_run.create_child.side_effect = create_child_with_extra
                mock_run_tree.return_value = mock_run

                with mock.patch(
                    "langsmith.integrations.openai_agents_sdk._openai_agents.agent_utils"
                ) as mock_utils:
                    mock_utils.get_run_name.return_value = "test"
                    mock_utils.get_run_type.return_value = "chain"
                    mock_utils.extract_span_data.return_value = {"inputs": {}}

                    # Start trace and spans
                    processor.on_trace_start(mock_trace)

                    # Start multiple spans without ending them
                    for i in range(3):
                        span = mock.MagicMock(spec=tracing.Span)
                        span.span_id = f"span-{i}"
                        span.trace_id = "trace-123"
                        span.parent_id = None
                        span.started_at = "2024-01-01T00:00:00"
                        span.error = None
                        span.span_data = mock.MagicMock()
                        processor.on_span_start(span)

        # Verify spans are in _runs
        assert "trace-123" in processor._runs
        assert "span-0" in processor._runs
        assert "span-1" in processor._runs
        assert "span-2" in processor._runs

        # End trace without ending spans - orphan spans should be cleaned up
        processor.on_trace_end(mock_trace)

        # Trace should be cleaned
        assert "trace-123" not in processor._runs

        # Orphan spans should also be cleaned (this is the fix we need)
        assert "span-0" not in processor._runs
        assert "span-1" not in processor._runs
        assert "span-2" not in processor._runs
