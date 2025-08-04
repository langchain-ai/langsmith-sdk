"""Tests for replica endpoints functionality."""

import json
import os
import uuid
from unittest.mock import Mock, patch

import pytest

from langsmith import Client
from langsmith import utils as ls_utils
from langsmith.run_trees import (
    RunTree,
    WriteReplica,
    _ensure_write_replicas,
    _get_write_replicas_from_env,
)


class TestWriteReplicaTypes:
    """Test the WriteReplica type definitions and conversion functions."""

    def test_ensure_write_replicas_with_none(self):
        with patch.dict(os.environ, {}, clear=True):
            result = _ensure_write_replicas(None)
            assert result == []

    def test_ensure_write_replicas_with_write_replica_format(self):
        """Test _ensure_write_replicas with WriteReplica format."""
        write_replicas = [
            WriteReplica(project_name="project1", updates={"key": "value"}),
            WriteReplica(project_name="project2", updates=None),
        ]

        result = _ensure_write_replicas(write_replicas)

        assert len(result) == 2
        assert result[0]["project_name"] == "project1"
        assert result[0]["updates"] == {"key": "value"}
        assert result[0].get("api_key") is None
        assert result[0].get("api_url") is None

        assert result[1]["project_name"] == "project2"
        assert result[1]["updates"] is None

    def test_ensure_write_replicas_with_new_format(self):
        """Test _ensure_write_replicas with WriteReplica format."""
        new_replicas = [
            WriteReplica(
                api_url="https://replica1.example.com",
                api_key="key1",
                project_name="project1",
                updates={"test": "value"},
            ),
            WriteReplica(
                api_url="https://replica2.example.com",
                api_key="key2",
            ),
        ]

        result = _ensure_write_replicas(new_replicas)

        assert len(result) == 2
        assert result[0]["api_url"] == "https://replica1.example.com"
        assert result[0]["api_key"] == "key1"
        assert result[0]["project_name"] == "project1"
        assert result[0]["updates"] == {"test": "value"}

        assert result[1]["api_url"] == "https://replica2.example.com"
        assert result[1]["api_key"] == "key2"
        assert result[1].get("project_name") is None


class TestEnvironmentVariableParsing:
    """Test environment variable parsing for LANGSMITH_RUNS_ENDPOINTS."""

    def test_get_write_replicas_from_env_empty(self):
        """Test _get_write_replicas_from_env with no environment variable."""
        ls_utils.get_env_var.cache_clear()
        with patch.dict(os.environ, {}, clear=True):
            result = _get_write_replicas_from_env()
            assert result == []

    def test_get_write_replicas_from_env_valid_json(self):
        """Test _get_write_replicas_from_env with valid JSON."""
        ls_utils.get_env_var.cache_clear()
        try:
            endpoints_config = {
                "https://api.smith.langchain.com": "primary-key-123",
                "https://replica1.example.com": "replica1-key-456",
                "https://replica2.example.com": "replica2-key-789",
            }

            # Clear conflicting environment variables
            with patch.dict(
                os.environ,
                {
                    "LANGSMITH_RUNS_ENDPOINTS": json.dumps(endpoints_config),
                    "LANGSMITH_ENDPOINT": "",
                    "LANGCHAIN_ENDPOINT": "",
                },
                clear=True,
            ):
                result = _get_write_replicas_from_env()

                assert len(result) == 3
                urls = [r["api_url"] for r in result]
                keys = [r["api_key"] for r in result]

                assert "https://api.smith.langchain.com" in urls
                assert "https://replica1.example.com" in urls
                assert "https://replica2.example.com" in urls
                assert "primary-key-123" in keys
                assert "replica1-key-456" in keys
                assert "replica2-key-789" in keys
        finally:
            # Clear cache to prevent pollution
            ls_utils.get_env_var.cache_clear()

    def test_get_write_replicas_from_env_invalid_json(self):
        """Test _get_write_replicas_from_env with invalid JSON."""
        ls_utils.get_env_var.cache_clear()
        with patch.dict(
            os.environ, {"LANGSMITH_RUNS_ENDPOINTS": "invalid-json"}, clear=True
        ):
            result = _get_write_replicas_from_env()
            assert result == []

    def test_get_write_replicas_from_env_conflicting_endpoints(self):
        """Test _get_write_replicas_from_env with conflicting env vars."""
        ls_utils.get_env_var.cache_clear()
        with patch.dict(
            os.environ,
            {
                "LANGSMITH_ENDPOINT": "https://api.smith.langchain.com",
                "LANGSMITH_RUNS_ENDPOINTS": '{"https://replica.example.com": "key123"}',
            },
            clear=True,
        ):
            with pytest.raises(ls_utils.LangSmithUserError):
                _get_write_replicas_from_env()

    def test_langsmith_runs_endpoints_not_in_write_api_urls(self):
        """Test that LANGSMITH_RUNS_ENDPOINTS is not parsed into _write_api_urls."""
        ls_utils.get_env_var.cache_clear()
        try:
            endpoints_config = {
                "https://replica1.example.com": "replica1-key",
                "https://replica2.example.com": "replica2-key",
            }

            # Use a clean environment with only LANGSMITH_RUNS_ENDPOINTS set
            clean_env = {"LANGSMITH_RUNS_ENDPOINTS": json.dumps(endpoints_config)}

            with patch.dict(os.environ, clean_env, clear=True):
                client = Client(auto_batch_tracing=False)

                # _write_api_urls should only contain the default endpoint
                assert len(client._write_api_urls) == 1
                assert client.api_url == "https://api.smith.langchain.com"

                # LANGSMITH_RUNS_ENDPOINTS should be available via replicas instead
                replicas = _get_write_replicas_from_env()
                assert len(replicas) == 2
                replica_urls = [r["api_url"] for r in replicas]
                assert "https://replica1.example.com" in replica_urls
                assert "https://replica2.example.com" in replica_urls
        finally:
            # Clear cache to prevent pollution
            ls_utils.get_env_var.cache_clear()


class TestClientReplicaMethods:
    """Test Client methods with replica support."""

    def test_create_run_accepts_api_key_and_url_parameters(self):
        """Test that create_run accepts api_key and api_url parameters without error."""
        client = Client(auto_batch_tracing=False)

        # Mock the session to avoid actual HTTP requests
        with patch.object(client.session, "request") as mock_request:
            mock_request.return_value.status_code = 200
            mock_request.return_value.text = ""

            # This should not raise an error
            client.create_run(
                name="test_run",
                inputs={"input": "test"},
                run_type="chain",
                api_key="custom-key",
                api_url="https://custom.example.com",
            )

    def test_update_run_accepts_api_key_and_url_parameters(self):
        """Test that update_run accepts api_key and api_url parameters without error."""
        client = Client(auto_batch_tracing=False)
        run_id = uuid.uuid4()

        # Mock the session to avoid actual HTTP requests
        with patch.object(client.session, "request") as mock_request:
            mock_request.return_value.status_code = 200
            mock_request.return_value.text = ""

            # This should not raise an error
            client.update_run(
                run_id=run_id,
                outputs={"output": "test"},
                api_key="custom-key",
                api_url="https://custom.example.com",
            )


class TestRunTreeReplicas:
    """Test RunTree with replica functionality."""

    def test_run_tree_with_write_replicas(self):
        """Test RunTree with WriteReplica format."""
        client = Mock()

        run_tree = RunTree(
            name="test_run",
            inputs={"input": "test"},
            client=client,
            project_name="test-project",
            replicas=[
                WriteReplica(project_name="replica-project", updates={"key": "value"})
            ],
        )

        run_tree.post()

        # Verify client.create_run was called with replica parameters
        assert client.create_run.call_count == 1
        call_args = client.create_run.call_args
        assert call_args[1]["api_key"] is None
        assert call_args[1]["api_url"] is None

    def test_run_tree_with_new_replicas(self):
        """Test RunTree with WriteReplica format."""
        client = Mock()

        replicas = [
            WriteReplica(
                api_url="https://replica1.example.com",
                api_key="replica1-key",
                project_name="replica1-project",
            ),
            WriteReplica(
                api_url="https://replica2.example.com",
                api_key="replica2-key",
                project_name="replica2-project",
            ),
        ]

        run_tree = RunTree(
            name="test_run",
            inputs={"input": "test"},
            client=client,
            project_name="test-project",
            replicas=replicas,
        )

        run_tree.post()

        # Verify client.create_run was called twice with different replica parameters
        assert client.create_run.call_count == 2

        calls = client.create_run.call_args_list
        assert calls[0][1]["api_key"] == "replica1-key"
        assert calls[0][1]["api_url"] == "https://replica1.example.com"
        assert calls[1][1]["api_key"] == "replica2-key"
        assert calls[1][1]["api_url"] == "https://replica2.example.com"

    def test_run_tree_patch_with_replicas(self):
        """Test RunTree patch method with replicas."""
        client = Mock()

        replicas = [
            WriteReplica(
                api_url="https://replica.example.com",
                api_key="replica-key",
                project_name="replica-project",
                updates={"extra_field": "extra_value"},
            )
        ]

        run_tree = RunTree(
            name="test_run",
            inputs={"input": "test"},
            client=client,
            project_name="test-project",
            replicas=replicas,
        )

        run_tree.patch()

        # Verify client.update_run was called with replica parameters
        assert client.update_run.call_count == 1
        call_args = client.update_run.call_args
        assert call_args[1]["api_key"] == "replica-key"
        assert call_args[1]["api_url"] == "https://replica.example.com"


class TestBaggageReplicaParsing:
    """Test baggage header parsing for replicas."""

    def test_baggage_parsing_tuple_format(self):
        """Test that baggage headers with tuple replica format are parsed correctly."""
        import json
        import urllib.parse

        from langsmith.run_trees import _Baggage

        # tuple format: [project_name, updates]
        tuple_replicas = [
            ["replica-project-1", {"environment": "staging"}],
            ["replica-project-2", None],
        ]

        baggage_value = (
            f"langsmith-replicas={urllib.parse.quote(json.dumps(tuple_replicas))}"
        )
        baggage = _Baggage.from_header(baggage_value)

        assert len(baggage.replicas) == 2
        # Legacy tuple format should be converted to WriteReplica dict format
        assert baggage.replicas[0]["project_name"] == "replica-project-1"
        assert baggage.replicas[0]["updates"] == {"environment": "staging"}
        assert baggage.replicas[0].get("api_url") is None
        assert baggage.replicas[0].get("api_key") is None

        assert baggage.replicas[1]["project_name"] == "replica-project-2"
        assert baggage.replicas[1]["updates"] is None

    def test_baggage_parsing_new_format(self):
        """Test baggage headers with WriteReplica format are parsed
        correctly."""
        import json
        import urllib.parse

        from langsmith.run_trees import _Baggage

        #  WriteReplica format
        new_replicas = [
            {
                "api_url": "https://replica1.example.com",
                "api_key": "replica1-key",
                "project_name": "replica1-project",
                "updates": {"environment": "production"},
            },
            {
                "api_url": "https://replica2.example.com",
                "api_key": "replica2-key",
                "project_name": "replica2-project",
            },
        ]

        baggage_value = (
            f"langsmith-replicas={urllib.parse.quote(json.dumps(new_replicas))}"
        )
        baggage = _Baggage.from_header(baggage_value)

        assert len(baggage.replicas) == 2
        assert baggage.replicas[0]["api_url"] == "https://replica1.example.com"
        assert baggage.replicas[0]["api_key"] == "replica1-key"
        assert baggage.replicas[0]["project_name"] == "replica1-project"
        assert baggage.replicas[0]["updates"] == {"environment": "production"}

        assert baggage.replicas[1]["api_url"] == "https://replica2.example.com"
        assert baggage.replicas[1]["api_key"] == "replica2-key"
        assert baggage.replicas[1]["project_name"] == "replica2-project"

    def test_baggage_parsing_mixed_format(self):
        """Test that baggage headers with mixed replica formats are parsed correctly."""
        import json
        import urllib.parse

        from langsmith.run_trees import _Baggage

        # Mixed format: both tuple and new
        mixed_replicas = [
            ["tuple-project", {"tuple": "true"}],  # tuple format
            {
                "api_url": "https://new.example.com",
                "api_key": "new-key",
                "project_name": "new-project",
            },  # New format
        ]

        baggage_value = (
            f"langsmith-replicas={urllib.parse.quote(json.dumps(mixed_replicas))}"
        )
        baggage = _Baggage.from_header(baggage_value)

        assert len(baggage.replicas) == 2
        # First should be converted from tuple format to WriteReplica dict format
        assert baggage.replicas[0]["project_name"] == "tuple-project"
        assert baggage.replicas[0]["updates"] == {"tuple": "true"}
        assert baggage.replicas[0].get("api_url") is None
        assert baggage.replicas[0].get("api_key") is None
        # Second should be new dict format
        assert baggage.replicas[1]["api_url"] == "https://new.example.com"
        assert baggage.replicas[1]["api_key"] == "new-key"
        assert baggage.replicas[1]["project_name"] == "new-project"


class TestTracingContextReplicas:
    """Test tracing_context function with replica support."""

    def test_tracing_context_with_new_replica_format(self):
        """Test that tracing_context accepts the WriteReplica format."""
        from langsmith.run_helpers import tracing_context
        from langsmith.run_trees import WriteReplica

        replicas = [
            WriteReplica(
                api_url="https://replica.example.com",
                api_key="replica-key",
                project_name="replica-project",
                updates={"environment": "test"},
            )
        ]

        # This should not raise a type error
        with tracing_context(replicas=replicas):
            pass  # Just testing that the context manager works

    def test_tracing_context_with_project_replica_format(self):
        """Test that tracing_context accepts replica format."""
        from langsmith.run_helpers import tracing_context
        from langsmith.run_trees import WriteReplica

        replicas = [
            WriteReplica(project_name="project1", updates={"tuple": True}),
            WriteReplica(project_name="another-project", updates=None),
        ]

        # This should not raise a type error
        with tracing_context(replicas=replicas):
            pass  # Just testing that the context manager works

    def test_tracing_context_with_mixed_replica_types(self):
        """Test that tracing_context accepts different types of replicas."""
        from langsmith.run_helpers import tracing_context
        from langsmith.run_trees import WriteReplica

        replicas = [
            # project replica
            WriteReplica(project_name="project-replica", updates={"env": "test"}),
            WriteReplica(
                api_url="https://new.example.com",
                api_key="new-key",
                project_name="new-project",
            ),  # API replica
        ]

        # This should not raise a type error
        with tracing_context(replicas=replicas):
            pass  # Just testing that the context manager works
