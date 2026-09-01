import pytest

from langsmith._openapi_client import AsyncLangsmith, Langsmith
from langsmith._openapi_client._httpx import httpx


def _info_response(request: httpx.Request) -> httpx.Response:
    assert request.url.path == "/api/v1/info"
    return httpx.Response(200, json={"version": "test"})


def test_user_agent_names_the_backend() -> None:
    from langsmith import AsyncClient, Client

    suffix = f"-{httpx.__name__}"
    assert Client(api_key="test")._compute_headers()["User-Agent"].endswith(suffix)
    assert AsyncClient(api_key="test")._compute_headers()["User-Agent"].endswith(suffix)


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
