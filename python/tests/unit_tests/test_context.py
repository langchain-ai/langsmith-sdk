"""Test the Context and AsyncContext classes for Hub non-prompt repos."""

from unittest.mock import AsyncMock, MagicMock

import pydantic
import pytest

from langsmith import schemas as ls_schemas
from langsmith import utils as ls_utils
from langsmith.context import AsyncContext, Context


def _mock_sync_client() -> MagicMock:
    client = MagicMock()
    client._host_url = "https://smith.langchain.com"
    client._current_tenant_is_owner.return_value = True
    client._owner_conflict_error.return_value = ls_utils.LangSmithUserError(
        "owner mismatch"
    )
    return client


def _mock_async_client() -> MagicMock:
    client = MagicMock()
    client._host_url = "https://smith.langchain.com"
    client._current_tenant_is_owner = AsyncMock(return_value=True)
    client._owner_conflict_error = AsyncMock(
        return_value=ls_utils.LangSmithUserError("owner mismatch")
    )
    client._arequest_with_retries = AsyncMock()
    return client


def _response(data: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = data
    return resp


def test_entry_discriminator_picks_file() -> None:
    adapter = pydantic.TypeAdapter(ls_schemas.Entry)
    entry = adapter.validate_python({"type": "file", "content": "hi"})
    assert isinstance(entry, ls_schemas.FileEntry)
    assert entry.content == "hi"


def test_entry_discriminator_picks_agent() -> None:
    adapter = pydantic.TypeAdapter(ls_schemas.Entry)
    entry = adapter.validate_python({"type": "agent", "repo_handle": "o/r"})
    assert isinstance(entry, ls_schemas.AgentEntry)
    assert entry.repo_handle == "o/r"


def test_entry_discriminator_picks_skill() -> None:
    adapter = pydantic.TypeAdapter(ls_schemas.Entry)
    entry = adapter.validate_python({"type": "skill", "repo_handle": "o/r"})
    assert isinstance(entry, ls_schemas.SkillEntry)


def test_agent_entry_exclude_none_strips_response_only_fields() -> None:
    entry = ls_schemas.AgentEntry(repo_handle="owner/repo")
    dumped = entry.model_dump(exclude_none=True)
    assert dumped == {"type": "agent", "repo_handle": "owner/repo"}
    assert "owner" not in dumped
    assert "commit_hash" not in dumped
    assert "commit_id" not in dumped


def test_push_agent_rejects_too_many_files() -> None:
    ctx = Context(_mock_sync_client())
    too_many = {f"p_{i}.py": ls_schemas.FileEntry(content="x") for i in range(501)}
    with pytest.raises(ls_utils.LangSmithUserError, match="Too many files"):
        ctx.push_agent("-/repo", files=too_many)


def test_push_agent_rejects_short_parent_commit() -> None:
    ctx = Context(_mock_sync_client())
    with pytest.raises(ls_utils.LangSmithUserError, match="8-64"):
        ctx.push_agent("-/repo", files={}, parent_commit="abc")


def test_push_agent_rejects_invalid_handle_on_create() -> None:
    client = _mock_sync_client()
    client.request_with_retries.side_effect = ls_utils.LangSmithNotFoundError(
        "not found"
    )
    ctx = Context(client)
    with pytest.raises(ls_utils.LangSmithUserError, match="Invalid repo_handle"):
        ctx.push_agent(
            "-/BadName",
            files={"main.py": ls_schemas.FileEntry(content="x")},
        )


def test_pull_agent_hits_correct_url_and_parses() -> None:
    client = _mock_sync_client()
    client.request_with_retries.return_value = _response(
        {
            "commit_id": "00000000-0000-0000-0000-000000000000",
            "commit_hash": "abc12345",
            "files": {"main.py": {"type": "file", "content": "print('hi')"}},
        }
    )
    ctx = Context(client)
    agent = ctx.pull_agent("owner/my-agent")
    call = client.request_with_retries.call_args
    assert call.args == ("GET", "/api/v1/platform/hub/repos/owner/my-agent/directories")
    assert call.kwargs.get("params") == {}
    assert isinstance(agent, ls_schemas.AgentContext)
    assert agent.owner == "owner"
    assert agent.repo == "my-agent"
    assert agent.commit_hash == "abc12345"
    assert isinstance(agent.files["main.py"], ls_schemas.FileEntry)


def test_pull_skill_and_file_return_correct_types() -> None:
    client = _mock_sync_client()
    client.request_with_retries.return_value = _response(
        {
            "commit_id": "00000000-0000-0000-0000-000000000000",
            "commit_hash": "xyz12345",
            "files": {},
        }
    )
    ctx = Context(client)
    assert isinstance(ctx.pull_skill("o/s"), ls_schemas.SkillContext)
    assert isinstance(ctx.pull_file("o/f"), ls_schemas.FileContext)


def test_pull_agent_with_version_passes_commit_param() -> None:
    client = _mock_sync_client()
    client.request_with_retries.return_value = _response(
        {
            "commit_id": "00000000-0000-0000-0000-000000000000",
            "commit_hash": "abc12345",
            "files": {},
        }
    )
    ctx = Context(client)
    ctx.pull_agent("owner/repo", version="abc12345")
    assert client.request_with_retries.call_args.kwargs["params"] == {
        "commit": "abc12345"
    }


def test_push_agent_creates_new_repo_and_commits() -> None:
    client = _mock_sync_client()
    client.request_with_retries.side_effect = [
        ls_utils.LangSmithNotFoundError("not found"),
        _response({}),
        _response(
            {
                "commit": {
                    "id": "00000000-0000-0000-0000-000000000000",
                    "commit_hash": "abc12345",
                }
            }
        ),
    ]
    ctx = Context(client)
    url = ctx.push_agent(
        "-/my-agent", files={"main.py": ls_schemas.FileEntry(content="x")}
    )
    assert url == "https://smith.langchain.com/hub/-/my-agent:abc12345"
    assert client.request_with_retries.call_count == 3

    create_call = client.request_with_retries.call_args_list[1]
    assert create_call.args == ("POST", "/api/v1/repos/")
    assert create_call.kwargs["json"]["repo_type"] == "agent"
    assert create_call.kwargs["json"]["repo_handle"] == "my-agent"

    commit_call = client.request_with_retries.call_args_list[2]
    assert commit_call.args == (
        "POST",
        "/api/v1/platform/hub/repos/-/my-agent/directories/commits",
    )
    assert commit_call.kwargs["json"]["files"] == {
        "main.py": {"type": "file", "content": "x"}
    }


def test_push_agent_updates_metadata_when_repo_exists() -> None:
    client = _mock_sync_client()
    client.request_with_retries.side_effect = [
        _response({}),
        _response({}),
        _response(
            {
                "commit": {
                    "id": "00000000-0000-0000-0000-000000000000",
                    "commit_hash": "abc12345",
                }
            }
        ),
    ]
    ctx = Context(client)
    ctx.push_agent(
        "-/my-agent",
        files={"main.py": ls_schemas.FileEntry(content="x")},
        description="new desc",
    )
    assert client.request_with_retries.call_count == 3
    patch_call = client.request_with_retries.call_args_list[1]
    assert patch_call.args == ("PATCH", "/api/v1/hub/repos/-/my-agent")
    assert patch_call.kwargs["json"] == {"description": "new desc"}


def test_push_agent_null_entry_serializes_as_delete() -> None:
    client = _mock_sync_client()
    client.request_with_retries.side_effect = [
        _response({}),
        _response(
            {
                "commit": {
                    "id": "00000000-0000-0000-0000-000000000000",
                    "commit_hash": "abc12345",
                }
            }
        ),
    ]
    ctx = Context(client)
    ctx.push_agent(
        "-/my-agent",
        files={
            "keep.py": ls_schemas.FileEntry(content="x"),
            "remove.py": None,
        },
    )
    commit_call = client.request_with_retries.call_args_list[1]
    body = commit_call.kwargs["json"]
    assert body["files"]["keep.py"] == {"type": "file", "content": "x"}
    assert body["files"]["remove.py"] is None


def test_push_agent_passes_parent_commit_when_provided() -> None:
    client = _mock_sync_client()
    client.request_with_retries.side_effect = [
        _response({}),
        _response(
            {
                "commit": {
                    "id": "00000000-0000-0000-0000-000000000000",
                    "commit_hash": "new12345",
                }
            }
        ),
    ]
    ctx = Context(client)
    ctx.push_agent(
        "-/my-agent",
        files={"main.py": ls_schemas.FileEntry(content="x")},
        parent_commit="abc12345",
    )
    commit_call = client.request_with_retries.call_args_list[1]
    assert commit_call.kwargs["json"]["parent_commit"] == "abc12345"


def test_delete_agent_hits_directories_delete() -> None:
    client = _mock_sync_client()
    client.request_with_retries.return_value = _response({})
    ctx = Context(client)
    ctx.delete_agent("-/old-agent")
    call = client.request_with_retries.call_args
    assert call.args == (
        "DELETE",
        "/api/v1/platform/hub/repos/-/old-agent/directories",
    )


def test_list_agents_passes_repo_type_filter() -> None:
    client = _mock_sync_client()
    client.request_with_retries.return_value = _response({"repos": [], "total": 0})
    ctx = Context(client)
    ctx.list_agents(limit=50, is_public=True, query="foo")
    call = client.request_with_retries.call_args
    assert call.args == ("GET", "/api/v1/hub/repos")
    params = call.kwargs["params"]
    assert params["repo_type"] == "agent"
    assert params["limit"] == 50
    assert params["is_public"] == "true"
    assert params["query"] == "foo"
    assert params["match_prefix"] == "true"


async def test_async_pull_agent_parses_and_merges_identifier() -> None:
    client = _mock_async_client()
    client._arequest_with_retries.return_value = _response(
        {
            "commit_id": "00000000-0000-0000-0000-000000000000",
            "commit_hash": "abc12345",
            "files": {"main.py": {"type": "file", "content": "hi"}},
        }
    )
    ctx = AsyncContext(client)
    agent = await ctx.pull_agent("owner/my-agent")
    assert isinstance(agent, ls_schemas.AgentContext)
    assert agent.owner == "owner"
    assert agent.repo == "my-agent"
    client._arequest_with_retries.assert_awaited_once_with(
        "GET",
        "/api/v1/platform/hub/repos/owner/my-agent/directories",
        params={},
    )


async def test_async_push_agent_creates_and_commits() -> None:
    client = _mock_async_client()
    client._arequest_with_retries.side_effect = [
        ls_utils.LangSmithNotFoundError("not found"),
        _response({}),
        _response(
            {
                "commit": {
                    "id": "00000000-0000-0000-0000-000000000000",
                    "commit_hash": "abc12345",
                }
            }
        ),
    ]
    ctx = AsyncContext(client)
    url = await ctx.push_agent(
        "-/my-agent", files={"main.py": ls_schemas.FileEntry(content="x")}
    )
    assert url == "https://smith.langchain.com/hub/-/my-agent:abc12345"
    assert client._arequest_with_retries.await_count == 3


async def test_async_delete_agent_hits_directories_delete() -> None:
    client = _mock_async_client()
    client._arequest_with_retries.return_value = _response({})
    ctx = AsyncContext(client)
    await ctx.delete_agent("-/old-agent")
    client._arequest_with_retries.assert_awaited_once_with(
        "DELETE",
        "/api/v1/platform/hub/repos/-/old-agent/directories",
    )


async def test_async_list_skills_passes_filter() -> None:
    client = _mock_async_client()
    client._arequest_with_retries.return_value = _response({"repos": [], "total": 0})
    ctx = AsyncContext(client)
    await ctx.list_skills(limit=25)
    call = client._arequest_with_retries.call_args
    assert call.args == ("GET", "/api/v1/hub/repos")
    assert call.kwargs["params"]["repo_type"] == "skill"
    assert call.kwargs["params"]["limit"] == 25


async def test_async_push_agent_rejects_too_many_files() -> None:
    ctx = AsyncContext(_mock_async_client())
    too_many = {f"p_{i}.py": ls_schemas.FileEntry(content="x") for i in range(501)}
    with pytest.raises(ls_utils.LangSmithUserError, match="Too many files"):
        await ctx.push_agent("-/repo", files=too_many)
