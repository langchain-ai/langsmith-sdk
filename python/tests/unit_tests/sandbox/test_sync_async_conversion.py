"""Tests for Sandbox <-> AsyncSandbox conversion."""

import dataclasses

import pytest

from langsmith.sandbox import (
    AsyncSandbox,
    AsyncSandboxClient,
    Sandbox,
    SandboxClient,
)

SANDBOX_DATA = {
    "name": "test-sandbox",
    "dataplane_url": "https://sandbox-router.example.com/sb-123",
    "id": "11111111-2222-3333-4444-555555555555",
    "status": "ready",
    "status_message": None,
    "created_at": "2026-03-24T12:00:00Z",
    "updated_at": "2026-03-24T12:05:00Z",
    "idle_ttl_seconds": 600,
    "delete_after_stop_seconds": 86400,
    "stopped_at": None,
    "snapshot_id": "66666666-7777-8888-9999-000000000000",
    "vcpus": 2,
    "mem_bytes": 1024**3,
    "fs_capacity_bytes": 10 * 1024**3,
}

DATA_FIELDS = list(SANDBOX_DATA)


@pytest.fixture
def sync_client():
    return SandboxClient(
        api_endpoint="http://test-server:8080",
        api_key="test-key",
        timeout=42.0,
        max_retries=7,
        headers={"X-Service-Key": "svc"},
    )


@pytest.fixture
def async_client():
    return AsyncSandboxClient(
        api_endpoint="http://test-server:8080",
        api_key="test-key",
        timeout=42.0,
        max_retries=7,
        headers={"X-Service-Key": "svc"},
    )


class TestClientConversion:
    def test_to_async_copies_config(self, sync_client):
        converted = sync_client.to_async()
        assert isinstance(converted, AsyncSandboxClient)
        assert converted._base_url == sync_client._base_url
        assert converted._api_key == sync_client._api_key
        assert converted._timeout == sync_client._timeout
        assert converted._max_retries == sync_client._max_retries
        assert converted._default_headers == sync_client._default_headers

    def test_to_sync_copies_config(self, async_client):
        converted = async_client.to_sync()
        assert isinstance(converted, SandboxClient)
        assert converted._base_url == async_client._base_url
        assert converted._api_key == async_client._api_key
        assert converted._timeout == async_client._timeout
        assert converted._max_retries == async_client._max_retries
        assert converted._default_headers == async_client._default_headers

    def test_roundtrip(self, sync_client):
        roundtripped = sync_client.to_async().to_sync()
        assert roundtripped._base_url == sync_client._base_url
        assert roundtripped._api_key == sync_client._api_key
        assert roundtripped._default_headers == sync_client._default_headers

    def test_to_async_without_optional_config(self):
        client = SandboxClient(api_endpoint="http://test-server:8080")
        converted = client.to_async()
        assert converted._api_key == client._api_key
        assert converted._default_headers == {}


class TestSandboxConversion:
    def test_to_async_copies_fields(self, sync_client):
        sb = Sandbox.from_dict(SANDBOX_DATA, client=sync_client, auto_delete=True)
        converted = sb.to_async()
        assert isinstance(converted, AsyncSandbox)
        for field in DATA_FIELDS:
            assert getattr(converted, field) == getattr(sb, field), field
        assert isinstance(converted._client, AsyncSandboxClient)
        assert converted._client._base_url == sync_client._base_url

    def test_to_sync_copies_fields(self, async_client):
        sb = AsyncSandbox.from_dict(SANDBOX_DATA, client=async_client, auto_delete=True)
        converted = sb.to_sync()
        assert isinstance(converted, Sandbox)
        for field in DATA_FIELDS:
            assert getattr(converted, field) == getattr(sb, field), field
        assert isinstance(converted._client, SandboxClient)
        assert converted._client._base_url == async_client._base_url

    def test_conversion_disables_auto_delete(self, sync_client, async_client):
        sb = Sandbox.from_dict(SANDBOX_DATA, client=sync_client, auto_delete=True)
        assert sb.to_async()._auto_delete is False
        asb = AsyncSandbox.from_dict(
            SANDBOX_DATA, client=async_client, auto_delete=True
        )
        assert asb.to_sync()._auto_delete is False

    def test_explicit_client_is_used(self, sync_client, async_client):
        sb = Sandbox.from_dict(SANDBOX_DATA, client=sync_client, auto_delete=False)
        assert sb.to_async(client=async_client)._client is async_client
        asb = AsyncSandbox.from_dict(
            SANDBOX_DATA, client=async_client, auto_delete=False
        )
        assert asb.to_sync(client=sync_client)._client is sync_client

    def test_data_fields_stay_in_sync(self):
        """Conversion copies every non-internal dataclass field.

        Guards against a new field being added to one class but missed in
        the conversion methods.
        """
        sync_fields = {f.name for f in dataclasses.fields(Sandbox)}
        async_fields = {f.name for f in dataclasses.fields(AsyncSandbox)}
        assert sync_fields == async_fields
        public_fields = {f for f in sync_fields if not f.startswith("_")}
        assert public_fields == set(DATA_FIELDS)
