import asyncio

import httpx
import pytest
from uvicorn import Config, Server

from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
from tests.integration_tests.fake_server import fake_app


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def fake_server():
    config = Config(app=fake_app, loop="asyncio", port=8000, log_level="info")
    server = Server(config=config)

    asyncio.create_task(server.serve())
    await asyncio.sleep(0.1)

    yield
    try:
        await server.shutdown()
    except RuntimeError:
        pass


@traceable
async def the_parent_function():
    async with httpx.AsyncClient(
        app=fake_app, base_url="http://localhost:8000"
    ) as http_client:
        headers = {}
        if span := get_current_run_tree():
            headers.update(span.to_headers())
        response = await http_client.post("/fake-route", headers=headers)
        assert response.status_code == 200
        return response.json()


@traceable
async def the_root_function(foo: str):
    return await the_parent_function()


@pytest.mark.asyncio
async def test_tracing_fake_server(fake_server):
    result = await the_root_function(
        "test input",
        langsmith_extra={
            "metadata": {"some-cool-value": 42},
            "tags": ["did-propagate"],
            "project_name": "distributed-tracing",
        },
    )
    assert result["message"] == "Fake route response"
