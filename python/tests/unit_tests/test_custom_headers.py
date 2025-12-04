"""Test custom headers functionality."""

from unittest import mock

import pytest

from langsmith import Client


def _clear_env_cache():
    """Clear the environment variable cache."""
    try:
        from langsmith import env

        env._runtime_env.cache_clear()
    except Exception:
        pass


@mock.patch("langsmith.client.requests.Session")
def test_custom_headers(
    mock_session: mock.Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that custom headers are properly merged with default headers."""
    _clear_env_cache()
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)

    with mock.patch.dict("os.environ", {}, clear=True):
        # Test with custom headers
        custom_headers = {
            "X-Custom-Header": "custom-value",
            "X-Another-Header": "another-value",
        }

        client = Client(
            api_url="http://localhost:1984",
            api_key="test-api-key",
            headers=custom_headers,
        )

        # Check that custom headers are included
        assert "X-Custom-Header" in client._headers
        assert client._headers["X-Custom-Header"] == "custom-value"
        assert "X-Another-Header" in client._headers
        assert client._headers["X-Another-Header"] == "another-value"

        # Check that default headers are still present
        assert "User-Agent" in client._headers
        assert "Accept" in client._headers
        assert "x-api-key" in client._headers
        assert client._headers["x-api-key"] == "test-api-key"


@mock.patch("langsmith.client.requests.Session")
def test_custom_headers_dont_override_required(
    mock_session: mock.Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that custom headers don't override required headers."""
    _clear_env_cache()
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)

    with mock.patch.dict("os.environ", {}, clear=True):
        # Try to override the API key with custom headers (should not work)
        custom_headers = {
            "x-api-key": "wrong-key",
            "X-Custom-Header": "custom-value",
        }

        client = Client(
            api_url="http://localhost:1984",
            api_key="correct-api-key",
            headers=custom_headers,
        )

        # Check that the API key from the parameter is used, not the custom header
        assert client._headers["x-api-key"] == "correct-api-key"
        # But the custom header should still be present
        assert client._headers["X-Custom-Header"] == "custom-value"


@mock.patch("langsmith.client.requests.Session")
def test_no_custom_headers(
    mock_session: mock.Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that client works without custom headers."""
    _clear_env_cache()
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)

    with mock.patch.dict("os.environ", {}, clear=True):
        client = Client(
            api_url="http://localhost:1984",
            api_key="test-api-key",
        )

        # Check that default headers are present
        assert "User-Agent" in client._headers
        assert "Accept" in client._headers
        assert "x-api-key" in client._headers
        assert client._headers["x-api-key"] == "test-api-key"


@mock.patch("langsmith.client.requests.Session")
def test_workspace_id_with_custom_headers(
    mock_session: mock.Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that workspace_id header is preserved with custom headers."""
    _clear_env_cache()
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)

    with mock.patch.dict("os.environ", {}, clear=True):
        custom_headers = {
            "X-Custom-Header": "custom-value",
        }

        client = Client(
            api_url="http://localhost:1984",
            api_key="test-api-key",
            workspace_id="test-workspace",
            headers=custom_headers,
        )

        # Check that workspace ID header is present
        assert "X-Tenant-Id" in client._headers
        assert client._headers["X-Tenant-Id"] == "test-workspace"
        # And custom header is also present
        assert client._headers["X-Custom-Header"] == "custom-value"
