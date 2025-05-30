"""Tests for hybrid OTEL and LangSmith tracing functionality."""

import json
import os
import time
import uuid
from unittest import mock
from unittest.mock import patch

import pytest

from langsmith import Client
from langsmith._internal._background_thread import (
    _hybrid_tracing_thread_handle_batch,
    TracingQueueItem,
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
        auto_batch_tracing=True,
    )
    client.otel_exporter = MockOTELExporter()
    return client


class TestHybridTracing:
    """Test suite for hybrid OTEL and LangSmith tracing."""

    @patch.dict(os.environ, {"HYBRID_OTEL_AND_LS_TRACING": "true"})
    def test_hybrid_tracing_enabled_both_exports_succeed(self, client_with_otel, mock_session):
        """Test that both OTEL and LangSmith exports are called when hybrid mode is enabled."""
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
            client, client.tracing_queue, batch, use_multipart=True
        )
        
        # Verify OTEL export was called
        assert len(client.otel_exporter.export_batch_calls) == 1
        exported_runs, context_map = client.otel_exporter.export_batch_calls[0]
        assert len(exported_runs) == 1
        assert exported_runs[0].id == run_id
        
        # Verify LangSmith export was called
        mock_session.request.assert_called()
        call_args = mock_session.request.call_args
        assert call_args[0][0] == "POST"  # Method
        assert "multipart" in call_args[0][1]  # URL contains multipart

    @patch.dict(os.environ, {"HYBRID_OTEL_AND_LS_TRACING": "true"})
    def test_hybrid_tracing_otel_failure_langsmith_succeeds(self, client_with_otel, mock_session):
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
            client, client.tracing_queue, batch, use_multipart=True
        )
        
        # Verify OTEL export was attempted
        assert len(client.otel_exporter.export_batch_calls) == 1
        
        # Verify LangSmith export still worked
        mock_session.request.assert_called()

    @patch.dict(os.environ, {"HYBRID_OTEL_AND_LS_TRACING": "true"})
    def test_hybrid_tracing_langsmith_failure_otel_succeeds(self, client_with_otel, mock_session):
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
            client, client.tracing_queue, batch, use_multipart=True
        )
        
        # Verify OTEL export succeeded
        assert len(client.otel_exporter.export_batch_calls) == 1
        assert len(client.otel_exporter.exported_batches) == 1

    @patch.dict(os.environ, {"HYBRID_OTEL_AND_LS_TRACING": "false", "OTEL_ENABLED": "true"})
    def test_hybrid_tracing_disabled_normal_behavior(self, client_with_otel, mock_session):
        """Test that normal OTEL-only behavior works when hybrid mode is disabled."""
        client = client_with_otel
        
        # Create runs and wait for processing
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
        
        # Wait for background processing
        if client.tracing_queue:
            client.tracing_queue.join()
        
        # With hybrid disabled and OTEL exporter present, should only export to OTEL
        assert len(client.otel_exporter.exported_batches) > 0
        
        # LangSmith should not be called when OTEL exporter is present and hybrid is disabled
        # However, the client may still make some initial setup calls, so we check that
        # no actual run data was sent to LangSmith
        if mock_session.request.called:
            # Check that no run data was actually sent
            for call in mock_session.request.call_args_list:
                if call[0][0] == "POST" and "runs" in call[0][1]:
                    # If there are run-related POST calls, this is unexpected
                    assert False, f"Unexpected LangSmith run POST call: {call}"

    @patch.dict(os.environ, {"HYBRID_OTEL_AND_LS_TRACING": "true"})
    def test_hybrid_tracing_no_otel_exporter(self, mock_session):
        """Test hybrid mode when no OTEL exporter is configured."""
        client = Client(
            api_url="http://localhost:1984",
            api_key="123",
            session=mock_session,
            auto_batch_tracing=True,
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
        
        # Wait for background processing
        if client.tracing_queue:
            client.tracing_queue.join()
        
        # Should still export to LangSmith
        mock_session.request.assert_called()

    @patch.dict(os.environ, {"HYBRID_OTEL_AND_LS_TRACING": "true"})
    def test_hybrid_tracing_queue_task_done_called_once(self, client_with_otel, mock_session):
        """Test that queue.task_done() is called exactly once per item in hybrid mode."""
        client = client_with_otel
        
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
        
        # Call the hybrid handler
        _hybrid_tracing_thread_handle_batch(
            client, client.tracing_queue, batch, use_multipart=True
        )
        
        # Verify task_done was called exactly once for the single item
        assert len(task_done_calls) == 1

    @patch.dict(os.environ, {"HYBRID_OTEL_AND_LS_TRACING": "true"})
    def test_hybrid_tracing_multiple_items_in_batch(self, client_with_otel, mock_session):
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
            client, client.tracing_queue, batch, use_multipart=True
        )
        
        # Verify OTEL received all items
        assert len(client.otel_exporter.export_batch_calls) == 1
        exported_runs, _ = client.otel_exporter.export_batch_calls[0]
        exported_run_ids = [run.id for run in exported_runs]
        assert set(exported_run_ids) == set(expected_run_ids)
        
        # Verify LangSmith was called
        mock_session.request.assert_called()

    @patch.dict(os.environ, {})  # No environment variable set
    def test_hybrid_tracing_env_var_not_set(self, client_with_otel, mock_session):
        """Test that hybrid mode is disabled when environment variable is not set."""
        client = client_with_otel
        
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
        
        # Wait for background processing
        if client.tracing_queue:
            client.tracing_queue.join()
        
        # Should only export to OTEL (normal behavior)
        assert len(client.otel_exporter.exported_batches) > 0
        
        # LangSmith should not be called when OTEL exporter is present and hybrid is disabled
        # However, the client may still make some initial setup calls, so we check that
        # no actual run data was sent to LangSmith
        if mock_session.request.called:
            # Check that no run data was actually sent
            for call in mock_session.request.call_args_list:
                if call[0][0] == "POST" and "runs" in call[0][1]:
                    # If there are run-related POST calls, this is unexpected
                    assert False, f"Unexpected LangSmith run POST call: {call}"


class TestHybridTracingIntegration:
    """Integration tests for hybrid tracing with real Client usage."""

    @patch.dict(os.environ, {"HYBRID_OTEL_AND_LS_TRACING": "true"})
    def test_hybrid_tracing_end_to_end(self, mock_session):
        """Test hybrid tracing from Client.create_run() to final export."""
        client = Client(
            api_url="http://localhost:1984",
            api_key="123",
            session=mock_session,
            auto_batch_tracing=True,
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
        
        # Wait for background processing
        if client.tracing_queue:
            client.tracing_queue.join()
        
        # Verify both exporters received data
        assert len(client.otel_exporter.exported_batches) > 0
        mock_session.request.assert_called()
        
        # Verify all runs were processed
        all_exported_run_ids = []
        for batch in client.otel_exporter.exported_batches:
            all_exported_run_ids.extend([run.id for run in batch])
        
        assert set(all_exported_run_ids) == set(run_ids)

    def test_hybrid_tracing_graceful_cleanup(self, mock_session):
        """Test that hybrid tracing cleans up gracefully."""
        with patch.dict(os.environ, {"HYBRID_OTEL_AND_LS_TRACING": "true"}):
            client = Client(
                api_url="http://localhost:1984",
                api_key="123",
                session=mock_session,
                auto_batch_tracing=True,
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
            
            # Clean up
            if client.tracing_queue:
                client.tracing_queue.join()
            
            # Should complete without errors
            assert len(client.otel_exporter.exported_batches) > 0 