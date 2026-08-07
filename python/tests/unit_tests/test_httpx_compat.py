import pytest

from langsmith._internal._httpx import httpx
from langsmith._openapi_client import AsyncLangsmith, Langsmith


def _info_response(request: httpx.Request) -> httpx.Response:
    assert request.url.path == "/api/v1/info"
    return httpx.Response(200, json={"version": "test"})


def test_prefers_httpx2_for_sync_requests() -> None:
    assert httpx.__name__ == "httpx2"
    with httpx.Client(transport=httpx.MockTransport(_info_response)) as http_client:
        with Langsmith(
            api_key="test", base_url="https://example.com", http_client=http_client
        ) as client:
            assert client.info.list().version == "test"


@pytest.mark.asyncio
async def test_prefers_httpx2_for_async_requests() -> None:
    assert httpx.__name__ == "httpx2"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(_info_response)
    ) as http_client:
        async with AsyncLangsmith(
            api_key="test", base_url="https://example.com", http_client=http_client
        ) as client:
            assert (await client.info.list()).version == "test"
