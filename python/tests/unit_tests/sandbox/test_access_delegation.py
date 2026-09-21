"""Tests for the access_delegation grant on sandbox create."""

import json

import pytest
from pytest_httpx import HTTPXMock

from langsmith.sandbox import AsyncSandboxClient, SandboxClient
from langsmith.sandbox._sandbox import Sandbox

DATAPLANE = "https://sandbox-router.example.com/sb-123"
CREATED = {"name": "sb", "status": "ready", "dataplane_url": DATAPLANE}


@pytest.fixture
def client():
    return SandboxClient(
        api_endpoint="http://test-server:8080", api_key="test-key", max_retries=0
    )


@pytest.fixture
def async_client():
    return AsyncSandboxClient(
        api_endpoint="http://test-server:8080", api_key="test-key", max_retries=0
    )


class TestCreateSendsGrant:
    def test_inherit(self, httpx_mock: HTTPXMock, client):
        httpx_mock.add_response(url="http://test-server:8080/boxes", json=CREATED)
        client.create_sandbox("snap-1", access_delegation={"mode": "INHERIT"})
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["access_delegation"] == {"mode": "INHERIT"}

    def test_explicit(self, httpx_mock: HTTPXMock, client):
        httpx_mock.add_response(url="http://test-server:8080/boxes", json=CREATED)
        client.create_sandbox(
            "snap-1",
            access_delegation={
                "mode": "EXPLICIT",
                "permissions": ["datasets:read", "tracer_sessions:read"],
            },
        )
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["access_delegation"] == {
            "mode": "EXPLICIT",
            "permissions": ["datasets:read", "tracer_sessions:read"],
        }

    def test_omitted_when_unset(self, httpx_mock: HTTPXMock, client):
        httpx_mock.add_response(url="http://test-server:8080/boxes", json=CREATED)
        client.create_sandbox("snap-1")
        assert "access_delegation" not in json.loads(
            httpx_mock.get_requests()[0].content
        )

    async def test_async_create_sends_grant(self, httpx_mock: HTTPXMock, async_client):
        httpx_mock.add_response(url="http://test-server:8080/boxes", json=CREATED)
        await async_client.create_sandbox(
            "snap-1", access_delegation={"mode": "INHERIT"}
        )
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["access_delegation"] == {"mode": "INHERIT"}


class TestCreateRejectsBadGrant:
    """Rejected client-side so the caller does not pay a round trip for a 422."""

    @pytest.mark.parametrize(
        ("grant", "message"),
        [
            ({"mode": "MAYBE"}, 'must be "INHERIT" or "EXPLICIT"'),
            ({"mode": "INHERIT", "permissions": ["a"]}, "not allowed with mode"),
            ({"mode": "EXPLICIT"}, "required with mode"),
            ({"mode": "EXPLICIT", "permissions": "a"}, "must be a list of strings"),
        ],
    )
    def test_invalid(self, client, grant, message):
        with pytest.raises(ValueError, match=message):
            client.create_sandbox("snap-1", access_delegation=grant)


class TestResponseCarriesGrant:
    def test_parsed(self, client):
        sandbox = Sandbox.from_dict(
            data={
                **CREATED,
                "access_delegation": {
                    "mode": "EXPLICIT",
                    "permissions": ["datasets:read"],
                },
            },
            client=client,
            auto_delete=False,
        )
        assert sandbox.access_delegation == {
            "mode": "EXPLICIT",
            "permissions": ["datasets:read"],
        }

    def test_absent(self, client):
        sandbox = Sandbox.from_dict(data=CREATED, client=client, auto_delete=False)
        assert sandbox.access_delegation is None
