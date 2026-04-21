"""Test the Context and AsyncContext classes for Hub non-prompt repos."""

import json

from unittest.mock import AsyncMock, MagicMock

import pydantic
import pytest

from langsmith import schemas as ls_schemas
from langsmith import utils as ls_utils
from langsmith.context import AsyncContext, Context


TOOLS_JSON = json.dumps(
    {
        "tools": [{"name": "read_file", "type": "builtin"}],
        "interrupt_config": {},
    }
)


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


@pytest.mark.parametrize(
    "handle,valid",
    [
        ("a", True),
        ("foo_bar-baz1", True),
        ("BadName", False),
        ("1agent", False),
        ("-agent", False),
        ("agent.name", False),
    ],
)
def test_repo_handle_pattern(handle: str, valid: bool) -> None:
    from langsmith.context import _REPO_HANDLE_PATTERN

    assert bool(_REPO_HANDLE_PATTERN.match(handle)) is valid


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
    assert call.args == ("GET", "/v1/platform/hub/repos/owner/my-agent/directories")
    assert call.kwargs.get("params") == {}
    assert isinstance(agent, ls_schemas.AgentContext)
    assert agent.owner == "owner"
    assert agent.repo == "my-agent"
    assert agent.commit_hash == "abc12345"
    assert isinstance(agent.files["main.py"], ls_schemas.FileEntry)


def test_pull_skill_returns_skill_context() -> None:
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
    assert create_call.args == ("POST", "/repos/")
    assert create_call.kwargs["json"]["repo_type"] == "agent"
    assert create_call.kwargs["json"]["repo_handle"] == "my-agent"

    commit_call = client.request_with_retries.call_args_list[2]
    assert commit_call.args == (
        "POST",
        "/v1/platform/hub/repos/-/my-agent/directories/commits",
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
    assert patch_call.args == ("PATCH", "/repos/-/my-agent")
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


def test_push_agent_accepts_tools_json_as_normal_file_entry() -> None:
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
        files={"tools.json": ls_schemas.FileEntry(content=TOOLS_JSON)},
    )
    commit_call = client.request_with_retries.call_args_list[1]
    assert commit_call.kwargs["json"]["files"] == {
        "tools.json": {"type": "file", "content": TOOLS_JSON}
    }


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
        "/v1/platform/hub/repos/-/old-agent/directories",
    )


def test_agent_exists_returns_true_on_200() -> None:
    client = _mock_sync_client()
    client.request_with_retries.return_value = _response({})
    ctx = Context(client)
    assert ctx.agent_exists("-/my-agent") is True


def test_agent_exists_returns_false_on_not_found() -> None:
    client = _mock_sync_client()
    client.request_with_retries.side_effect = ls_utils.LangSmithNotFoundError(
        "not found"
    )
    ctx = Context(client)
    assert ctx.agent_exists("-/nope") is False


def test_skill_exists_returns_true_on_200() -> None:
    client = _mock_sync_client()
    client.request_with_retries.return_value = _response({})
    ctx = Context(client)
    assert ctx.skill_exists("-/my-skill") is True


def test_skill_exists_returns_false_on_not_found() -> None:
    client = _mock_sync_client()
    client.request_with_retries.side_effect = ls_utils.LangSmithNotFoundError(
        "not found"
    )
    ctx = Context(client)
    assert ctx.skill_exists("-/nope") is False


def test_list_agents_passes_repo_type_filter() -> None:
    client = _mock_sync_client()
    client.request_with_retries.return_value = _response({"repos": [], "total": 0})
    ctx = Context(client)
    ctx.list_agents(limit=50, is_public=True, query="foo")
    call = client.request_with_retries.call_args
    assert call.args == ("GET", "/repos")
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
        "/v1/platform/hub/repos/owner/my-agent/directories",
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


async def test_async_push_agent_accepts_tools_json_as_normal_file_entry() -> None:
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
    await ctx.push_agent(
        "-/my-agent",
        files={"tools.json": ls_schemas.FileEntry(content=TOOLS_JSON)},
    )
    commit_call = client._arequest_with_retries.call_args_list[2]
    assert commit_call.kwargs["json"]["files"] == {
        "tools.json": {"type": "file", "content": TOOLS_JSON}
    }


async def test_async_create_repo_swallows_conflict() -> None:
    client = _mock_async_client()
    client._arequest_with_retries.side_effect = [
        ls_utils.LangSmithNotFoundError("not found"),  # _repo_exists
        ls_utils.LangSmithConflictError("already exists"),  # _create_repo race
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
        "/v1/platform/hub/repos/-/old-agent/directories",
    )


async def test_async_agent_exists_returns_true_on_200() -> None:
    client = _mock_async_client()
    client._arequest_with_retries.return_value = _response({})
    ctx = AsyncContext(client)
    assert await ctx.agent_exists("-/my-agent") is True


async def test_async_agent_exists_returns_false_on_not_found() -> None:
    client = _mock_async_client()
    client._arequest_with_retries.side_effect = ls_utils.LangSmithNotFoundError(
        "not found"
    )
    ctx = AsyncContext(client)
    assert await ctx.agent_exists("-/nope") is False


async def test_async_skill_exists_returns_true_on_200() -> None:
    client = _mock_async_client()
    client._arequest_with_retries.return_value = _response({})
    ctx = AsyncContext(client)
    assert await ctx.skill_exists("-/my-skill") is True


async def test_async_skill_exists_returns_false_on_not_found() -> None:
    client = _mock_async_client()
    client._arequest_with_retries.side_effect = ls_utils.LangSmithNotFoundError(
        "not found"
    )
    ctx = AsyncContext(client)
    assert await ctx.skill_exists("-/nope") is False


async def test_async_list_skills_passes_filter() -> None:
    client = _mock_async_client()
    client._arequest_with_retries.return_value = _response({"repos": [], "total": 0})
    ctx = AsyncContext(client)
    await ctx.list_skills(limit=25)
    call = client._arequest_with_retries.call_args
    assert call.args == ("GET", "/repos")
    assert call.kwargs["params"]["repo_type"] == "skill"
    assert call.kwargs["params"]["limit"] == 25
