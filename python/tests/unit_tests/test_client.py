"""Test the LangSmith client."""
import asyncio
import uuid
from datetime import datetime
from io import BytesIO
from unittest import mock

import pytest

from langsmith.client import Client, _is_localhost
from langsmith.schemas import Example
from langsmith.utils import LangChainPlusUserError

_CREATED_AT = datetime(2015, 1, 1, 0, 0, 0)


def test_is_localhost() -> None:
    assert _is_localhost("http://localhost:1984")
    assert _is_localhost("http://localhost:1984")
    assert _is_localhost("http://0.0.0.0:1984")
    assert not _is_localhost("http://example.com:1984")


def test_validate_api_key_if_hosted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    with pytest.raises(LangChainPlusUserError, match="API key must be provided"):
        Client(api_url="http://www.example.com")
    client = Client(api_url="http://localhost:1984")
    assert client.api_url == "http://localhost:1984"
    assert client.api_key is None


def test_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    client = Client(api_url="http://localhost:1984", api_key="123")
    assert client._headers == {"x-api-key": "123"}

    client_no_key = Client(api_url="http://localhost:1984")
    assert client_no_key._headers == {}


@mock.patch("langsmith.client.requests.post")
def test_upload_csv(mock_post: mock.Mock) -> None:
    dataset_id = str(uuid.uuid4())
    example_1 = Example(
        id=str(uuid.uuid4()),
        created_at=_CREATED_AT,
        inputs={"input": "1"},
        outputs={"output": "2"},
        dataset_id=dataset_id,
    )
    example_2 = Example(
        id=str(uuid.uuid4()),
        created_at=_CREATED_AT,
        inputs={"input": "3"},
        outputs={"output": "4"},
        dataset_id=dataset_id,
    )
    mock_response = mock.Mock()
    mock_response.json.return_value = {
        "id": dataset_id,
        "name": "test.csv",
        "description": "Test dataset",
        "owner_id": "the owner",
        "created_at": _CREATED_AT,
        "examples": [example_1, example_2],
    }
    mock_post.return_value = mock_response

    client = Client(
        api_url="http://localhost:1984",
        api_key="123",
    )
    csv_file = ("test.csv", BytesIO(b"input,output\n1,2\n3,4\n"))

    dataset = client.upload_csv(
        csv_file,
        description="Test dataset",
        input_keys=["input"],
        output_keys=["output"],
    )

    assert dataset.id == uuid.UUID(dataset_id)
    assert dataset.name == "test.csv"
    assert dataset.description == "Test dataset"


def test_async_methods():
    """For every method defined on the Client, if there is a

    corresponding async method, then the async method args should be a
    superset of the sync method args.
    """
    sync_methods = [
        method
        for method in dir(Client)
        if not method.startswith("_")
        and callable(getattr(Client, method))
        and not asyncio.iscoroutinefunction(getattr(Client, method))
    ]
    async_methods = [
        method
        for method in dir(Client)
        if not method.startswith("_")
        and callable(getattr(Client, method))
        and asyncio.iscoroutinefunction(getattr(Client, method))
    ]

    for async_method in async_methods:
        sync_method = async_method[1:]  # Remove the "a" from the beginning
        assert sync_method in sync_methods
        sync_args = set(Client.__dict__[sync_method].__code__.co_varnames)
        async_args = set(Client.__dict__[async_method].__code__.co_varnames)
        assert sync_args.issubset(async_args)
