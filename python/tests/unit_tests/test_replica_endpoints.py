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
    _parse_write_replicas_from_env_var,
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

    def test_get_write_replicas_from_env_array_format(self):
        """Test _get_write_replicas_from_env with array format for multiple keys
        per URL."""
        ls_utils.get_env_var.cache_clear()
        try:
            endpoints_config = {
                "https://api.example.com": ["key1", "key2", "key3"],
                "https://replica.example.com": "single-key",
            }

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

                assert len(result) == 4  # 3 from array + 1 single

                # Check that we have 3 replicas for the first URL
                api_example_replicas = [
                    r for r in result if r["api_url"] == "https://api.example.com"
                ]
                assert len(api_example_replicas) == 3

                api_keys = [r["api_key"] for r in api_example_replicas]
                assert "key1" in api_keys
                assert "key2" in api_keys
                assert "key3" in api_keys

                # Check single key replica
                replica_example_replicas = [
                    r for r in result if r["api_url"] == "https://replica.example.com"
                ]
                assert len(replica_example_replicas) == 1
                assert replica_example_replicas[0]["api_key"] == "single-key"

        finally:
            ls_utils.get_env_var.cache_clear()

    def test_get_write_replicas_from_env_mixed_format(self):
        """Test _get_write_replicas_from_env with mixed single and array formats."""
        ls_utils.get_env_var.cache_clear()
        try:
            endpoints_config = {
                "https://single.example.com": "single-key",
                "https://multi.example.com": ["multi-key1", "multi-key2"],
                "https://another.example.com": "another-single-key",
            }

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

                assert len(result) == 4  # 1 + 2 + 1

                urls = [r["api_url"] for r in result]
                keys = [r["api_key"] for r in result]

                assert "https://single.example.com" in urls
                assert "https://multi.example.com" in urls
                assert "https://another.example.com" in urls

                assert "single-key" in keys
                assert "multi-key1" in keys
                assert "multi-key2" in keys
                assert "another-single-key" in keys

        finally:
            ls_utils.get_env_var.cache_clear()

    def test_get_write_replicas_from_env_empty_array(self):
        """Test _get_write_replicas_from_env with empty array."""
        ls_utils.get_env_var.cache_clear()
        try:
            endpoints_config = {
                "https://api.example.com": [],
                "https://valid.example.com": "valid-key",
            }

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

                # Should only have the valid replica, empty array should be ignored
                assert len(result) == 1
                assert result[0]["api_url"] == "https://valid.example.com"
                assert result[0]["api_key"] == "valid-key"

        finally:
            ls_utils.get_env_var.cache_clear()

    def test_get_write_replicas_from_env_invalid_array_elements(self):
        """Test _get_write_replicas_from_env with invalid elements in array."""
        ls_utils.get_env_var.cache_clear()
        try:
            endpoints_config = {
                "https://api.example.com": [
                    "valid-key",
                    123,
                    None,
                    "another-valid-key",
                ],
                "https://valid.example.com": "valid-key",
            }

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

                # Should have 3 replicas: 2 valid from array + 1 single
                assert len(result) == 3

                api_keys = [r["api_key"] for r in result]
                assert "valid-key" in api_keys
                assert "another-valid-key" in api_keys
                # Invalid elements (123, None) should be filtered out
                assert 123 not in api_keys
                assert None not in api_keys

        finally:
            ls_utils.get_env_var.cache_clear()

    def test_get_write_replicas_from_env_invalid_value_types(self):
        """Test _get_write_replicas_from_env with invalid value types."""
        ls_utils.get_env_var.cache_clear()
        try:
            endpoints_config = {
                "https://api.example.com": {"invalid": "dict"},
                "https://valid.example.com": "valid-key",
                "https://number.example.com": 123,
            }

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

                # Should only have the valid replica
                assert len(result) == 1
                assert result[0]["api_url"] == "https://valid.example.com"
                assert result[0]["api_key"] == "valid-key"

        finally:
            ls_utils.get_env_var.cache_clear()


class TestParseWriteReplicasFromEnvVar:
    """Test the _parse_write_replicas_from_env_var function directly."""

    def test_parse_array_format_single_url(self):
        """Test parsing array format with single URL."""
        env_var = '{"https://api.example.com": ["key1", "key2", "key3"]}'

        with patch.dict(
            os.environ, {"LANGSMITH_ENDPOINT": "", "LANGCHAIN_ENDPOINT": ""}, clear=True
        ):
            result = _parse_write_replicas_from_env_var(env_var)

        assert len(result) == 3
        assert all(r["api_url"] == "https://api.example.com" for r in result)

        keys = [r["api_key"] for r in result]
        assert "key1" in keys
        assert "key2" in keys
        assert "key3" in keys

        # All should have None for project_name and updates
        assert all(r["project_name"] is None for r in result)
        assert all(r["updates"] is None for r in result)

    def test_parse_mixed_format(self):
        """Test parsing mixed single and array formats."""
        env_var = json.dumps(
            {
                "https://single.example.com": "single-key",
                "https://multi.example.com": ["multi1", "multi2"],
            }
        )

        with patch.dict(
            os.environ, {"LANGSMITH_ENDPOINT": "", "LANGCHAIN_ENDPOINT": ""}, clear=True
        ):
            result = _parse_write_replicas_from_env_var(env_var)

        assert len(result) == 3

        # Check single format replica
        single_replicas = [
            r for r in result if r["api_url"] == "https://single.example.com"
        ]
        assert len(single_replicas) == 1
        assert single_replicas[0]["api_key"] == "single-key"

        # Check array format replicas
        multi_replicas = [
            r for r in result if r["api_url"] == "https://multi.example.com"
        ]
        assert len(multi_replicas) == 2
        multi_keys = [r["api_key"] for r in multi_replicas]
        assert "multi1" in multi_keys
        assert "multi2" in multi_keys

    def test_parse_url_trailing_slash_removal(self):
        """Test that trailing slashes are removed from URLs."""
        env_var = json.dumps(
            {
                "https://api.example.com/": ["key1", "key2"],
                "https://other.example.com/path/": "single-key",
            }
        )

        with patch.dict(
            os.environ, {"LANGSMITH_ENDPOINT": "", "LANGCHAIN_ENDPOINT": ""}, clear=True
        ):
            result = _parse_write_replicas_from_env_var(env_var)

        assert len(result) == 3

        # Check that trailing slashes are removed
        urls = [r["api_url"] for r in result]
        assert "https://api.example.com" in urls
        assert "https://other.example.com/path" in urls
        assert "https://api.example.com/" not in urls
        assert "https://other.example.com/path/" not in urls

    def test_parse_empty_array(self):
        """Test parsing with empty array."""
        env_var = json.dumps(
            {
                "https://empty.example.com": [],
                "https://valid.example.com": "valid-key",
            }
        )

        with patch.dict(
            os.environ, {"LANGSMITH_ENDPOINT": "", "LANGCHAIN_ENDPOINT": ""}, clear=True
        ):
            result = _parse_write_replicas_from_env_var(env_var)

        # Should only have the valid replica
        assert len(result) == 1
        assert result[0]["api_url"] == "https://valid.example.com"
        assert result[0]["api_key"] == "valid-key"

    def test_parse_invalid_array_elements(self):
        """Test parsing with invalid elements in array."""
        env_var = json.dumps(
            {
                "https://api.example.com": [
                    "valid1",
                    123,
                    None,
                    "valid2",
                    {"invalid": "dict"},
                ],
            }
        )

        with patch.dict(
            os.environ, {"LANGSMITH_ENDPOINT": "", "LANGCHAIN_ENDPOINT": ""}, clear=True
        ):
            result = _parse_write_replicas_from_env_var(env_var)

        # Should only have valid string elements
        assert len(result) == 2
        keys = [r["api_key"] for r in result]
        assert "valid1" in keys
        assert "valid2" in keys

    def test_parse_invalid_value_types(self):
        """Test parsing with invalid value types."""
        env_var = json.dumps(
            {
                "https://dict.example.com": {"invalid": "dict"},
                "https://number.example.com": 123,
                "https://valid.example.com": "valid-key",
            }
        )

        with patch.dict(
            os.environ, {"LANGSMITH_ENDPOINT": "", "LANGCHAIN_ENDPOINT": ""}, clear=True
        ):
            result = _parse_write_replicas_from_env_var(env_var)

        # Should only have the valid replica
        assert len(result) == 1
        assert result[0]["api_url"] == "https://valid.example.com"
        assert result[0]["api_key"] == "valid-key"

    def test_parse_empty_string(self):
        """Test parsing with empty string."""
        result = _parse_write_replicas_from_env_var("")
        assert result == []

    def test_parse_none(self):
        """Test parsing with None."""
        result = _parse_write_replicas_from_env_var(None)
        assert result == []

    def test_parse_invalid_json(self):
        """Test parsing with invalid JSON."""
        result = _parse_write_replicas_from_env_var("invalid-json")
        assert result == []


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
