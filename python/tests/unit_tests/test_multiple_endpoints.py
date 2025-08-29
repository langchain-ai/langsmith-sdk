"""
Unit test that mocks LANGSMITH_RUNS_ENDPOINTS and verifies that multiple requests
are made to the respective endpoints for the same run.

This test covers:
1. Direct client.create_run() calls with api_key/api_url parameters
2. RunTree.post() with replicas that have api_key/api_url
3. Background threading mode with different endpoints
4. Both multipart and non-multipart modes
"""

import json
import uuid
from unittest.mock import Mock, patch

import pytest

from langsmith import Client
from langsmith._internal._background_thread import (
    TracingQueueItem,
    _tracing_thread_handle_batch,
)
from langsmith._internal._operations import serialize_run_dict
from langsmith.run_trees import RunTree, WriteReplica


class TestLangsmithRunsEndpoints:
    """Test LANGSMITH_RUNS_ENDPOINTS functionality with multiple endpoints."""

    def setup_method(self):
        """Set up test data."""
        self.run_data = {
            "id": uuid.uuid4(),
            "trace_id": uuid.uuid4(),
            "dotted_order": "20231201T120000000000Z" + str(uuid.uuid4()),
            "session_name": "test-project",
            "name": "test_run",
            "inputs": {"input": "test"},
            "run_type": "llm",
        }

        self.endpoints_config = [
            {"api_url": "https://api1.example.com", "api_key": "key1"},
            {"api_url": "https://api2.example.com", "api_key": "key2"},
            {"api_url": "https://api3.example.com", "api_key": "key3"},
        ]

    def test_client_create_run_with_multiple_write_api_urls(self):
        """Test that client.create_run() sends to multiple endpoints when using
        _write_api_urls.
        """
        # Create client with multiple write API URLs
        api_urls = {
            "https://api1.example.com": "key1",
            "https://api2.example.com": "key2",
            "https://api3.example.com": "key3",
        }

        client = Client(api_urls=api_urls, auto_batch_tracing=False)

        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = {}
            mock_request.return_value = mock_response

            # Call create_run without specific api_key/api_url
            # (should use all endpoints)
            client.create_run(**self.run_data)

            # Verify requests were made to all 3 endpoints
            assert mock_request.call_count == 3

            # Extract the URLs from the calls
            called_urls = []
            for call_args in mock_request.call_args_list:
                # The URL is the second positional argument:
                # session.request(method, url, ...)
                full_url = call_args[0][1]  # call_args[0] is args tuple, [1] is the URL
                base_url = full_url.replace("/runs", "")
                called_urls.append(base_url)

            # Verify all endpoints were called
            assert "https://api1.example.com" in called_urls
            assert "https://api2.example.com" in called_urls
            assert "https://api3.example.com" in called_urls

            # Verify correct API keys were used
            for i, call_args in enumerate(mock_request.call_args_list):
                # Headers are in kwargs
                headers = call_args[1].get("headers", {})
                api_key = headers.get("x-api-key")  # Note: lowercase header key
                assert api_key in ["key1", "key2", "key3"]

    def test_client_create_run_with_specific_endpoint(self):
        """Test that client.create_run() with specific api_key/api_url only sends
        to that endpoint.
        """
        api_urls = {
            "https://api1.example.com": "key1",
            "https://api2.example.com": "key2",
        }

        client = Client(api_urls=api_urls, auto_batch_tracing=False)

        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = {}
            mock_request.return_value = mock_response

            # Call create_run with specific endpoint
            client.create_run(
                **self.run_data,
                api_key="custom_key",
                api_url="https://custom.example.com",
            )

            # Verify only one request was made to the specific endpoint
            assert mock_request.call_count == 1
            call_args = mock_request.call_args
            full_url = call_args[0][1]  # Second positional argument is the URL
            assert full_url == "https://custom.example.com/runs"

            headers = call_args[1].get("headers", {})
            # Note: lowercase header key
            assert headers.get("x-api-key") == "custom_key"

    def test_run_tree_with_replicas(self):
        """Test RunTree.post() with replicas containing api_key/api_url."""
        client = Mock()

        # Create RunTree with replicas that have different endpoints
        replicas = [
            WriteReplica(
                api_url="https://replica1.example.com",
                api_key="replica_key1",
                project_name="project1",
            ),
            WriteReplica(
                api_url="https://replica2.example.com",
                api_key="replica_key2",
                project_name="project2",
            ),
        ]

        run_tree = RunTree(
            name="test_run",
            inputs={"input": "test"},
            client=client,
            project_name="main-project",
            replicas=replicas,
        )

        # Call post()
        run_tree.post()

        # Verify client.create_run was called once for each replica
        assert client.create_run.call_count == 2

        # Verify the calls had correct api_key/api_url parameters
        calls = client.create_run.call_args_list

        # First replica call
        first_call = calls[0]
        assert first_call.kwargs["api_key"] == "replica_key1"
        assert first_call.kwargs["api_url"] == "https://replica1.example.com"
        assert first_call.kwargs["session_name"] == "project1"

        # Second replica call
        second_call = calls[1]
        assert second_call.kwargs["api_key"] == "replica_key2"
        assert second_call.kwargs["api_url"] == "https://replica2.example.com"
        assert second_call.kwargs["session_name"] == "project2"

    def test_background_threading_with_different_endpoints(self):
        """Test background threading correctly groups and sends to different
        endpoints.
        """
        client = Mock()
        tracing_queue = Mock()

        # Mock the client methods
        client._multipart_ingest_ops = Mock()
        client._batch_ingest_run_ops = Mock()

        # Create batch with items for different endpoints
        serialized_op1 = serialize_run_dict(
            "post", {**self.run_data, "id": uuid.uuid4()}
        )
        serialized_op2 = serialize_run_dict(
            "post", {**self.run_data, "id": uuid.uuid4()}
        )
        serialized_op3 = serialize_run_dict(
            "post", {**self.run_data, "id": uuid.uuid4()}
        )

        batch = [
            TracingQueueItem(
                "priority1",
                serialized_op1,
                api_key="key1",
                api_url="https://api1.com",
            ),
            # Same endpoint
            TracingQueueItem(
                "priority2",
                serialized_op2,
                api_key="key1",
                api_url="https://api1.com",
            ),
            # Different endpoint
            TracingQueueItem(
                "priority3",
                serialized_op3,
                api_key="key2",
                api_url="https://api2.com",
            ),
        ]

        # Test multipart mode
        _tracing_thread_handle_batch(client, tracing_queue, batch, use_multipart=True)

        # Verify _multipart_ingest_ops was called twice (once per unique endpoint)
        assert client._multipart_ingest_ops.call_count == 2

        # Verify the calls had correct endpoint parameters
        calls = client._multipart_ingest_ops.call_args_list
        endpoint_calls = [
            (call.kwargs.get("api_url"), call.kwargs.get("api_key")) for call in calls
        ]

        assert ("https://api1.com", "key1") in endpoint_calls
        assert ("https://api2.com", "key2") in endpoint_calls

        # Verify the first endpoint got 2 operations, second got 1
        for call in calls:
            ops = call.args[0]  # First positional argument is the operations list
            if call.kwargs.get("api_url") == "https://api1.com":
                assert len(ops) == 2  # Two operations for api1
            else:
                assert len(ops) == 1  # One operation for api2

    def test_background_threading_non_multipart_mode(self):
        """Test background threading in non-multipart mode with different endpoints."""
        client = Mock()
        tracing_queue = Mock()

        # Mock the client methods
        client._batch_ingest_run_ops = Mock()

        # Create batch with items for different endpoints
        serialized_op1 = serialize_run_dict(
            "post", {**self.run_data, "id": uuid.uuid4()}
        )
        serialized_op2 = serialize_run_dict(
            "post", {**self.run_data, "id": uuid.uuid4()}
        )

        batch = [
            TracingQueueItem(
                "priority1",
                serialized_op1,
                api_key="key1",
                api_url="https://api1.com",
            ),
            TracingQueueItem(
                "priority2",
                serialized_op2,
                api_key="key2",
                api_url="https://api2.com",
            ),
        ]

        # Test non-multipart mode
        _tracing_thread_handle_batch(client, tracing_queue, batch, use_multipart=False)

        # Verify _batch_ingest_run_ops was called twice (once per endpoint)
        assert client._batch_ingest_run_ops.call_count == 2

        # Verify the calls had correct endpoint parameters
        calls = client._batch_ingest_run_ops.call_args_list
        endpoint_calls = [
            (call.kwargs.get("api_url"), call.kwargs.get("api_key")) for call in calls
        ]

        assert ("https://api1.com", "key1") in endpoint_calls
        assert ("https://api2.com", "key2") in endpoint_calls

    def test_langsmith_runs_endpoints_env_var_integration(self):
        """Test integration with LANGSMITH_RUNS_ENDPOINTS environment variable."""
        from langsmith.run_trees import _parse_write_replicas_from_env_var

        # Test the parsing function directly
        env_var = json.dumps(self.endpoints_config)
        replicas = _parse_write_replicas_from_env_var(env_var)

        assert len(replicas) == 3
        assert replicas[0]["api_url"] == "https://api1.example.com"
        assert replicas[0]["api_key"] == "key1"
        assert replicas[1]["api_url"] == "https://api2.example.com"
        assert replicas[1]["api_key"] == "key2"
        assert replicas[2]["api_url"] == "https://api3.example.com"
        assert replicas[2]["api_key"] == "key3"

    def test_mixed_endpoints_and_default_fallback(self):
        """Test batch with mixed endpoints and items that should use default."""
        client = Mock()
        tracing_queue = Mock()
        client._multipart_ingest_ops = Mock()

        # Create batch with mixed endpoint specifications
        serialized_op1 = serialize_run_dict(
            "post", {**self.run_data, "id": uuid.uuid4()}
        )
        serialized_op2 = serialize_run_dict(
            "post", {**self.run_data, "id": uuid.uuid4()}
        )
        serialized_op3 = serialize_run_dict(
            "post", {**self.run_data, "id": uuid.uuid4()}
        )

        batch = [
            TracingQueueItem(
                "priority1",
                serialized_op1,
                api_key="key1",
                api_url="https://api1.com",
            ),
            # Should use default
            TracingQueueItem(
                "priority2",
                serialized_op2,
                api_key=None,
                api_url=None,
            ),
            TracingQueueItem(
                "priority3",
                serialized_op3,
                api_key="key2",
                api_url="https://api2.com",
            ),
        ]

        _tracing_thread_handle_batch(client, tracing_queue, batch, use_multipart=True)

        # Should have 3 calls: one for each unique endpoint combination
        assert client._multipart_ingest_ops.call_count == 3

        # Verify endpoint combinations
        calls = client._multipart_ingest_ops.call_args_list
        endpoint_calls = [
            (call.kwargs.get("api_url"), call.kwargs.get("api_key")) for call in calls
        ]

        assert ("https://api1.com", "key1") in endpoint_calls
        assert ("https://api2.com", "key2") in endpoint_calls
        assert (None, None) in endpoint_calls  # Default endpoint


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
