"""Tests for replica endpoints functionality."""

import json
import os
import uuid
from unittest.mock import Mock, patch

import pytest

from langsmith import Client
from langsmith import utils as ls_utils
from langsmith.run_trees import (
    ApiKeyAuth,
    RunTree,
    ServiceAuth,
    WriteReplica,
    _ensure_write_replicas,
    _extract_replica_auth,
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
        assert result[0].get("auth") is None
        assert result[0].get("api_url") is None

        assert result[1]["project_name"] == "project2"
        assert result[1]["updates"] is None

    def test_ensure_write_replicas_with_new_format(self):
        """Test _ensure_write_replicas with WriteReplica format."""
        new_replicas = [
            WriteReplica(
                api_url="https://replica1.example.com",
                auth=ApiKeyAuth(api_key="key1"),
                project_name="project1",
                updates={"test": "value"},
            ),
            WriteReplica(
                api_url="https://replica2.example.com",
                auth=ApiKeyAuth(api_key="key2"),
            ),
        ]

        result = _ensure_write_replicas(new_replicas)

        assert len(result) == 2
        assert result[0]["api_url"] == "https://replica1.example.com"
        assert result[0]["auth"]["api_key"] == "key1"
        assert result[0]["project_name"] == "project1"
        assert result[0]["updates"] == {"test": "value"}

        assert result[1]["api_url"] == "https://replica2.example.com"
        assert result[1]["auth"]["api_key"] == "key2"
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
                keys = [r["auth"]["api_key"] for r in result]

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

    def test_get_write_replicas_from_env_new_array_format(self):
        """Test _get_write_replicas_from_env with new array format."""
        ls_utils.get_env_var.cache_clear()
        try:
            endpoints_config = [
                {"api_url": "https://api.example.com", "api_key": "key1"},
                {"api_url": "https://api.example.com", "api_key": "key2"},
                {"api_url": "https://api.example.com", "api_key": "key3"},
                {"api_url": "https://replica.example.com", "api_key": "single-key"},
            ]

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

                assert len(result) == 4

                # Check that we have 3 replicas for the first URL
                api_example_replicas = [
                    r for r in result if r["api_url"] == "https://api.example.com"
                ]
                assert len(api_example_replicas) == 3

                api_keys = [r["auth"]["api_key"] for r in api_example_replicas]
                assert "key1" in api_keys
                assert "key2" in api_keys
                assert "key3" in api_keys

                # Check single key replica
                replica_example_replicas = [
                    r for r in result if r["api_url"] == "https://replica.example.com"
                ]
                assert len(replica_example_replicas) == 1
                assert replica_example_replicas[0]["auth"]["api_key"] == "single-key"

        finally:
            ls_utils.get_env_var.cache_clear()

    def test_get_write_replicas_from_env_object_format(self):
        """Test _get_write_replicas_from_env with object format."""
        ls_utils.get_env_var.cache_clear()
        try:
            endpoints_config = {
                "https://single.example.com": "single-key",
                "https://another.example.com": "another-key",
                "https://third.example.com": "third-key",
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

                assert len(result) == 3

                urls = [r["api_url"] for r in result]
                keys = [r["auth"]["api_key"] for r in result]

                assert "https://single.example.com" in urls
                assert "https://another.example.com" in urls
                assert "https://third.example.com" in urls

                assert "single-key" in keys
                assert "another-key" in keys
                assert "third-key" in keys

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
                assert result[0]["auth"]["api_key"] == "valid-key"

        finally:
            ls_utils.get_env_var.cache_clear()

    def test_get_write_replicas_from_env_invalid_object_values(self):
        """Test _get_write_replicas_from_env with invalid values in object format."""
        ls_utils.get_env_var.cache_clear()
        try:
            endpoints_config = {
                "https://api.example.com": 123,  # Invalid: should be string
                "https://valid.example.com": "valid-key",
                "https://another.example.com": None,  # Invalid: should be string
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

                # Should have 1 replica: only the valid one
                assert len(result) == 1

                assert result[0]["api_url"] == "https://valid.example.com"
                assert result[0]["auth"]["api_key"] == "valid-key"

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
                assert result[0]["auth"]["api_key"] == "valid-key"

        finally:
            ls_utils.get_env_var.cache_clear()


class TestParseWriteReplicasFromEnvVar:
    """Test the _parse_write_replicas_from_env_var function directly."""

    def test_parse_new_array_format(self):
        """Test parsing new array format."""
        env_var = json.dumps(
            [
                {"api_url": "https://api.example.com", "api_key": "key1"},
                {"api_url": "https://api.example.com", "api_key": "key2"},
                {"api_url": "https://api.example.com", "api_key": "key3"},
            ]
        )

        with patch.dict(
            os.environ, {"LANGSMITH_ENDPOINT": "", "LANGCHAIN_ENDPOINT": ""}, clear=True
        ):
            result = _parse_write_replicas_from_env_var(env_var)

        assert len(result) == 3
        assert all(r["api_url"] == "https://api.example.com" for r in result)

        keys = [r["auth"]["api_key"] for r in result]
        assert "key1" in keys
        assert "key2" in keys
        assert "key3" in keys

        # All should have None for project_name and updates
        assert all(r["project_name"] is None for r in result)
        assert all(r["updates"] is None for r in result)

    def test_parse_object_format(self):
        """Test parsing object format."""
        env_var = json.dumps(
            {
                "https://single.example.com": "single-key",
                "https://another.example.com": "another-key",
            }
        )

        with patch.dict(
            os.environ, {"LANGSMITH_ENDPOINT": "", "LANGCHAIN_ENDPOINT": ""}, clear=True
        ):
            result = _parse_write_replicas_from_env_var(env_var)

        assert len(result) == 2

        # Check replicas
        urls = [r["api_url"] for r in result]
        keys = [r["auth"]["api_key"] for r in result]

        assert "https://single.example.com" in urls
        assert "https://another.example.com" in urls
        assert "single-key" in keys
        assert "another-key" in keys

    def test_parse_url_trailing_slash_removal(self):
        """Test that trailing slashes are removed from URLs."""
        # Test with new array format
        env_var = json.dumps(
            [
                {"api_url": "https://api.example.com/", "api_key": "key1"},
                {"api_url": "https://other.example.com/path/", "api_key": "key2"},
            ]
        )

        with patch.dict(
            os.environ, {"LANGSMITH_ENDPOINT": "", "LANGCHAIN_ENDPOINT": ""}, clear=True
        ):
            result = _parse_write_replicas_from_env_var(env_var)

        assert len(result) == 2

        # Check that trailing slashes are removed
        urls = [r["api_url"] for r in result]
        assert "https://api.example.com" in urls
        assert "https://other.example.com/path" in urls
        assert "https://api.example.com/" not in urls
        assert "https://other.example.com/path/" not in urls

        # Test with object format
        env_var2 = json.dumps(
            {
                "https://object.example.com/": "object-key",
            }
        )

        with patch.dict(
            os.environ, {"LANGSMITH_ENDPOINT": "", "LANGCHAIN_ENDPOINT": ""}, clear=True
        ):
            result2 = _parse_write_replicas_from_env_var(env_var2)

        assert len(result2) == 1
        assert result2[0]["api_url"] == "https://object.example.com"

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
        assert result[0]["auth"]["api_key"] == "valid-key"

    def test_parse_invalid_object_values(self):
        """Test parsing with invalid values in object format."""
        env_var = json.dumps(
            {
                "https://api.example.com": ["invalid", "array"],
                "https://valid.example.com": "valid-key",
                "https://number.example.com": 123,  # Invalid: should be string
                "https://dict.example.com": {"invalid": "dict"},
            }
        )

        with patch.dict(
            os.environ, {"LANGSMITH_ENDPOINT": "", "LANGCHAIN_ENDPOINT": ""}, clear=True
        ):
            result = _parse_write_replicas_from_env_var(env_var)

        # Should only have the valid replica
        assert len(result) == 1
        assert result[0]["api_url"] == "https://valid.example.com"
        assert result[0]["auth"]["api_key"] == "valid-key"

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
        assert result[0]["auth"]["api_key"] == "valid-key"

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

    def test_parse_new_array_format_invalid_items(self):
        """Test parsing new array format with invalid items."""
        env_var = json.dumps(
            [
                {"api_url": "https://valid.example.com", "api_key": "valid-key"},
                "invalid-string-item",
                {"api_url": "https://missing-key.example.com"},  # missing api_key
                {"api_key": "missing-url-key"},  # missing api_url
                {"api_url": 123, "api_key": "invalid-url-type"},  # invalid api_url type
                {"api_url": "https://invalid-key-type.example.com", "api_key": 456},
            ]
        )

        with patch.dict(
            os.environ, {"LANGSMITH_ENDPOINT": "", "LANGCHAIN_ENDPOINT": ""}, clear=True
        ):
            result = _parse_write_replicas_from_env_var(env_var)

        # Should only have the valid replica
        assert len(result) == 1
        assert result[0]["api_url"] == "https://valid.example.com"
        assert result[0]["auth"]["api_key"] == "valid-key"

    def test_parse_invalid_root_type(self):
        """Test parsing with invalid root type (not list or dict)."""
        env_var = json.dumps("invalid-string-root")

        with patch.dict(
            os.environ, {"LANGSMITH_ENDPOINT": "", "LANGCHAIN_ENDPOINT": ""}, clear=True
        ):
            result = _parse_write_replicas_from_env_var(env_var)

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


class TestReplicaAuthExtraction:
    """Test replica auth extraction for legacy and current formats."""

    def test_extract_replica_auth_with_top_level_api_key(self):
        replica = WriteReplica(
            api_url="https://replica.example.com",
            api_key="legacy-key",
            project_name="replica-project",
        )

        api_url, api_key, service_key, tenant_id = _extract_replica_auth(replica)
        assert api_url == "https://replica.example.com"
        assert api_key == "legacy-key"
        assert service_key is None
        assert tenant_id is None

    def test_extract_replica_auth_with_auth_api_key(self):
        replica = WriteReplica(
            api_url="https://replica.example.com",
            auth=ApiKeyAuth(api_key="auth-key"),
        )

        api_url, api_key, service_key, tenant_id = _extract_replica_auth(replica)
        assert api_url == "https://replica.example.com"
        assert api_key == "auth-key"
        assert service_key is None
        assert tenant_id is None

    def test_extract_replica_auth_with_service_auth(self):
        replica = WriteReplica(
            api_url="https://replica.example.com",
            auth=ServiceAuth(service_key="svc-key", tenant_id="tenant-123"),
        )

        api_url, api_key, service_key, tenant_id = _extract_replica_auth(replica)
        assert api_url == "https://replica.example.com"
        assert api_key is None
        assert service_key == "svc-key"
        assert tenant_id == "tenant-123"


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
        assert call_args[1]["service_key"] is None
        assert call_args[1]["tenant_id"] is None

    def test_run_tree_with_new_replicas(self):
        """Test RunTree with WriteReplica format."""
        client = Mock()

        replicas = [
            WriteReplica(
                api_url="https://replica1.example.com",
                auth=ApiKeyAuth(api_key="replica1-key"),
                project_name="replica1-project",
            ),
            WriteReplica(
                api_url="https://replica2.example.com",
                auth=ApiKeyAuth(api_key="replica2-key"),
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

    def test_run_tree_with_service_auth_replicas(self):
        """Test RunTree with ServiceAuth replicas."""
        client = Mock()

        replicas = [
            WriteReplica(
                api_url="https://internal.example.com",
                auth=ServiceAuth(service_key="jwt-token-123", tenant_id="tenant-abc"),
                project_name="internal-project",
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

        # Verify client.create_run was called with service auth parameters
        assert client.create_run.call_count == 1
        call_args = client.create_run.call_args
        assert call_args[1]["api_key"] is None
        assert call_args[1]["api_url"] == "https://internal.example.com"
        assert call_args[1]["service_key"] == "jwt-token-123"
        assert call_args[1]["tenant_id"] == "tenant-abc"

    def test_run_tree_patch_with_replicas(self):
        """Test RunTree patch method with replicas."""
        client = Mock()

        replicas = [
            WriteReplica(
                api_url="https://replica.example.com",
                auth=ApiKeyAuth(api_key="replica-key"),
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

        # tuple format: (project_name, updates)
        tuple_replicas = [
            ("replica-project-1", {"environment": "staging"}),
            ("replica-project-2", None),
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
        assert baggage.replicas[0].get("auth") is None

        assert baggage.replicas[1]["project_name"] == "replica-project-2"
        assert baggage.replicas[1]["updates"] is None

    def test_baggage_parsing_new_format(self):
        """Test baggage headers with WriteReplica format are parsed correctly."""
        import json
        import urllib.parse

        from langsmith.run_trees import _Baggage

        #  WriteReplica format with auth (auth should be ignored for safety)
        new_replicas = [
            {
                "api_url": "https://replica1.example.com",
                "auth": {"api_key": "replica1-key"},
                "project_name": "replica1-project",
                "updates": {"environment": "production"},
            },
            {
                "api_url": "https://replica2.example.com",
                "auth": {"api_key": "replica2-key"},
                "project_name": "replica2-project",
            },
        ]

        baggage_value = (
            f"langsmith-replicas={urllib.parse.quote(json.dumps(new_replicas))}"
        )
        baggage = _Baggage.from_header(baggage_value)

        assert len(baggage.replicas) == 2
        assert baggage.replicas[0]["project_name"] == "replica1-project"
        assert baggage.replicas[0]["updates"] == {"environment": "production"}
        assert baggage.replicas[0].get("api_url") is None
        assert baggage.replicas[0].get("auth") is None

        assert "api_url" not in baggage.replicas[1]
        assert "api_key" not in baggage.replicas[1]
        assert baggage.replicas[1]["project_name"] == "replica2-project"

    def test_baggage_parsing_mixed_format(self):
        """Test that baggage headers with mixed replica formats are parsed correctly."""
        import json
        import urllib.parse

        from langsmith.run_trees import _Baggage

        # Mixed format: both tuple and new
        mixed_replicas = [
            ("tuple-project", {"tuple": "true"}),  # tuple format
            {
                "api_url": "https://new.example.com",
                "auth": {"api_key": "new-key"},
                "project_name": "new-project",
            },  # New format with auth
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
        assert "api_url" not in baggage.replicas[1]
        assert "api_key" not in baggage.replicas[1]
        assert baggage.replicas[1]["project_name"] == "new-project"
        assert baggage.replicas[1].get("api_url") is None
        assert baggage.replicas[1].get("auth") is None

    def test_baggage_parsing_drops_replica_without_project_name(self):
        """Replicas without project_name should be ignored from baggage."""
        import json
        import urllib.parse

        from langsmith.run_trees import _Baggage

        new_replicas = [
            {"api_url": "https://attacker.example.com"},
            {"api_url": "https://replica.example.com", "project_name": "safe-project"},
        ]
        baggage_value = (
            f"langsmith-replicas={urllib.parse.quote(json.dumps(new_replicas))}"
        )
        baggage = _Baggage.from_header(baggage_value)
        assert len(baggage.replicas) == 1
        assert baggage.replicas[0]["project_name"] == "safe-project"
        assert baggage.replicas[0].get("api_url") is None
        assert baggage.replicas[0].get("auth") is None

    def test_run_tree_to_headers_does_not_propagate_replica_auth(self):
        """Replica auth should not be propagated via W3C baggage headers."""
        from langsmith.run_trees import _Baggage

        client = Mock()
        run_tree = RunTree(
            name="test_run",
            inputs={"input": "test"},
            client=client,
            project_name="test-project",
            replicas=[
                WriteReplica(
                    api_url="https://replica.example.com",
                    auth=ApiKeyAuth(api_key="replica-key"),
                    project_name="replica-project",
                    updates={"env": "test"},
                ),
                WriteReplica(
                    api_url="https://internal.example.com",
                    auth=ServiceAuth(
                        service_key="jwt-token-123", tenant_id="tenant-abc"
                    ),
                    project_name="internal-project",
                ),
            ],
        )

        headers = run_tree.to_headers()
        baggage = _Baggage.from_headers(headers)
        assert baggage.replicas == []

    def test_from_headers_does_not_accept_replica_endpoint_or_auth(self):
        """Inbound baggage must not be allowed to redirect writes or inject auth."""
        import json
        import urllib.parse
        import uuid

        from langsmith.run_trees import RunTree

        replicas = [
            {
                "api_url": "https://attacker.example.com",
                "auth": {"api_key": "attacker-key"},
                "project_name": "safe-project",
            }
        ]
        baggage = f"langsmith-replicas={urllib.parse.quote(json.dumps(replicas))}"
        headers = {
            "baggage": baggage,
            "langsmith-trace": "20240101T000000000000Z" + str(uuid.uuid4()),
        }

        rt = RunTree.from_headers(headers)
        assert rt.replicas
        assert rt.replicas[0]["project_name"] == "safe-project"
        assert rt.replicas[0].get("api_url") is None
        assert rt.replicas[0].get("auth") is None


class TestServiceAuthBatching:
    def test_multipart_ingest_uses_service_auth_headers(self):
        """ServiceAuth should flow through multipart batching headers."""
        import uuid
        from unittest.mock import patch

        from langsmith._internal._operations import serialize_run_dict

        client = Client(
            api_url="https://default.example.com",
            api_key="default-key",
            # Avoid any network calls for /info during test setup.
            info={"version": "0.0.0"},
        )

        run = {
            "id": uuid.uuid4(),
            "trace_id": uuid.uuid4(),
            "dotted_order": "20240101T000000000000Z00000000000000000000000000000000",
            "session_name": "proj",
            "name": "test",
            "run_type": "chain",
            "inputs": {"x": 1},
        }
        op = serialize_run_dict("post", run)

        with patch.object(Client, "request_with_retries") as mock_req:
            client._multipart_ingest_ops(
                [op],
                api_url="https://ingest.example.com",
                service_key="jwt-token-123",
                tenant_id="tenant-abc",
            )

            assert mock_req.call_count == 1
            _, url = mock_req.call_args.args[:2]
            assert url == "https://ingest.example.com/runs/multipart"
            headers = mock_req.call_args.kwargs["request_kwargs"]["headers"]
            assert headers.get("X-Service-Key") == "jwt-token-123"
            assert headers.get("X-Tenant-Id") == "tenant-abc"
            # Should not use API key auth when service auth is provided
            assert "x-api-key" not in {k.lower(): v for k, v in headers.items()}

    def test_batch_ingest_uses_service_auth_headers(self):
        """ServiceAuth should flow through /runs/batch headers."""
        from unittest.mock import patch

        client = Client(
            api_url="https://default.example.com",
            api_key="default-key",
            info={"version": "0.0.0"},
        )

        body = b'{"post": [], "patch": []}'
        with patch.object(Client, "request_with_retries") as mock_req:
            client._post_batch_ingest_runs(
                body,
                _context="test",
                api_url="https://ingest.example.com",
                service_key="jwt-token-123",
                tenant_id="tenant-abc",
            )

            assert mock_req.call_count == 1
            _, url = mock_req.call_args.args[:2]
            assert url == "https://ingest.example.com/runs/batch"
            headers = mock_req.call_args.kwargs["request_kwargs"]["headers"]
            assert headers.get("X-Service-Key") == "jwt-token-123"
            assert headers.get("X-Tenant-Id") == "tenant-abc"
            assert "x-api-key" not in {k.lower(): v for k, v in headers.items()}


class TestTracingContextReplicas:
    """Test tracing_context function with replica support."""

    def test_tracing_context_with_new_replica_format(self):
        """Test that tracing_context accepts the WriteReplica format."""
        from langsmith.run_helpers import tracing_context
        from langsmith.run_trees import ApiKeyAuth, WriteReplica

        replicas = [
            WriteReplica(
                api_url="https://replica.example.com",
                auth=ApiKeyAuth(api_key="replica-key"),
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
        from langsmith.run_trees import ApiKeyAuth, WriteReplica

        replicas = [
            # project replica
            WriteReplica(project_name="project-replica", updates={"env": "test"}),
            WriteReplica(
                api_url="https://new.example.com",
                auth=ApiKeyAuth(api_key="new-key"),
                project_name="new-project",
            ),  # API replica
        ]

        # This should not raise a type error
        with tracing_context(replicas=replicas):
            pass  # Just testing that the context manager works
