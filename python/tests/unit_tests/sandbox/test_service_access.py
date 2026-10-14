"""Tests for LangSmith-login service URLs (the ``access`` parameter)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from langsmith.sandbox import (
    AsyncSandboxClient,
    SandboxClient,
    ServiceLoginURL,
    ServiceURL,
)

TOKEN_BODY = {
    "browser_url": "https://box--8000.example.dev/_svc/auth?token=tok",
    "service_url": "https://box--8000.example.dev/",
    "token": "tok",
    "expires_at": "2099-01-01T00:00:00Z",
}

LOGIN_BODY = {
    "browser_url": "https://l-abc.example.dev/",
    "service_url": "https://l-abc.example.dev/",
    "access": "workspace",
}


def _client(body):
    client = SandboxClient(
        api_endpoint="http://test-server:8080", api_key="k", max_retries=0
    )
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = body
    client._http.post = MagicMock(return_value=response)
    return client


def _payload(client):
    return client._http.post.call_args.kwargs["json"]


class TestTokenMode:
    def test_default_is_token_mode(self):
        client = _client(TOKEN_BODY)
        result = client.service("sb", 8000)
        assert isinstance(result, ServiceURL)
        assert _payload(client) == {"port": 8000, "expires_in_seconds": 600}


class TestLoginMode:
    @pytest.mark.parametrize("access", ["restricted", "workspace"])
    def test_returns_a_login_url(self, access):
        client = _client({**LOGIN_BODY, "access": access})
        result = client.service("sb", 8000, access=access)
        assert isinstance(result, ServiceLoginURL)
        assert result.url == "https://l-abc.example.dev/"
        assert result.access == access

    def test_ttl_is_not_sent(self):
        """A login URL carries no token, so a TTL would be meaningless."""
        client = _client(LOGIN_BODY)
        client.service("sb", 8000, access="workspace", expires_in_seconds=3600)
        assert _payload(client) == {"port": 8000, "access": "workspace"}


class TestValidation:
    def test_rejects_off(self):
        """`off` revokes a share as a side effect of minting; not exposed."""
        client = _client(TOKEN_BODY)
        with pytest.raises(ValueError, match="restricted"):
            client.service("sb", 8000, access="off")
        client._http.post.assert_not_called()

    def test_rejects_an_unknown_access_value(self):
        client = _client(TOKEN_BODY)
        with pytest.raises(ValueError, match="restricted"):
            client.service("sb", 8000, access="maybe")
        client._http.post.assert_not_called()


class TestAsyncClient:
    async def test_login_mode(self):
        client = AsyncSandboxClient(
            api_endpoint="http://test-server:8080", api_key="k", max_retries=0
        )
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = LOGIN_BODY
        client._http.post = AsyncMock(return_value=response)

        result = await client.service("sb", 8000, access="workspace")
        assert isinstance(result, ServiceLoginURL)
        assert result.access == "workspace"
        assert client._http.post.call_args.kwargs["json"] == {
            "port": 8000,
            "access": "workspace",
        }
