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
