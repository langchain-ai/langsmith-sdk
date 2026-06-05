"""Test the AsyncClient."""

import json
import pathlib
import uuid
import warnings
from datetime import datetime
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest
import requests

from langsmith import AsyncClient
from langsmith import schemas as ls_schemas
from langsmith import utils as ls_utils


def _clear_profile_env(monkeypatch: pytest.MonkeyPatch) -> None:
    ls_utils.get_env_var.cache_clear()
    for key in (
        "LANGCHAIN_API_KEY",
        "LANGSMITH_API_KEY",
        "LANGCHAIN_ENDPOINT",
        "LANGSMITH_ENDPOINT",
        "LANGSMITH_PROFILE",
    ):
        monkeypatch.delenv(key, raising=False)


@mock.patch("langsmith.async_client.httpx.AsyncClient")
def test_async_client_custom_headers(mock_client_cls: mock.Mock) -> None:
    mock_httpx_client = mock.Mock()
    mock_httpx_client.headers = httpx.Headers()
    mock_client_cls.return_value = mock_httpx_client

    AsyncClient(
        api_url="http://localhost:1984",
        api_key="test-api-key",
        headers={
            "X-Custom-Header": "custom-value",
            "X-Another-Header": "another-value",
        },
    )

    passed_headers = mock_client_cls.call_args.kwargs["headers"]
    assert passed_headers["X-Custom-Header"] == "custom-value"
    assert passed_headers["X-Another-Header"] == "another-value"
    assert passed_headers["Content-Type"] == "application/json"
    assert passed_headers["x-api-key"] == "test-api-key"


@mock.patch("langsmith.async_client.httpx.AsyncClient")
def test_async_client_headers_dont_override_required(
    mock_client_cls: mock.Mock,
) -> None:
    mock_httpx_client = mock.Mock()
    mock_httpx_client.headers = httpx.Headers()
    mock_client_cls.return_value = mock_httpx_client

    AsyncClient(
        api_url="http://localhost:1984",
        api_key="correct-api-key",
        headers={
            "x-api-key": "wrong-key",
            "X-Custom-Header": "custom-value",
        },
    )

    passed_headers = mock_client_cls.call_args.kwargs["headers"]
    assert passed_headers["x-api-key"] == "correct-api-key"
    assert passed_headers["X-Custom-Header"] == "custom-value"


@mock.patch("langsmith.async_client.httpx.AsyncClient")
def test_async_client_headers_property_setter(mock_client_cls: mock.Mock) -> None:
    mock_httpx_client = mock.Mock()
    mock_httpx_client.headers = httpx.Headers()
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(
        api_url="http://localhost:1984",
        api_key="test-api-key",
        headers={"X-Initial-Header": "initial-value"},
    )

    client.headers = {
        "X-New-Header": "new-value",
        "X-Another-Header": "another-value",
    }

    assert client._headers["x-new-header"] == "new-value"
    assert client._headers["x-another-header"] == "another-value"
    assert client._headers["x-api-key"] == "test-api-key"
    assert "x-initial-header" not in client._headers


@mock.patch("langsmith.async_client.httpx.AsyncClient")
def test_async_client_headers_property_getter(mock_client_cls: mock.Mock) -> None:
    mock_httpx_client = mock.Mock()
    mock_httpx_client.headers = httpx.Headers()
    mock_client_cls.return_value = mock_httpx_client

    custom_headers = {"X-Custom-Header": "custom-value"}
    client = AsyncClient(
        api_url="http://localhost:1984",
        api_key="test-api-key",
        headers=custom_headers,
    )

    assert client.headers == custom_headers


@mock.patch("langsmith.async_client.httpx.AsyncClient")
def test_async_client_no_custom_headers(mock_client_cls: mock.Mock) -> None:
    mock_httpx_client = mock.Mock()
    mock_httpx_client.headers = httpx.Headers()
    mock_client_cls.return_value = mock_httpx_client

    AsyncClient(
        api_url="http://localhost:1984",
        api_key="test-api-key",
    )

    passed_headers = mock_client_cls.call_args.kwargs["headers"]
    assert passed_headers["Content-Type"] == "application/json"
    assert passed_headers["x-api-key"] == "test-api-key"


@mock.patch("langsmith.async_client.httpx.AsyncClient")
def test_async_client_profile_config_uses_oauth_access_token(
    mock_client_cls: mock.Mock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    _clear_profile_env(monkeypatch)
    mock_httpx_client = mock.Mock()
    mock_httpx_client.headers = httpx.Headers()
    mock_client_cls.return_value = mock_httpx_client
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "profiles": {
                    "default": {
                        "api_url": "https://profile.example.com",
                        "oauth": {"access_token": "profile-access-token"},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LANGSMITH_CONFIG_FILE", str(config_path))

    AsyncClient()

    assert mock_client_cls.call_args.kwargs["base_url"] == "https://profile.example.com"
    passed_headers = mock_client_cls.call_args.kwargs["headers"]
    assert passed_headers["Authorization"] == "Bearer profile-access-token"
    assert "x-api-key" not in passed_headers


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_async_client_profile_refresh_replaces_snapshotted_auth_headers(
    mock_client_cls: mock.Mock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    _clear_profile_env(monkeypatch)
    mock_httpx_client = mock.AsyncMock()
    mock_httpx_client.headers = httpx.Headers()
    response = mock.Mock()
    response.status_code = 200
    mock_httpx_client.request.return_value = response
    mock_client_cls.return_value = mock_httpx_client
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "profiles": {
                    "default": {
                        "api_url": "https://profile.example.com",
                        "oauth": {
                            "access_token": "old-access-token",
                            "refresh_token": "old-refresh-token",
                            "expires_at": "2000-01-01T00:00:00Z",
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LANGSMITH_CONFIG_FILE", str(config_path))

    def mock_post(url: str, **kwargs: object) -> mock.Mock:
        response = mock.Mock()
        response.status_code = 200
        response.json.return_value = {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 300,
        }
        return response

    monkeypatch.setattr(requests, "post", mock_post)
    client = AsyncClient()
    snapshotted_headers = dict(mock_client_cls.call_args.kwargs["headers"])

    await client._arequest_with_retries(
        "GET",
        "/info",
        headers=snapshotted_headers,
    )

    request_headers = mock_httpx_client.request.call_args.kwargs["headers"]
    assert request_headers["Authorization"] == "Bearer new-access-token"


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
@patch("langsmith.async_client.asyncio.sleep", new_callable=AsyncMock)
@patch("langsmith.async_client.ls_utils.raise_for_status_with_text")
async def test_arequest_with_retries_retries_on_502(
    mock_raise_for_status: mock.Mock,
    _mock_sleep: AsyncMock,
    mock_client_cls: mock.Mock,
) -> None:
    mock_httpx_client = AsyncMock()
    mock_client_cls.return_value = mock_httpx_client

    first_response = MagicMock()
    first_response.status_code = 502

    second_response = MagicMock()
    second_response.status_code = 200
    mock_httpx_client.request.side_effect = [first_response, second_response]

    def _raise_for_status(response):
        if response.status_code >= 400:
            raise httpx.HTTPStatusError(
                "status error",
                request=httpx.Request("GET", "http://test"),
                response=response,
            )

    mock_raise_for_status.side_effect = _raise_for_status

    client = AsyncClient(retry_config={"max_retries": 2})
    response = await client._arequest_with_retries("GET", "/repos/-/test")
    assert response == second_response


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
@patch("langsmith.async_client.ls_utils.raise_for_status_with_text")
async def test_create_feedback_forwards_trace_id(
    mock_raise_for_status: mock.Mock,
    mock_client_cls: mock.Mock,
) -> None:
    mock_httpx_client = AsyncMock()
    mock_client_cls.return_value = mock_httpx_client
    mock_raise_for_status.return_value = None

    run_id = uuid4()
    trace_id = uuid4()
    now = datetime(2024, 1, 1).isoformat()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "id": str(uuid4()),
        "created_at": now,
        "modified_at": now,
        "run_id": str(run_id),
        "trace_id": str(trace_id),
        "key": "quality",
    }
    mock_httpx_client.request.return_value = response

    client = AsyncClient(api_url="http://localhost:1984", api_key="test")
    await client.create_feedback(run_id, key="quality", score=1, trace_id=trace_id)

    call = mock_httpx_client.request.call_args
    assert call.args[0] == "POST"
    assert call.args[1] == "/feedback"
    body = json.loads(call.kwargs["content"])
    assert uuid.UUID(body["run_id"]) == run_id
    assert uuid.UUID(body["trace_id"]) == trace_id
    assert body["key"] == "quality"


@mock.patch("langsmith.async_client.httpx.AsyncClient")
@pytest.mark.asyncio
@patch("langsmith.async_client.asyncio.sleep", new_callable=AsyncMock)
@patch("langsmith.async_client.ls_utils.raise_for_status_with_text")
async def test_create_feedback_retries_on_not_found(
    mock_raise_for_status: mock.Mock,
    _mock_sleep: AsyncMock,
    mock_client_cls: mock.Mock,
) -> None:
    mock_httpx_client = AsyncMock()
    mock_client_cls.return_value = mock_httpx_client

    run_id = uuid4()
    trace_id = uuid4()
    now = datetime(2024, 1, 1).isoformat()

    not_found = MagicMock()
    not_found.status_code = 404
    success = MagicMock()
    success.status_code = 200
    success.json.return_value = {
        "id": str(uuid4()),
        "created_at": now,
        "modified_at": now,
        "run_id": str(run_id),
        "trace_id": str(trace_id),
        "key": "quality",
    }
    mock_httpx_client.request.side_effect = [not_found, success]

    def _raise_for_status(response: mock.Mock) -> None:
        if response.status_code >= 400:
            raise httpx.HTTPStatusError(
                "status error",
                request=httpx.Request("POST", "http://test"),
                response=response,
            )

    mock_raise_for_status.side_effect = _raise_for_status

    client = AsyncClient(
        api_url="http://localhost:1984",
        api_key="test",
        retry_config={"max_retries": 2},
    )
    feedback = await client.create_feedback(run_id, key="quality", trace_id=trace_id)

    # A 404 (run not yet ingested) is retried, unlike other 4xx.
    assert mock_httpx_client.request.call_count == 2
    assert str(feedback.run_id) == str(run_id)
    assert mock_httpx_client.request.call_count == 2


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
def test_async_client_repr_hides_sensitive_info(mock_client_cls: mock.Mock) -> None:
    """Test that __repr__ does not expose sensitive information like API keys."""
    mock_httpx_client = mock.Mock()
    mock_httpx_client.base_url = "https://api.smith.langchain.com"
    mock_httpx_client.headers = httpx.Headers()
    mock_client_cls.return_value = mock_httpx_client

    client = AsyncClient(
        api_url="https://api.smith.langchain.com",
        api_key="super-secret-api-key-12345",
    )

    repr_str = repr(client)
    # Ensure API key is NOT in the repr
    assert "super-secret-api-key-12345" not in repr_str
    # Ensure the repr shows the API URL
    assert "https://api.smith.langchain.com" in repr_str
    # Ensure it's properly formatted
    assert repr_str == "AsyncClient (API URL: https://api.smith.langchain.com)"


def _online_evaluator_response(
    evaluator_id: uuid.UUID,
    *,
    evaluator_type: str = "llm",
) -> dict:
    response = {
        "id": str(evaluator_id),
        "tenant_id": str(uuid.uuid4()),
        "name": "quality judge",
        "type": evaluator_type,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
        "feedback_keys": ["quality"],
        "created_by": "tester",
        "run_rules": [],
    }
    if evaluator_type == "llm":
        response["llm_evaluator"] = {
            "evaluator_id": str(evaluator_id),
            "prompt_id": str(uuid.uuid4()),
            "prompt_repo_handle": "owner/quality-judge",
            "variable_mapping": {"input": "inputs.question"},
            "commit_hash_or_tag": "latest",
        }
    else:
        response["code_evaluator"] = {
            "evaluator_id": str(evaluator_id),
            "code": "def score(run): return True",
            "language": "python",
        }
    return response


def _without_bound_client(args: tuple, client: AsyncClient) -> tuple:
    return args[1:] if args and args[0] is client else args


@pytest.mark.asyncio
async def test_async_create_llm_evaluator_posts_payload() -> None:
    evaluator_id = uuid.uuid4()
    mock_response = MagicMock(status_code=200)
    mock_response.json.return_value = {
        "evaluator": _online_evaluator_response(evaluator_id)
    }
    client = AsyncClient(api_url="http://localhost:1984", api_key="test")

    with patch.object(
        AsyncClient, "_arequest_with_retries", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response
        evaluator = await client.create_llm_evaluator(
            name="quality judge",
            prompt_repo_handle="owner/quality-judge",
            feedback_keys=["quality"],
            variable_mapping={"input": "inputs.question"},
            commit_hash_or_tag="latest",
            run_rules=[{"session_name": "default", "trace_count": 10}],
        )

    assert evaluator.id == evaluator_id
    mock_request.assert_awaited_once()
    request_args = _without_bound_client(mock_request.call_args.args, client)
    assert request_args[:2] == ("POST", "/v1/platform/evaluators")
    body = json.loads(mock_request.call_args.kwargs["content"])
    assert body == {
        "name": "quality judge",
        "type": "llm",
        "feedback_keys": ["quality"],
        "llm_evaluator": {
            "prompt_repo_handle": "owner/quality-judge",
            "variable_mapping": {"input": "inputs.question"},
            "commit_hash_or_tag": "latest",
        },
        "run_rules": [
            {
                "session_name": "default",
                "use_corrections_dataset": False,
                "trace_count": 10,
            }
        ],
    }


@pytest.mark.asyncio
async def test_async_update_code_evaluator_patches_payload() -> None:
    evaluator_id = uuid.uuid4()
    mock_response = MagicMock(status_code=200)
    mock_response.json.return_value = {
        "evaluator": _online_evaluator_response(evaluator_id, evaluator_type="code")
    }
    client = AsyncClient(api_url="http://localhost:1984", api_key="test")

    with patch.object(
        AsyncClient, "_arequest_with_retries", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response
        evaluator = await client.update_code_evaluator(
            evaluator_id,
            name="updated judge",
            feedback_keys=["correctness"],
            code="def score(run): return False",
        )

    assert evaluator.type == "code"
    request_args = _without_bound_client(mock_request.call_args.args, client)
    assert request_args[:2] == (
        "PATCH",
        f"/v1/platform/evaluators/{evaluator_id}",
    )
    body = json.loads(mock_request.call_args.kwargs["content"])
    assert body == {
        "name": "updated judge",
        "feedback_keys": ["correctness"],
        "code_evaluator": {"code": "def score(run): return False"},
    }


@pytest.mark.asyncio
async def test_async_read_list_delete_evaluators() -> None:
    evaluator_id = uuid.uuid4()
    mock_response = MagicMock(status_code=200)
    mock_response.json.return_value = _online_evaluator_response(evaluator_id)
    client = AsyncClient(api_url="http://localhost:1984", api_key="test")

    with patch.object(
        AsyncClient, "_arequest_with_retries", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response
        evaluator = await client.read_evaluator(evaluator_id)

    assert evaluator.id == evaluator_id
    request_args = _without_bound_client(mock_request.call_args.args, client)
    assert request_args[:2] == ("GET", f"/v1/platform/evaluators/{evaluator_id}")

    with patch.object(
        AsyncClient, "_arequest_with_retries", new_callable=AsyncMock
    ) as mock_request:
        list_response = MagicMock(status_code=200)
        list_response.json.return_value = {
            "evaluators": [_online_evaluator_response(evaluator_id)]
        }
        mock_request.return_value = list_response
        evaluators = [
            evaluator
            async for evaluator in client.list_evaluators(
                evaluator_ids=[evaluator_id],
                evaluator_type="llm",
                sort_by="created_at",
                sort_by_desc=True,
                limit=1,
            )
        ]

    assert [evaluator.id for evaluator in evaluators] == [evaluator_id]
    request_args = _without_bound_client(mock_request.call_args.args, client)
    assert request_args[:2] == ("GET", "/v1/platform/evaluators")
    assert mock_request.call_args.kwargs["params"]["evaluator_id"] == [evaluator_id]
    assert mock_request.call_args.kwargs["params"]["type"] == "llm"
    assert mock_request.call_args.kwargs["params"]["sort_by"] == "created_at"
    assert mock_request.call_args.kwargs["params"]["sort_by_desc"] is True
    assert mock_request.call_args.kwargs["params"]["limit"] == 1

    with patch.object(
        AsyncClient, "_arequest_with_retries", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response
        await client.delete_evaluator(evaluator_id)

    request_args = _without_bound_client(mock_request.call_args.args, client)
    assert request_args[:2] == (
        "DELETE",
        f"/v1/platform/evaluators/{evaluator_id}",
    )
