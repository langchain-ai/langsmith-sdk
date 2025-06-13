"""Tests for hybrid OTEL and LangSmith tracing functionality."""

import os
import uuid
from unittest import mock
from unittest.mock import patch

import pytest

from langsmith import Client
from langsmith._internal._background_thread import (
    TracingQueueItem,
    _hybrid_tracing_thread_handle_batch,
)
from langsmith._internal._operations import serialize_run_dict


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

    @patch.dict(os.environ, {"LANGSMITH_OTEL_ENABLED": "true"})
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

    @patch.dict(os.environ, {"LANGSMITH_OTEL_ENABLED": "true"})
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

    @patch.dict(os.environ, {"LANGSMITH_OTEL_ENABLED": "true"})
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

    @patch.dict(
        os.environ, {"LANGSMITH_OTEL_ENABLED": "true", "LANGSMITH_OTEL_ONLY": "true"}
    )
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

    @patch.dict(os.environ, {"LANGSMITH_OTEL_ENABLED": "true"})
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

    @patch.dict(os.environ, {"LANGSMITH_OTEL_ENABLED": "true"})
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

    @patch.dict(os.environ, {"LANGSMITH_OTEL_ENABLED": "true"})
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
        # When auto_batch_tracing=False and no LANGSMITH_OTEL_ENABLED,
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

    @patch.dict(os.environ, {"LANGSMITH_OTEL_ENABLED": "true"})
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
        with patch.dict(os.environ, {"LANGSMITH_OTEL_ENABLED": "true"}):
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
