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
                "commit": {"commit_hash": "new_commit_123", "id": "1"},
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
                    ],
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
    mock_create_commit: AsyncMock,
    mock_prompt_exists: AsyncMock,
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
async def test_list_shared_examples_pagination(mock_client_cls: mock.Mock) -> None:
    """Test list_shared_examples handles pagination correctly."""
    mock_httpx_client = mock.AsyncMock()

    async def mock_request(method, url, **kwargs):
        response = mock.Mock()
        response.status_code = 200
        response.raise_for_status = mock.Mock()

        if "/info" in url:
            response.json.return_value = {}
            return response

        # First request will return 100 examples, second request 50 examples
        offset = kwargs.get("params", {}).get("offset", 0) if "params" in kwargs else 0
        if offset == 0:
            examples = [
                {
                    "id": str(uuid.uuid4()),
                    "created_at": datetime(2015, 1, 1, 0, 0, 0).isoformat(),
                    "inputs": {"text": f"input_{i}"},
                    "outputs": {"result": f"output_{i}"},
                    "dataset_id": str(uuid.uuid4()),
                }
                for i in range(100)
            ]
        else:
            examples = [
                {
                    "id": str(uuid.uuid4()),
                    "created_at": datetime(2015, 1, 1, 0, 0, 0).isoformat(),
                    "inputs": {"text": f"input_{i}"},
                    "outputs": {"result": f"output_{i}"},
                    "dataset_id": str(uuid.uuid4()),
                }
                for i in range(100, 150)
            ]

        response.json.return_value = examples
        return response

    mock_httpx_client.request.side_effect = mock_request
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(
        api_url="http://localhost:1984",
        api_key="fake-key",
    )
    examples = []
    async for example in client.list_shared_examples(str(uuid.uuid4())):
        examples.append(example)

    assert len(examples) == 150  # Should get all examples
    assert examples[0].inputs["text"] == "input_0"
    assert examples[149].inputs["text"] == "input_149"


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_create_examples(mock_client_cls: mock.Mock) -> None:
    """Test create_examples creates multiple examples."""
    mock_httpx_client = mock.AsyncMock()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"id": str(uuid.uuid4())},
        {"id": str(uuid.uuid4())},
    ]
    mock_response.raise_for_status = mock.Mock()
    mock_httpx_client.request.return_value = mock_response
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(api_url="http://localhost:1984", api_key="test-key")

    # Mock read_dataset
    dataset_id = uuid.uuid4()
    with mock.patch.object(
        AsyncClient,
        "read_dataset",
        new_callable=AsyncMock,
        return_value=ls_schemas.Dataset(
            id=dataset_id,
            name="test",
            created_at=datetime.now(),
        ),
    ):
        result = await client.create_examples(
            dataset_name="test",
            examples=[
                {"inputs": {"text": "input1"}, "outputs": {"result": "output1"}},
                {"inputs": {"text": "input2"}, "outputs": {"result": "output2"}},
            ],
        )

    # UpsertExamplesResponse is a TypedDict, access as dict
    assert result["count"] == 2
    assert len(result["example_ids"]) == 2


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_update_example(mock_client_cls: mock.Mock) -> None:
    """Test update_example updates a single example."""
    mock_httpx_client = mock.AsyncMock()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    example_id = uuid.uuid4()
    dataset_id = uuid.uuid4()
    mock_response.json.return_value = {
        "id": str(example_id),
        "dataset_id": str(dataset_id),
        "inputs": {"text": "updated"},
    }
    mock_response.raise_for_status = mock.Mock()
    mock_httpx_client.request.return_value = mock_response
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(api_url="http://localhost:1984", api_key="test-key")

    # Mock read_example
    existing_example = ls_schemas.Example(
        id=example_id,
        dataset_id=dataset_id,
        inputs={"text": "original"},
        created_at=datetime.now(),
    )
    with mock.patch.object(
        AsyncClient,
        "read_example",
        new_callable=AsyncMock,
        return_value=existing_example,
    ):
        result = await client.update_example(
            example_id=example_id,
            inputs={"text": "updated"},
        )

    assert result["inputs"]["text"] == "updated"


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_delete_example(mock_client_cls: mock.Mock) -> None:
    """Test delete_example deletes a single example."""
    mock_httpx_client = mock.AsyncMock()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = mock.Mock()
    mock_httpx_client.request.return_value = mock_response
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(api_url="http://localhost:1984", api_key="test-key")
    example_id = uuid.uuid4()

    await client.delete_example(example_id)

    # Verify DELETE request was made
    assert mock_httpx_client.request.called
    call_args = mock_httpx_client.request.call_args
    assert call_args[0][0] == "DELETE"
    assert str(example_id) in call_args[0][1]


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_delete_examples(mock_client_cls: mock.Mock) -> None:
    """Test delete_examples deletes multiple examples."""
    mock_httpx_client = mock.AsyncMock()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = mock.Mock()
    mock_httpx_client.request.return_value = mock_response
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(api_url="http://localhost:1984", api_key="test-key")
    example_ids = [uuid.uuid4(), uuid.uuid4()]

    await client.delete_examples(example_ids)

    # Verify DELETE request was made
    assert mock_httpx_client.request.called
    call_args = mock_httpx_client.request.call_args
    assert call_args[0][0] == "DELETE"


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_update_examples(mock_client_cls: mock.Mock) -> None:
    """Test update_examples updates multiple examples."""
    mock_httpx_client = mock.AsyncMock()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"message": "2 examples updated", "count": 2}
    mock_response.raise_for_status = mock.Mock()
    mock_httpx_client.request.return_value = mock_response
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(api_url="http://localhost:1984", api_key="test-key")
    dataset_id = uuid.uuid4()

    with mock.patch.object(
        AsyncClient,
        "read_dataset",
        new_callable=AsyncMock,
        return_value=ls_schemas.Dataset(
            id=dataset_id,
            name="test",
            created_at=datetime.now(),
        ),
    ):
        result = await client.update_examples(
            dataset_name="test",
            updates=[
                {"id": str(uuid.uuid4()), "inputs": {"text": "updated1"}},
                {"id": str(uuid.uuid4()), "inputs": {"text": "updated2"}},
            ],
        )

    assert result["count"] == 2


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_has_dataset(mock_client_cls: mock.Mock) -> None:
    """Test has_dataset checks if dataset exists."""
    mock_httpx_client = mock.AsyncMock()

    call_count = [0]  # Use list to allow modification in nested function

    async def mock_request(method, url, **kwargs):
        response = mock.Mock()
        response.status_code = 200
        response.raise_for_status = mock.Mock()

        # First call: test-dataset exists
        # Second call: non-existent dataset
        call_count[0] += 1

        if call_count[0] == 1:
            # Existing dataset
            response.json.return_value = {
                "id": str(uuid.uuid4()),
                "name": "test-dataset",
                "created_at": datetime.now().isoformat(),
            }
        else:
            # Non-existent dataset - return empty list
            response.json.return_value = []

        return response

    mock_httpx_client.request.side_effect = mock_request
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(api_url="http://localhost:1984", api_key="test-key")

    result = await client.has_dataset(dataset_name="test-dataset")
    assert result is True

    # Test with non-existent dataset
    result = await client.has_dataset(dataset_name="non-existent")
    assert result is False


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_share_dataset(mock_client_cls: mock.Mock) -> None:
    """Test share_dataset creates a share link."""
    mock_httpx_client = mock.AsyncMock()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    share_token_uuid = uuid.uuid4()
    mock_response.json.return_value = {
        "share_token": str(share_token_uuid),
        "dataset_id": str(uuid.uuid4()),
    }
    mock_response.raise_for_status = mock.Mock()
    mock_httpx_client.request.return_value = mock_response
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(api_url="http://localhost:1984", api_key="test-key")
    dataset_id = uuid.uuid4()

    with mock.patch.object(
        AsyncClient,
        "read_dataset",
        new_callable=AsyncMock,
        return_value=ls_schemas.Dataset(
            id=dataset_id,
            name="test",
            created_at=datetime.now(),
        ),
    ):
        result = await client.share_dataset(dataset_name="test")

    # DatasetShareSchema is a TypedDict, access as dict
    # share_token remains as string in the dict (cast doesn't convert types)
    assert str(result["share_token"]) == str(share_token_uuid)
    assert "url" in result


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_unshare_dataset(mock_client_cls: mock.Mock) -> None:
    """Test unshare_dataset removes share link."""
    mock_httpx_client = mock.AsyncMock()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = mock.Mock()
    mock_httpx_client.request.return_value = mock_response
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(api_url="http://localhost:1984", api_key="test-key")
    dataset_id = uuid.uuid4()

    await client.unshare_dataset(dataset_id)

    # Verify DELETE request was made
    assert mock_httpx_client.request.called
    call_args = mock_httpx_client.request.call_args
    assert call_args[0][0] == "DELETE"
    assert str(dataset_id) in call_args[0][1]


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_read_shared_dataset(mock_client_cls: mock.Mock) -> None:
    """Test read_shared_dataset reads a shared dataset."""
    mock_httpx_client = mock.AsyncMock()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    dataset_id = uuid.uuid4()
    mock_response.json.return_value = {
        "id": str(dataset_id),
        "name": "shared-dataset",
        "created_at": datetime.now().isoformat(),
    }
    mock_response.raise_for_status = mock.Mock()
    mock_httpx_client.request.return_value = mock_response
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(api_url="http://localhost:1984", api_key="test-key")
    share_token = str(uuid.uuid4())

    result = await client.read_shared_dataset(share_token)

    assert result.id == dataset_id
    assert result.name == "shared-dataset"


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_create_llm_example(mock_client_cls: mock.Mock) -> None:
    """Test create_llm_example creates an LLM example."""
    mock_httpx_client = mock.AsyncMock()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    example_id = uuid.uuid4()
    mock_response.json.return_value = {
        "id": str(example_id),
        "inputs": {"input": "test prompt"},
        "outputs": {"output": "test generation"},
    }
    mock_response.raise_for_status = mock.Mock()
    mock_httpx_client.request.return_value = mock_response
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(api_url="http://localhost:1984", api_key="test-key")
    dataset_id = uuid.uuid4()

    with mock.patch.object(
        AsyncClient,
        "read_dataset",
        new_callable=AsyncMock,
        return_value=ls_schemas.Dataset(
            id=dataset_id,
            name="test",
            created_at=datetime.now(),
        ),
    ):
        result = await client.create_llm_example(
            prompt="test prompt",
            generation="test generation",
            dataset_name="test",
        )

    assert result.inputs["input"] == "test prompt"
    assert result.outputs["output"] == "test generation"


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_create_chat_example(mock_client_cls: mock.Mock) -> None:
    """Test create_chat_example creates a chat example."""
    mock_httpx_client = mock.AsyncMock()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    example_id = uuid.uuid4()
    mock_response.json.return_value = {
        "id": str(example_id),
        "inputs": {"input": [{"role": "user", "content": "hello"}]},
        "outputs": {"output": {"role": "assistant", "content": "hi"}},
    }
    mock_response.raise_for_status = mock.Mock()
    mock_httpx_client.request.return_value = mock_response
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(api_url="http://localhost:1984", api_key="test-key")
    dataset_id = uuid.uuid4()

    with mock.patch.object(
        AsyncClient,
        "read_dataset",
        new_callable=AsyncMock,
        return_value=ls_schemas.Dataset(
            id=dataset_id,
            name="test",
            created_at=datetime.now(),
        ),
    ):
        result = await client.create_chat_example(
            messages=[{"role": "user", "content": "hello"}],
            generations={"role": "assistant", "content": "hi"},
            dataset_name="test",
        )

    assert len(result.inputs["input"]) == 1
    assert result.inputs["input"][0]["role"] == "user"


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_read_dataset_version(mock_client_cls: mock.Mock) -> None:
    """Test read_dataset_version reads a dataset version."""
    mock_httpx_client = mock.AsyncMock()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    dataset_id = uuid.uuid4()
    mock_response.json.return_value = {
        "as_of": datetime.now().isoformat(),
        "tags": ["latest"],
    }
    mock_response.raise_for_status = mock.Mock()
    mock_httpx_client.request.return_value = mock_response
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(api_url="http://localhost:1984", api_key="test-key")

    with mock.patch.object(
        AsyncClient,
        "read_dataset",
        new_callable=AsyncMock,
        return_value=ls_schemas.Dataset(
            id=dataset_id,
            name="test",
            created_at=datetime.now(),
        ),
    ):
        result = await client.read_dataset_version(dataset_name="test", tag="latest")

    assert result.tags == ["latest"]


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_list_dataset_versions(mock_client_cls: mock.Mock) -> None:
    """Test list_dataset_versions lists dataset versions."""
    mock_httpx_client = mock.AsyncMock()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"id": str(uuid.uuid4()), "tag": "v1", "as_of": datetime.now().isoformat()},
        {"id": str(uuid.uuid4()), "tag": "v2", "as_of": datetime.now().isoformat()},
    ]
    mock_response.raise_for_status = mock.Mock()
    mock_httpx_client.request.return_value = mock_response
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(api_url="http://localhost:1984", api_key="test-key")
    dataset_id = uuid.uuid4()

    with mock.patch.object(
        AsyncClient,
        "read_dataset",
        new_callable=AsyncMock,
        return_value=ls_schemas.Dataset(
            id=dataset_id,
            name="test",
            created_at=datetime.now(),
        ),
    ):
        versions = []
        async for version in client.list_dataset_versions(dataset_name="test"):
            versions.append(version)

    assert len(versions) == 2


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_update_dataset_tag(mock_client_cls: mock.Mock) -> None:
    """Test update_dataset_tag updates a dataset tag."""
    mock_httpx_client = mock.AsyncMock()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = mock.Mock()
    mock_httpx_client.request.return_value = mock_response
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(api_url="http://localhost:1984", api_key="test-key")
    dataset_id = uuid.uuid4()

    with mock.patch.object(
        AsyncClient,
        "read_dataset",
        new_callable=AsyncMock,
        return_value=ls_schemas.Dataset(
            id=dataset_id,
            name="test",
            created_at=datetime.now(),
        ),
    ):
        await client.update_dataset_tag(
            dataset_name="test",
            as_of=datetime.now(),
            tag="production",
        )

    # Verify PUT request was made
    assert mock_httpx_client.request.called
    call_args = mock_httpx_client.request.call_args
    assert call_args[0][0] == "PUT"
    assert str(dataset_id) in call_args[0][1]


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_list_dataset_splits(mock_client_cls: mock.Mock) -> None:
    """Test list_dataset_splits lists dataset splits."""
    mock_httpx_client = mock.AsyncMock()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = ["train", "test", "validation"]
    mock_response.raise_for_status = mock.Mock()
    mock_httpx_client.request.return_value = mock_response
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(api_url="http://localhost:1984", api_key="test-key")
    dataset_id = uuid.uuid4()

    with mock.patch.object(
        AsyncClient,
        "read_dataset",
        new_callable=AsyncMock,
        return_value=ls_schemas.Dataset(
            id=dataset_id,
            name="test",
            created_at=datetime.now(),
        ),
    ):
        splits = await client.list_dataset_splits(dataset_name="test")

    assert len(splits) == 3
    assert "train" in splits
    assert "test" in splits
    assert "validation" in splits


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_update_dataset_splits(mock_client_cls: mock.Mock) -> None:
    """Test update_dataset_splits updates dataset splits."""
    mock_httpx_client = mock.AsyncMock()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = mock.Mock()
    mock_httpx_client.request.return_value = mock_response
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(api_url="http://localhost:1984", api_key="test-key")
    dataset_id = uuid.uuid4()
    example_ids = [uuid.uuid4(), uuid.uuid4()]

    with mock.patch.object(
        AsyncClient,
        "read_dataset",
        new_callable=AsyncMock,
        return_value=ls_schemas.Dataset(
            id=dataset_id,
            name="test",
            created_at=datetime.now(),
        ),
    ):
        await client.update_dataset_splits(
            dataset_name="test",
            split_name="train",
            example_ids=example_ids,
        )

    # Verify POST request was made
    assert mock_httpx_client.request.called
    call_args = mock_httpx_client.request.call_args
    assert call_args[0][0] == "POST"
    assert str(dataset_id) in call_args[0][1]


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_diff_dataset_versions(mock_client_cls: mock.Mock) -> None:
    """Test diff_dataset_versions gets differences between versions."""
    mock_httpx_client = mock.AsyncMock()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "examples_added": [str(uuid.uuid4()) for _ in range(5)],
        "examples_removed": [str(uuid.uuid4()) for _ in range(2)],
        "examples_modified": [str(uuid.uuid4()) for _ in range(3)],
    }
    mock_response.raise_for_status = mock.Mock()
    mock_httpx_client.request.return_value = mock_response
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(api_url="http://localhost:1984", api_key="test-key")
    dataset_id = uuid.uuid4()

    with mock.patch.object(
        AsyncClient,
        "read_dataset",
        new_callable=AsyncMock,
        return_value=ls_schemas.Dataset(
            id=dataset_id,
            name="test",
            created_at=datetime.now(),
        ),
    ):
        result = await client.diff_dataset_versions(
            dataset_name="test",
            from_version="v1",
            to_version="v2",
        )

    assert len(result.examples_added) == 5
    assert len(result.examples_removed) == 2
    assert len(result.examples_modified) == 3


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_read_dataset_shared_schema(mock_client_cls: mock.Mock) -> None:
    """Test read_dataset_shared_schema reads shared schema."""
    mock_httpx_client = mock.AsyncMock()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    share_token_uuid = uuid.uuid4()
    mock_response.json.return_value = {
        "share_token": str(share_token_uuid),
        "dataset_id": str(uuid.uuid4()),
    }
    mock_response.raise_for_status = mock.Mock()
    mock_httpx_client.request.return_value = mock_response
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(api_url="http://localhost:1984", api_key="test-key")
    dataset_id = uuid.uuid4()

    with mock.patch.object(
        AsyncClient,
        "read_dataset",
        new_callable=AsyncMock,
        return_value=ls_schemas.Dataset(
            id=dataset_id,
            name="test",
            created_at=datetime.now(),
        ),
    ):
        result = await client.read_dataset_shared_schema(dataset_name="test")

    # DatasetShareSchema is a TypedDict, access as dict
    # share_token remains as string in the dict (cast doesn't convert types)
    assert str(result["share_token"]) == str(share_token_uuid)
    assert "url" in result


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_read_dataset_openai_finetuning(mock_client_cls: mock.Mock) -> None:
    """Test read_dataset_openai_finetuning downloads dataset in OpenAI format."""
    mock_httpx_client = mock.AsyncMock()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.text = '{"messages": [{"role": "user", "content": "test"}]}\n{"messages": [{"role": "assistant", "content": "response"}]}'
    mock_response.raise_for_status = mock.Mock()
    mock_httpx_client.request.return_value = mock_response
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(api_url="http://localhost:1984", api_key="test-key")
    dataset_id = uuid.uuid4()

    with mock.patch.object(
        AsyncClient,
        "read_dataset",
        new_callable=AsyncMock,
        return_value=ls_schemas.Dataset(
            id=dataset_id,
            name="test",
            created_at=datetime.now(),
        ),
    ):
        result = await client.read_dataset_openai_finetuning(dataset_name="test")

    assert len(result) == 2
    assert result[0]["messages"][0]["role"] == "user"
