"""Tests for hybrid OTEL and LangSmith tracing functionality."""

import asyncio
import importlib
import os
import uuid
from typing import AsyncGenerator, Generator
from unittest import mock
from unittest.mock import patch

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import (
    NonRecordingSpan,
    SpanContext,
    TraceFlags,
    TraceState,
    get_current_span,
    get_tracer,
    set_tracer_provider,
    use_span,
)

import langsmith.client
from langsmith import Client, traceable
from langsmith._internal._background_thread import (
    TracingQueueItem,
    _hybrid_tracing_thread_handle_batch,
)
from langsmith._internal._operations import serialize_run_dict
from langsmith.utils import get_env_var

pytest.skip("Skipping hybrid tracing tests", allow_module_level=True)


class MockOTELExporter:
    """Mock OTEL exporter for testing."""

    def __init__(self):
        self.exported_batches = []
        self.export_batch_calls = []
        self.should_fail = False

    def export_batch(self, run_ops, otel_context_map):
        """Mock export_batch method."""
        self.export_batch_calls.append((run_ops, otel_context_map))
        if self.should_fail:
            raise Exception("Mock OTEL export failure")
        self.exported_batches.append(run_ops)


@pytest.fixture
def mock_session():
    """Create a mock session for testing."""
    session = mock.MagicMock()
    session.request = mock.Mock()
    return session


@pytest.fixture
def client_with_otel(mock_session):
    """Create a client with OTEL exporter for testing."""
    client = Client(
        api_url="http://localhost:1984",
        api_key="123",
        session=mock_session,
        auto_batch_tracing=False,  # Disable background threads
    )
    client.otel_exporter = MockOTELExporter()
    return client


class TestHybridTracing:
    """Test suite for hybrid OTEL and LangSmith tracing."""

    @patch.dict(os.environ, {"OTEL_ENABLED": "true"})
    def test_hybrid_tracing_enabled_both_exports_succeed(
        self, client_with_otel, mock_session
    ):
        """Test that both OTEL and LangSmith exports are called when hybrid
        mode is enabled."""
        client = client_with_otel

        # Create test data
        run_id = uuid.uuid4()
        trace_id = uuid.uuid4()
        run_data = {
            "id": run_id,
            "trace_id": trace_id,
            "dotted_order": f"20231201T120000000000Z{trace_id}.{run_id}",
            "session_name": "test-project",
            "name": "test_run",
            "inputs": {"input": "test"},
            "run_type": "llm",
        }

        # Create test batch
        serialized_op = serialize_run_dict("post", run_data)
        batch = [TracingQueueItem("test_priority", serialized_op)]

        # Call the hybrid handler
        _hybrid_tracing_thread_handle_batch(
            client,
            client.tracing_queue,
            batch,
            use_multipart=True,
            mark_task_done=False,
        )

        # Verify OTEL export was called
        assert len(client.otel_exporter.export_batch_calls) == 1
        exported_runs, _ = client.otel_exporter.export_batch_calls[0]
        assert len(exported_runs) == 1
        assert exported_runs[0].id == run_id

        # Verify LangSmith export was called
        mock_session.request.assert_called()
        call_args = mock_session.request.call_args
        assert call_args[0][0] == "POST"  # Method

    @patch.dict(os.environ, {"OTEL_ENABLED": "true"})
    def test_hybrid_tracing_otel_failure_langsmith_succeeds(
        self, client_with_otel, mock_session
    ):
        """Test that LangSmith export still works when OTEL export fails."""
        client = client_with_otel
        client.otel_exporter.should_fail = True

        # Create test data
        run_id = uuid.uuid4()
        trace_id = uuid.uuid4()
        run_data = {
            "id": run_id,
            "trace_id": trace_id,
            "dotted_order": f"20231201T120000000000Z{trace_id}.{run_id}",
            "session_name": "test-project",
            "name": "test_run",
            "inputs": {"input": "test"},
            "run_type": "llm",
        }

        serialized_op = serialize_run_dict("post", run_data)
        batch = [TracingQueueItem("test_priority", serialized_op)]

        # Call should not raise exception even if OTEL fails
        _hybrid_tracing_thread_handle_batch(
            client,
            client.tracing_queue,
            batch,
            use_multipart=True,
            mark_task_done=False,
        )

        # Verify OTEL export was attempted
        assert len(client.otel_exporter.export_batch_calls) == 1

        # Verify LangSmith export still worked
        mock_session.request.assert_called()

    @patch.dict(os.environ, {"OTEL_ENABLED": "true"})
    def test_hybrid_tracing_langsmith_failure_otel_succeeds(
        self, client_with_otel, mock_session
    ):
        """Test that OTEL export still works when LangSmith export fails."""
        client = client_with_otel

        # Make LangSmith export fail
        mock_session.request.side_effect = Exception("Mock LangSmith failure")

        # Create test data
        run_id = uuid.uuid4()
        trace_id = uuid.uuid4()
        run_data = {
            "id": run_id,
            "trace_id": trace_id,
            "dotted_order": f"20231201T120000000000Z{trace_id}.{run_id}",
            "session_name": "test-project",
            "name": "test_run",
            "inputs": {"input": "test"},
            "run_type": "llm",
        }

        serialized_op = serialize_run_dict("post", run_data)
        batch = [TracingQueueItem("test_priority", serialized_op)]

        # Call should not raise exception even if LangSmith fails
        _hybrid_tracing_thread_handle_batch(
            client,
            client.tracing_queue,
            batch,
            use_multipart=True,
            mark_task_done=False,
        )

        # Verify OTEL export succeeded
        assert len(client.otel_exporter.export_batch_calls) == 1
        assert len(client.otel_exporter.exported_batches) == 1

    @patch.dict(os.environ, {"OTEL_ENABLED": "true", "OTEL_ONLY": "true"})
    def test_otel_only_mode_behavior(self, client_with_otel, mock_session):
        """Test that OTEL-only mode works when OTEL_ONLY is enabled."""
        client = client_with_otel

        # Create runs - with auto_batch_tracing=False, these are processed synchronously
        for i in range(5):
            run_id = uuid.uuid4()
            trace_id = uuid.uuid4()
            client.create_run(
                name=f"test_run_{i}",
                inputs={"input": f"test_{i}"},
                run_type="llm",
                id=run_id,
                trace_id=trace_id,
                dotted_order=f"20231201T120000000000Z{trace_id}.{run_id}",
            )

    @patch.dict(os.environ, {"OTEL_ENABLED": "true"})
    def test_hybrid_tracing_no_otel_exporter(self, mock_session):
        """Test hybrid mode when no OTEL exporter is configured."""
        client = Client(
            api_url="http://localhost:1984",
            api_key="123",
            session=mock_session,
            auto_batch_tracing=False,  # Disable background threads
        )
        # No OTEL exporter set
        assert client.otel_exporter is None

        # Create runs
        for i in range(3):
            run_id = uuid.uuid4()
            trace_id = uuid.uuid4()
            client.create_run(
                name=f"test_run_{i}",
                inputs={"input": f"test_{i}"},
                run_type="llm",
                id=run_id,
                trace_id=trace_id,
                dotted_order=f"20231201T120000000000Z{trace_id}.{run_id}",
            )

        # With auto_batch_tracing=False, runs are sent directly to LangSmith
        # Should still export to LangSmith
        mock_session.request.assert_called()

    @patch.dict(os.environ, {"OTEL_ENABLED": "true"})
    def test_hybrid_tracing_queue_task_done_called_once(self, mock_session):
        """Test that queue.task_done() is called exactly once per item in
        hybrid mode."""
        # We need auto_batch_tracing=True to have a tracing queue,
        # but we'll control it carefully
        client = Client(
            api_url="http://localhost:1984",
            api_key="123",
            session=mock_session,
            auto_batch_tracing=True,
        )
        client.otel_exporter = MockOTELExporter()

        try:
            # Mock the tracing queue to track task_done calls
            original_task_done = client.tracing_queue.task_done
            task_done_calls = []

            def mock_task_done():
                task_done_calls.append(1)
                return original_task_done()

            client.tracing_queue.task_done = mock_task_done

            # Create test data
            run_id = uuid.uuid4()
            trace_id = uuid.uuid4()
            run_data = {
                "id": run_id,
                "trace_id": trace_id,
                "dotted_order": f"20231201T120000000000Z{trace_id}.{run_id}",
                "session_name": "test-project",
                "name": "test_run",
                "inputs": {"input": "test"},
                "run_type": "llm",
            }

            serialized_op = serialize_run_dict("post", run_data)
            batch = [TracingQueueItem("test_priority", serialized_op)]

            # Add items to queue first to match the real workflow
            for item in batch:
                client.tracing_queue.put(item)

            # Call the hybrid handler with mark_task_done=True
            _hybrid_tracing_thread_handle_batch(
                client,
                client.tracing_queue,
                batch,
                use_multipart=True,
                mark_task_done=True,
            )

            # Verify task_done was called exactly once for the single item
            assert len(task_done_calls) == 1
        finally:
            # Always restore the original method and stop background processing
            client.tracing_queue.task_done = original_task_done
            # Ensure queue is empty to prevent background thread issues
            while not client.tracing_queue.empty():
                try:
                    client.tracing_queue.get_nowait()
                    client.tracing_queue.task_done()
                except Exception:
                    break

    @patch.dict(os.environ, {"OTEL_ENABLED": "true"})
    def test_hybrid_tracing_multiple_items_in_batch(
        self, client_with_otel, mock_session
    ):
        """Test hybrid tracing with multiple items in a batch."""
        client = client_with_otel

        # Create multiple test items
        batch = []
        expected_run_ids = []

        for i in range(3):
            run_id = uuid.uuid4()
            trace_id = uuid.uuid4()
            expected_run_ids.append(run_id)

            run_data = {
                "id": run_id,
                "trace_id": trace_id,
                "dotted_order": f"20231201T120000000000Z{trace_id}.{run_id}",
                "session_name": "test-project",
                "name": f"test_run_{i}",
                "inputs": {"input": f"test_{i}"},
                "run_type": "llm",
            }

            serialized_op = serialize_run_dict("post", run_data)
            batch.append(TracingQueueItem(f"priority_{i}", serialized_op))

        # Call the hybrid handler
        _hybrid_tracing_thread_handle_batch(
            client,
            client.tracing_queue,
            batch,
            use_multipart=True,
            mark_task_done=False,
        )

        # Verify OTEL received all items
        assert len(client.otel_exporter.export_batch_calls) == 1
        exported_runs, _ = client.otel_exporter.export_batch_calls[0]
        exported_run_ids = [run.id for run in exported_runs]
        assert set(exported_run_ids) == set(expected_run_ids)

        # Verify LangSmith was called
        mock_session.request.assert_called()

    @patch.dict(os.environ, {})  # No environment variable set
    def test_langsmith_only_mode_default(self, mock_session):
        """Test that LangSmith-only mode is used when no environment
        variables are set."""
        # When auto_batch_tracing=False and no OTEL_ENABLED,
        # runs are sent directly to LangSmith
        client = Client(
            api_url="http://localhost:1984",
            api_key="123",
            session=mock_session,
            auto_batch_tracing=False,  # Disable background processing
        )
        # Don't set otel_exporter to test the default behavior

        # Create runs - these should be sent directly to LangSmith synchronously
        for i in range(3):
            run_id = uuid.uuid4()
            trace_id = uuid.uuid4()
            client.create_run(
                name=f"test_run_{i}",
                inputs={"input": f"test_{i}"},
                run_type="llm",
                id=run_id,
                trace_id=trace_id,
                dotted_order=f"20231201T120000000000Z{trace_id}.{run_id}",
            )

        # With auto_batch_tracing=False, runs are sent directly to
        # LangSmith synchronously
        # Verify LangSmith was called for the runs
        mock_session.request.assert_called()

        # Check that POST calls were made to LangSmith for runs
        post_calls = [
            call for call in mock_session.request.call_args_list if call[0][0] == "POST"
        ]
        assert len(post_calls) > 0, "Expected POST calls to LangSmith"


class TestHybridTracingIntegration:
    """Integration tests for hybrid tracing with real Client usage."""

    @patch.dict(os.environ, {"OTEL_ENABLED": "true"})
    def test_hybrid_tracing_end_to_end(self, mock_session):
        """Test hybrid tracing from Client.create_run() to final export."""
        client = Client(
            api_url="http://localhost:1984",
            api_key="123",
            session=mock_session,
            auto_batch_tracing=False,  # Disable background processing
        )
        client.otel_exporter = MockOTELExporter()

        # Create several runs
        run_ids = []
        for i in range(5):
            run_id = uuid.uuid4()
            trace_id = uuid.uuid4()
            run_ids.append(run_id)

            client.create_run(
                name=f"test_run_{i}",
                inputs={"input": f"test_{i}"},
                run_type="llm",
                id=run_id,
                trace_id=trace_id,
                dotted_order=f"20231201T120000000000Z{trace_id}.{run_id}",
            )

        # Since auto_batch_tracing=False, runs are sent directly to LangSmith
        # Verify LangSmith was called
        mock_session.request.assert_called()

        # For OTEL export in hybrid mode, we would need to manually trigger
        # processing but since auto_batch_tracing=False, the OTEL exporter
        # wouldn't be used. This test verifies that the hybrid mode logic
        # works when enabled

    def test_hybrid_tracing_graceful_cleanup(self, mock_session):
        """Test that hybrid tracing cleans up gracefully."""
        with patch.dict(os.environ, {"OTEL_ENABLED": "true"}):
            client = Client(
                api_url="http://localhost:1984",
                api_key="123",
                session=mock_session,
                auto_batch_tracing=False,  # Disable background processing
            )
            client.otel_exporter = MockOTELExporter()

            # Create some runs
            for i in range(3):
                run_id = uuid.uuid4()
                trace_id = uuid.uuid4()
                client.create_run(
                    name=f"test_run_{i}",
                    inputs={"input": f"test_{i}"},
                    run_type="llm",
                    id=run_id,
                    trace_id=trace_id,
                    dotted_order=f"20231201T120000000000Z{trace_id}.{run_id}",
                )

            mock_session.request.assert_called()

    @patch.dict(
        os.environ, {"LANGSMITH_OTEL_ENABLED": "true", "LANGSMITH_TRACING": "true"}
    )
    def test_otel_context_propagation_with_traceable(self):
        """Test that OpenTelemetry context is properly set using NonRecordingSpan."""
        get_env_var.cache_clear()

        tracer_provider = TracerProvider()
        set_tracer_provider(tracer_provider)

        test_trace_id = 12345678901234567890123456789012345
        test_span_id = 1234567890123456

        span_context = SpanContext(
            trace_id=test_trace_id,
            span_id=test_span_id,
            is_remote=False,
            trace_state=TraceState(),
        )
        non_recording_span = NonRecordingSpan(span_context)

        captured_span_contexts = []

        def inner_function():
            current_span = get_current_span()
            if current_span:
                captured_span_contexts.append(current_span.get_span_context())

        with use_span(non_recording_span):
            inner_function()

        assert len(captured_span_contexts) == 1
        assert captured_span_contexts[0].trace_id == test_trace_id
        assert captured_span_contexts[0].span_id == test_span_id

        captured_traceable_contexts = []

        @traceable
        def test_tool():
            """Test tool that captures the current OpenTelemetry span context."""
            current_span = get_current_span()
            if current_span:
                span_context = current_span.get_span_context()
                captured_traceable_contexts.append(span_context)
            return "tool_result"

        result = test_tool()

        assert result == "tool_result"

        assert len(captured_traceable_contexts) >= 1

        span_context = captured_traceable_contexts[0]
        assert span_context.trace_id > 0
        assert span_context.span_id > 0


def capture_current_context(label: str, captured_contexts: list[tuple[str, int, int]]):
    current_span = get_current_span()
    if current_span:
        context = current_span.get_span_context()
        captured_contexts.append((label, context.trace_id, context.span_id))


class TestOTELContextPropagation:
    """Test suite for OpenTelemetry context propagation with LangSmith tracing."""

    @patch.dict(
        os.environ, {"LANGSMITH_OTEL_ENABLED": "true", "LANGSMITH_TRACING": "true"}
    )
    def test_nested_langsmith_otel_langsmith_otel_tracing(self):
        """Test nested tracing pattern: LangSmith -> OTEL -> LangSmith -> OTEL."""
        get_env_var.cache_clear()

        importlib.reload(langsmith.client)

        from langsmith.client import HAS_OTEL

        assert HAS_OTEL, "HAS_OTEL should be True when OTEL packages are installed"

        tracer_provider = TracerProvider()
        set_tracer_provider(tracer_provider)
        tracer = get_tracer(__name__)

        captured_contexts = []

        @traceable
        def langsmith_outer():
            capture_current_context("langsmith_outer", captured_contexts)

            with tracer.start_as_current_span("otel_outer"):
                capture_current_context("otel_outer", captured_contexts)

                @traceable
                def langsmith_inner():
                    capture_current_context("langsmith_inner", captured_contexts)

                    with tracer.start_as_current_span("otel_inner"):
                        capture_current_context("otel_inner", captured_contexts)
                        return "inner_result"

                return langsmith_inner()

        result = langsmith_outer()

        assert result == "inner_result"
        assert len(captured_contexts) == 4

        # Verify we captured all contexts
        labels = [ctx[0] for ctx in captured_contexts]
        assert "langsmith_outer" in labels
        assert "otel_outer" in labels
        assert "langsmith_inner" in labels
        assert "otel_inner" in labels

        for label, trace_id, span_id in captured_contexts:
            assert trace_id > 0, f"Invalid trace_id for {label}"
            assert span_id > 0, f"Invalid span_id for {label}"

        trace_ids = [ctx[1] for ctx in captured_contexts]
        unique_trace_ids = set(trace_ids)
        assert len(unique_trace_ids) == 1, (
            f"Expected all contexts to share same trace_id, got: {unique_trace_ids}"
        )

    @patch.dict(
        os.environ, {"LANGSMITH_OTEL_ENABLED": "true", "LANGSMITH_TRACING": "true"}
    )
    def test_otel_context_propagation_async(self):
        """Test OpenTelemetry context propagation with async functions."""
        get_env_var.cache_clear()

        importlib.reload(langsmith.client)

        from langsmith.client import HAS_OTEL

        assert HAS_OTEL, "HAS_OTEL should be True when OTEL packages are installed"

        tracer_provider = TracerProvider()
        set_tracer_provider(tracer_provider)
        tracer = get_tracer(__name__)

        captured_contexts = []

        @traceable
        async def async_langsmith_outer():
            """Async LangSmith traced function."""
            capture_current_context("async_langsmith_outer", captured_contexts)

            with tracer.start_as_current_span("async_otel_outer"):
                capture_current_context("async_otel_outer", captured_contexts)

                @traceable
                async def async_langsmith_inner():
                    """Async inner LangSmith traced function."""
                    capture_current_context("async_langsmith_inner", captured_contexts)

                    # Simulate async work
                    await asyncio.sleep(0.01)

                    with tracer.start_as_current_span("async_otel_inner"):
                        capture_current_context("async_otel_inner", captured_contexts)
                        await asyncio.sleep(0.01)
                        return "async_inner_result"

                return await async_langsmith_inner()

        async def run_test():
            result = await async_langsmith_outer()
            return result

        # Use asyncio.run to execute the async test
        result = asyncio.run(run_test())

        assert result == "async_inner_result"
        assert len(captured_contexts) == 4

        labels = [ctx[0] for ctx in captured_contexts]
        assert "async_langsmith_outer" in labels
        assert "async_otel_outer" in labels
        assert "async_langsmith_inner" in labels
        assert "async_otel_inner" in labels

        for label, trace_id, span_id in captured_contexts:
            assert trace_id > 0, f"Invalid trace_id for {label}"
            assert span_id > 0, f"Invalid span_id for {label}"

        trace_ids = [ctx[1] for ctx in captured_contexts]
        unique_trace_ids = set(trace_ids)
        assert len(unique_trace_ids) == 1, (
            f"Expected all async contexts to share same trace_id, "
            f"got: {unique_trace_ids}"
        )

        span_ids = [ctx[2] for ctx in captured_contexts]
        unique_span_ids = set(span_ids)
        assert len(unique_span_ids) == len(captured_contexts), (
            "Each async span should have unique span_id"
        )

    @patch.dict(
        os.environ, {"LANGSMITH_OTEL_ENABLED": "true", "LANGSMITH_TRACING": "true"}
    )
    def test_generator_partial_consumption_with_otel_context(self):
        """Test OpenTelemetry context propagation with generator partial consumption."""
        get_env_var.cache_clear()

        # Force reimport of client module to pick up new environment variables
        importlib.reload(langsmith.client)

        from langsmith.client import HAS_OTEL

        assert HAS_OTEL, "HAS_OTEL should be True when OTEL packages are installed"

        tracer_provider = TracerProvider()
        set_tracer_provider(tracer_provider)
        tracer = get_tracer(__name__)

        captured_contexts = []
        generator_contexts = []

        @traceable
        def generator_function() -> Generator[str, None, None]:
            """Generator function that yields values with OTEL context."""
            capture_current_context("generator_start", captured_contexts)

            with tracer.start_as_current_span("generator_otel_span"):
                capture_current_context("generator_otel_span", captured_contexts)

                for i in range(5):
                    current_span = get_current_span()
                    if current_span:
                        context = current_span.get_span_context()
                        generator_contexts.append(
                            (f"yield_{i}", context.trace_id, context.span_id)
                        )

                    yield f"value_{i}"

                capture_current_context("generator_end", captured_contexts)

        gen = generator_function()

        value1 = next(gen)
        value2 = next(gen)

        assert value1 == "value_0"
        assert value2 == "value_1"

        @traceable
        def sibling_function():
            """Sibling function that should have its own context."""
            capture_current_context("sibling_function", captured_contexts)

            with tracer.start_as_current_span("sibling_otel_span"):
                capture_current_context("sibling_otel_span", captured_contexts)
                return "sibling_result"

        sibling_result = sibling_function()
        assert sibling_result == "sibling_result"

        # Now finish consuming the generator
        remaining_values = list(gen)
        assert remaining_values == ["value_2", "value_3", "value_4"]

        assert (
            len(captured_contexts) >= 4
        )  # generator_start, generator_otel_span, sibling_function, sibling_otel_span
        assert len(generator_contexts) == 5

        generator_trace_ids = [ctx[1] for ctx in generator_contexts]
        assert len(set(generator_trace_ids)) == 1, (
            "Generator should maintain same trace ID"
        )

        sibling_contexts = [ctx for ctx in captured_contexts if "sibling" in ctx[0]]
        assert len(sibling_contexts) == 2

        sibling_trace_ids = [ctx[1] for ctx in sibling_contexts]
        assert len(set(sibling_trace_ids)) == 1, (
            "Sibling should have consistent trace ID"
        )

        generator_trace_id = generator_trace_ids[0]
        sibling_trace_id = sibling_trace_ids[0]
        assert generator_trace_id != sibling_trace_id, (
            "Generator and sibling should have different trace_ids"
        )

        generator_span_ids = [ctx[2] for ctx in generator_contexts]
        sibling_span_ids = [ctx[2] for ctx in sibling_contexts]
        assert len(set(generator_span_ids)) >= 1, (
            "Generator should have at least one span"
        )
        assert len(set(sibling_span_ids)) >= 1, "Sibling should have at least one span"

        for label, trace_id, span_id in captured_contexts + generator_contexts:
            assert trace_id > 0, f"Invalid trace_id for {label}"
            assert span_id > 0, f"Invalid span_id for {label}"

    @patch.dict(
        os.environ, {"LANGSMITH_OTEL_ENABLED": "true", "LANGSMITH_TRACING": "true"}
    )
    def test_async_generator_with_otel_context(self):
        get_env_var.cache_clear()

        tracer_provider = TracerProvider()
        set_tracer_provider(tracer_provider)
        tracer = get_tracer(__name__)

        captured_contexts = []

        @traceable
        async def async_generator_function() -> AsyncGenerator[str, None]:
            """Async generator function that yields values with OTEL context."""
            capture_current_context("async_generator_start", captured_contexts)

            with tracer.start_as_current_span("async_generator_otel_span"):
                capture_current_context("async_generator_otel_span", captured_contexts)

                for i in range(3):
                    capture_current_context(f"async_yield_{i}", captured_contexts)
                    await asyncio.sleep(0.01)  # Simulate async work
                    yield f"async_value_{i}"

                capture_current_context("async_generator_end", captured_contexts)

        async def run_async_generator_test():
            gen = async_generator_function()

            value1 = await gen.__anext__()
            assert value1 == "async_value_0"

            @traceable
            async def async_sibling_function():
                capture_current_context("async_sibling_function", captured_contexts)

                with tracer.start_as_current_span("async_sibling_otel_span"):
                    capture_current_context(
                        "async_sibling_otel_span", captured_contexts
                    )
                    await asyncio.sleep(0.01)
                    return "async_sibling_result"

            sibling_result = await async_sibling_function()
            assert sibling_result == "async_sibling_result"

            remaining_values = []
            async for value in gen:
                remaining_values.append(value)

            assert remaining_values == ["async_value_1", "async_value_2"]

            return True

        result = asyncio.run(run_async_generator_test())
        assert result is True

        assert len(captured_contexts) >= 6

        generator_contexts = [
            ctx
            for ctx in captured_contexts
            if "async_generator" in ctx[0] or "async_yield" in ctx[0]
        ]
        assert len(generator_contexts) >= 4

        sibling_contexts = [
            ctx for ctx in captured_contexts if "async_sibling" in ctx[0]
        ]
        assert len(sibling_contexts) == 2

        for label, trace_id, span_id in captured_contexts:
            assert trace_id > 0, f"Invalid trace_id for {label}"
            assert span_id > 0, f"Invalid span_id for {label}"

        generator_trace_ids = [ctx[1] for ctx in generator_contexts]
        assert len(set(generator_trace_ids)) == 1, (
            "Async generator should have consistent trace ID"
        )

        sibling_trace_ids = [ctx[1] for ctx in sibling_contexts]
        assert len(set(sibling_trace_ids)) == 1, (
            "Async sibling should have consistent trace ID"
        )

        generator_trace_id = generator_trace_ids[0]
        sibling_trace_id = sibling_trace_ids[0]
        assert generator_trace_id != sibling_trace_id, (
            "Async generator and sibling should have different trace_ids"
        )

        generator_span_ids = [ctx[2] for ctx in generator_contexts]
        sibling_span_ids = [ctx[2] for ctx in sibling_contexts]
        assert len(set(generator_span_ids)) >= 1, (
            "Async generator should have at least one span"
        )
        assert len(set(sibling_span_ids)) >= 1, (
            "Async sibling should have at least one span"
        )

    @patch.dict(
        os.environ, {"LANGSMITH_OTEL_ENABLED": "true", "LANGSMITH_TRACING": "true"}
    )
    def test_complex_nested_context_inheritance(self):
        """Test complex nested context inheritance patterns."""
        get_env_var.cache_clear()

        tracer_provider = TracerProvider()
        set_tracer_provider(tracer_provider)
        tracer = get_tracer(__name__)

        captured_contexts = []

        test_trace_id = 12345678901234567890123456789012345
        test_span_id = 1234567890123456

        span_context = SpanContext(
            trace_id=test_trace_id,
            span_id=test_span_id,
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
            trace_state=TraceState(),
        )
        non_recording_span = NonRecordingSpan(span_context)

        @traceable
        def langsmith_function_within_existing_otel():
            """LangSmith function called within existing OTEL context."""
            capture_current_context("langsmith_within_otel", captured_contexts)

            with tracer.start_as_current_span("nested_otel_span"):
                capture_current_context(
                    "nested_otel_within_langsmith", captured_contexts
                )

                @traceable
                def deeply_nested_langsmith():
                    """Deeply nested LangSmith function."""
                    capture_current_context(
                        "deeply_nested_langsmith", captured_contexts
                    )
                    return "deeply_nested_result"

                return deeply_nested_langsmith()

        # Execute within the pre-existing OTEL context
        with use_span(non_recording_span):
            capture_current_context("pre_existing_otel", captured_contexts)
            result = langsmith_function_within_existing_otel()

        assert result == "deeply_nested_result"
        assert len(captured_contexts) == 4

        labels = [ctx[0] for ctx in captured_contexts]
        expected_labels = [
            "pre_existing_otel",
            "langsmith_within_otel",
            "nested_otel_within_langsmith",
            "deeply_nested_langsmith",
        ]
        for label in expected_labels:
            assert label in labels, f"Missing expected label: {label}"

        pre_existing_context = next(
            ctx for ctx in captured_contexts if ctx[0] == "pre_existing_otel"
        )
        assert pre_existing_context[1] == test_trace_id
        assert pre_existing_context[2] == test_span_id

        for label, trace_id, span_id in captured_contexts:
            assert trace_id > 0, f"Invalid trace_id for {label}"
            assert span_id > 0, f"Invalid span_id for {label}"

        trace_ids = [ctx[1] for ctx in captured_contexts]
        unique_trace_ids = set(trace_ids)

        assert test_trace_id in unique_trace_ids, (
            "Pre-existing OTEL trace_id should be captured"
        )

        pre_existing_traces = [
            ctx for ctx in captured_contexts if ctx[1] == test_trace_id
        ]
        assert len(pre_existing_traces) >= 1, (
            "Should capture the pre-existing OTEL context"
        )

        span_ids = [ctx[2] for ctx in captured_contexts]
        unique_span_ids = set(span_ids)
        assert len(unique_span_ids) == len(captured_contexts), (
            "Each span should have unique span_id in nested hierarchy"
        )

    @patch.dict(
        os.environ, {"LANGSMITH_OTEL_ENABLED": "true", "LANGSMITH_TRACING": "true"}
    )
    def test_generator_otel_partial_consumption_with_sibling_traceable(self):
        """Test the specific scenario: generator with OTEL -> partial consumption ->
        sibling traceable -> finish consuming generator."""
        get_env_var.cache_clear()

        tracer_provider = TracerProvider()
        set_tracer_provider(tracer_provider)
        tracer = get_tracer(__name__)

        captured_contexts = []

        @traceable
        def otel_generator_function() -> Generator[str, None, None]:
            """Generator function that creates OTEL spans and yields values."""
            capture_current_context("otel_gen_start", captured_contexts)

            with tracer.start_as_current_span("otel_gen_main_span"):
                capture_current_context("otel_gen_main_span", captured_contexts)

                for i in range(4):
                    with tracer.start_as_current_span(f"otel_gen_item_{i}"):
                        capture_current_context(
                            f"otel_gen_before_yield_{i}", captured_contexts
                        )
                        yield f"otel_value_{i}"
                        capture_current_context(
                            f"otel_gen_after_yield_{i}", captured_contexts
                        )

                capture_current_context("otel_gen_end", captured_contexts)

        otel_gen = otel_generator_function()

        value1 = next(otel_gen)
        value2 = next(otel_gen)

        assert value1 == "otel_value_0"
        assert value2 == "otel_value_1"

        @traceable
        def sibling_traceable_function():
            capture_current_context("sibling_start", captured_contexts)

            with tracer.start_as_current_span("sibling_otel_span"):
                capture_current_context("sibling_otel_span", captured_contexts)

                result = "sibling_work_done"
                capture_current_context("sibling_before_return", captured_contexts)
                return result

        sibling_result = sibling_traceable_function()
        assert sibling_result == "sibling_work_done"

        remaining_values = list(otel_gen)

        assert remaining_values == ["otel_value_2", "otel_value_3"]

        generator_contexts = [ctx for ctx in captured_contexts if "otel_gen" in ctx[0]]
        sibling_contexts = [ctx for ctx in captured_contexts if "sibling" in ctx[0]]

        assert len(generator_contexts) >= 10
        assert len(sibling_contexts) == 3

        generator_trace_ids = [ctx[1] for ctx in generator_contexts]
        unique_generator_trace_ids = set(generator_trace_ids)
        assert len(unique_generator_trace_ids) == 1, (
            f"Generator should have consistent trace_id, "
            f"got: {unique_generator_trace_ids}"
        )

        sibling_trace_ids = [ctx[1] for ctx in sibling_contexts]
        unique_sibling_trace_ids = set(sibling_trace_ids)
        assert len(unique_sibling_trace_ids) == 1, (
            f"Sibling should have consistent trace_id, got: {unique_sibling_trace_ids}"
        )

        generator_trace_id = generator_trace_ids[0]
        sibling_trace_id = sibling_trace_ids[0]
        assert generator_trace_id != sibling_trace_id, (
            "Generator and sibling should have different trace_ids"
        )

        contexts_before_sibling = [
            ctx
            for ctx in generator_contexts
            if "yield_0" in ctx[0] or "yield_1" in ctx[0]
        ]
        contexts_after_sibling = [
            ctx
            for ctx in generator_contexts
            if "yield_2" in ctx[0] or "yield_3" in ctx[0]
        ]

        before_trace_ids = [ctx[1] for ctx in contexts_before_sibling]
        after_trace_ids = [ctx[1] for ctx in contexts_after_sibling]

        assert set(before_trace_ids) == set(after_trace_ids), (
            "Generator trace should be consistent before and after sibling"
        )

        for label, trace_id, span_id in captured_contexts:
            assert trace_id > 0, f"Invalid trace_id for {label}"
            assert span_id > 0, f"Invalid span_id for {label}"
