"""Test the AsyncClient."""

import warnings
from unittest import mock
from uuid import uuid4

import pytest

from langsmith import AsyncClient


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_list_runs_child_run_ids_deprecation_warning(
    mock_client_cls: mock.Mock,
) -> None:
    mock_httpx_client = mock.AsyncMock()
    mock_client_cls.return_value = mock_httpx_client

    # Mock the response for list_runs
    mock_response = mock.Mock()
    mock_response.json.return_value = {"runs": []}
    mock_response.status_code = 200
    mock_response.raise_for_status = mock.Mock()
    mock_httpx_client.request.return_value = mock_response

    client = AsyncClient()

    # Test that deprecation warning is raised when child_run_ids is in select
    with pytest.warns(DeprecationWarning, match="child_run_ids field is deprecated"):
        async for _ in client.list_runs(
            project_id=uuid4(),
            select=["id", "name", "child_run_ids"],
        ):
            pass

    # Test that no warning is raised when child_run_ids is not in select
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        async for _ in client.list_runs(project_id=uuid4(), select=["id", "name"]):
            pass


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_list_examples_pagination_with_ids(mock_client_cls: mock.Mock) -> None:
    """Test list_examples does not paginate when filtering by IDs."""
    mock_httpx_client = mock.AsyncMock()
    mock_client_cls.return_value = mock_httpx_client
    request_offsets = []

    async def mock_request(*args, **kwargs):
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = mock.Mock()

        params = kwargs.get("params", {})
        offset = params.get("offset", 0)
        request_offsets.append(offset)

        if offset == 0:
            examples = [
                {
                    "id": str(uuid4()),
                    "inputs": {"text": f"input_{i}"},
                    "outputs": {"result": f"output_{i}"},
                }
                for i in range(100)
            ]
            mock_response.json.return_value = examples
        else:
            raise Exception(f"Unexpected pagination request with offset={offset}")

        return mock_response

    mock_httpx_client.request.side_effect = mock_request

    client = AsyncClient(api_key="test-key")
    example_ids = [str(uuid4()) for _ in range(100)]

    examples = []
    async for example in client.list_examples(example_ids=example_ids):
        examples.append(example)

    assert len(examples) == 100
    assert all(offset == 0 for offset in request_offsets)
