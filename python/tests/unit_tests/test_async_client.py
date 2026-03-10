"""Test the AsyncClient."""

import uuid
import warnings
from datetime import datetime
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from langsmith import AsyncClient
from langsmith import schemas as ls_schemas


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
async def test__create_commit_tags(mock_client_cls: mock.Mock) -> None:
    try:
        from langchain_core.prompts import ChatPromptTemplate
    except ImportError:
        pytest.skip("Skipping test that requires langchain-core")

    mock_httpx_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200

    async def mock_request(method, url, **kwargs):
        response = MagicMock()
        response.status_code = 200

        if "/commits/" in url and method == "GET":
            response.json.return_value = {
                "commits": [{"commit_hash": "parent123"}],
                "total": 1,
            }
        elif "/commits/" in url and method == "POST":
            response.json.return_value = {
                "commit": {"commit_hash": "new_commit_123", "id": "1"}
            }
        elif "/repos/" in url and "/tags" in url and method == "POST":
            response.json.return_value = {}
        else:
            response.json.return_value = {}

        return response

    mock_httpx_client.request.side_effect = mock_request
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(
        api_url="http://localhost:1984",
        api_key="test_api_key",
    )

    # Test 1: _update_prompt_tags with multiple tags
    mock_httpx_client.request.reset_mock()
    mock_httpx_client.request.return_value = mock_response
    tags = ["tag1", "tag2", "tag3"]
    commit_id = "abc123"
    await client._create_commit_tags("test-owner/test-repo", commit_id, tags)

    post_calls = [
        call
        for call in mock_httpx_client.request.call_args_list
        if call[0][0] == "POST" and "/repos/" in str(call)
    ]
    assert len(post_calls) == 3

    for i, tag in enumerate(tags):
        call_kwargs = post_calls[i][1]
        assert call_kwargs["json"] == {
            "tag_name": tag,
            "commit_id": commit_id,
        }

    # Test 2: Empty tags list
    mock_httpx_client.request.reset_mock()
    await client._create_commit_tags("owner/repo", "commit123", [])

    post_calls = [
        call
        for call in mock_httpx_client.request.call_args_list
        if call[0][0] == "POST" and "/repos/" in str(call)
    ]
    assert len(post_calls) == 0

    # Test 3: create_commit with tags
    mock_httpx_client.request.reset_mock()
    mock_httpx_client.request.side_effect = mock_request

    with patch.object(AsyncClient, "_prompt_exists", return_value=True):
        with patch.object(AsyncClient, "_current_tenant_is_owner", return_value=True):
            with patch.object(AsyncClient, "_get_settings") as mock_settings:
                mock_settings.return_value = ls_schemas.LangSmithSettings(
                    id=str(uuid.uuid4()),
                    tenant_handle="test-owner",
                    display_name="test_commit",
                    created_at=datetime.now(),
                )

                prompt = ChatPromptTemplate.from_messages(
                    [
                        ("system", "You are a helpful assistant"),
                        ("human", "{input}"),
                    ]
                )

                commit_tags = ["production", "v1.0"]
                await client.create_commit(
                    "test-owner/test-prompt",
                    prompt,
                    tags=commit_tags,
                )

                tag_post_calls = [
                    call
                    for call in mock_httpx_client.request.call_args_list
                    if call[0][0] == "POST"
                    and "/repos/" in str(call)
                    and "/tags" in str(call)
                ]
                assert len(tag_post_calls) == 2

                tag_names = [call[1]["json"]["tag_name"] for call in tag_post_calls]
                assert "production" in tag_names
                assert "v1.0" in tag_names

    # Test 4: create_commit without tags
    mock_httpx_client.request.reset_mock()
    mock_httpx_client.request.side_effect = mock_request

    with patch.object(AsyncClient, "_prompt_exists", return_value=True):
        with patch.object(AsyncClient, "_current_tenant_is_owner", return_value=True):
            with patch.object(AsyncClient, "_get_settings") as mock_settings:
                mock_settings.return_value = ls_schemas.LangSmithSettings(
                    id=str(uuid.uuid4()),
                    tenant_handle="test-owner",
                    display_name="test_commit",
                    created_at=datetime.now(),
                )

                await client.create_commit(
                    "test-owner/test-prompt",
                    prompt,
                )

                tag_post_calls = [
                    call
                    for call in mock_httpx_client.request.call_args_list
                    if call[0][0] == "POST"
                    and "/repos/" in str(call)
                    and "/tags" in str(call)
                ]
                assert len(tag_post_calls) == 0


@pytest.mark.asyncio
@patch.object(AsyncClient, "_prompt_exists", return_value=True)
@patch.object(AsyncClient, "create_commit", new_callable=AsyncMock)
async def test_push_prompt_forwards_commit_tags(
    mock_create_commit: AsyncMock, mock_prompt_exists: AsyncMock
) -> None:
    client = AsyncClient(
        api_url="http://localhost:1984",
        api_key="test_api_key",
    )

    commit_tags = ["alpha", "beta"]
    await client.push_prompt(
        "owner/prompt",
        object=MagicMock(),
        commit_tags=commit_tags,
    )

    mock_create_commit.assert_awaited_once()
    _, kwargs = mock_create_commit.call_args
    assert kwargs["tags"] == commit_tags


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_update_commit_tags(mock_client_cls: mock.Mock) -> None:
    """Test update_commit_tags deletes existing tags then creates new ones."""
    mock_httpx_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200

    mock_httpx_client.request.return_value = mock_response
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(
        api_url="http://localhost:1984",
        api_key="test_api_key",
    )

    # Test 1: update_commit_tags with multiple tags
    commit_id = "abc-123-def"
    tags = ["dev", "prod"]

    with patch.object(AsyncClient, "_get_settings") as mock_settings:
        mock_settings.return_value = ls_schemas.LangSmithSettings(
            id=str(uuid.uuid4()),
            tenant_handle="test-owner",
            display_name="test",
            created_at=datetime.now(),
        )
        await client.update_commit_tags(
            "test-owner/test-prompt",
            commit_id=commit_id,
            tags=tags,
        )

    # Should have DELETE calls for each tag, then POST calls for each tag
    delete_calls = [
        call
        for call in mock_httpx_client.request.call_args_list
        if call[0][0] == "DELETE" and "/tags/" in str(call)
    ]
    post_calls = [
        call
        for call in mock_httpx_client.request.call_args_list
        if call[0][0] == "POST" and "/tags" in str(call)
    ]

    assert len(delete_calls) == 2
    assert len(post_calls) == 2

    # Verify DELETE calls target correct tags
    deleted_tags = {
        call[0][1].rsplit("/", 1)[-1] for call in delete_calls
    }
    assert deleted_tags == {"dev", "prod"}

    # Verify POST calls create correct tags
    created_tags = {call[1]["json"]["tag_name"] for call in post_calls}
    assert created_tags == {"dev", "prod"}
    for call in post_calls:
        assert call[1]["json"]["commit_id"] == commit_id

    # Test 2: single tag as string
    mock_httpx_client.request.reset_mock()
    mock_httpx_client.request.return_value = mock_response

    with patch.object(AsyncClient, "_get_settings") as mock_settings:
        mock_settings.return_value = ls_schemas.LangSmithSettings(
            id=str(uuid.uuid4()),
            tenant_handle="test-owner",
            display_name="test",
            created_at=datetime.now(),
        )
        await client.update_commit_tags(
            "test-owner/test-prompt",
            commit_id=commit_id,
            tags="staging",
        )

    delete_calls = [
        call
        for call in mock_httpx_client.request.call_args_list
        if call[0][0] == "DELETE" and "/tags/" in str(call)
    ]
    post_calls = [
        call
        for call in mock_httpx_client.request.call_args_list
        if call[0][0] == "POST" and "/tags" in str(call)
    ]
    assert len(delete_calls) == 1
    assert len(post_calls) == 1
    assert post_calls[0][1]["json"]["tag_name"] == "staging"


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_delete_commit_tag_not_found(mock_client_cls: mock.Mock) -> None:
    """Test _delete_commit_tag is a no-op when the tag does not exist."""
    mock_httpx_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 404

    mock_httpx_client.request.return_value = mock_response
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(
        api_url="http://localhost:1984",
        api_key="test_api_key",
    )

    # Should not raise
    await client._delete_commit_tag("test-owner/test-repo", "nonexistent")
