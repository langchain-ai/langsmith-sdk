import pytest
from pytest_httpx import HTTPXMock

from langsmith import utils
from langsmith.sandbox import AsyncSandboxClient, SandboxClient


@pytest.fixture(autouse=True)
def clear_env_cache():
    utils.get_env_var.cache_clear()
    yield
    utils.get_env_var.cache_clear()


@pytest.mark.parametrize(
    "host",
    [
        "https://ls.example.com",
        "https://eu.api.smith.langchain.com",
        "https://ls.example.com/prefix",
    ],
)
@pytest.mark.parametrize("suffix", ["", "/", "/api", "/api/", "/api/v1", "/api/v1/"])
@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("async_client", [False, True])
async def test_endpoint_requests(
    monkeypatch, httpx_mock: HTTPXMock, host, suffix, explicit, async_client
):
    monkeypatch.setenv("LANGSMITH_ENDPOINT", host + suffix)
    endpoint = host + "/api/v2/sandboxes/" if explicit else None
    httpx_mock.add_response(
        url=host + "/api/v2/sandboxes/boxes", json={"sandboxes": []}
    )
    httpx_mock.add_response(
        url=host + "/api/v2/sandboxes/registries", json={"registries": []}
    )
    if async_client:
        async with AsyncSandboxClient(api_endpoint=endpoint, api_key="test") as client:
            await client.list_sandboxes()
            await client.registries.list()
    else:
        with SandboxClient(api_endpoint=endpoint, api_key="test") as client:
            client.list_sandboxes()
            client.registries.list()


@pytest.mark.parametrize("client_class", [SandboxClient, AsyncSandboxClient])
async def test_default_endpoint(monkeypatch, client_class):
    monkeypatch.delenv("LANGSMITH_ENDPOINT", raising=False)
    monkeypatch.delenv("LANGCHAIN_ENDPOINT", raising=False)
    client = client_class(api_key="test")
    assert client._base_url == "https://api.smith.langchain.com/api/v2/sandboxes"
    assert client._api_root() == "https://api.smith.langchain.com"
    if isinstance(client, AsyncSandboxClient):
        await client.aclose()
    else:
        client.close()
