import uuid

import pytest

import langsmith.schemas as ls_schemas
import langsmith.utils as ls_utils
from langsmith.async_client import AsyncClient
from tests.integration_tests.conftest import skip_if_rate_limited


@pytest.fixture
def langsmith_client() -> AsyncClient:
    return AsyncClient(timeout_ms=(50_000, 90_000))


@pytest.fixture
def agent_identifier() -> str:
    return f"-/ctx-test-async-agent-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def skill_identifier() -> str:
    return f"-/ctx-test-async-skill-{uuid.uuid4().hex[:8]}"


@skip_if_rate_limited
async def test_push_and_pull_agent_roundtrip(
    langsmith_client: AsyncClient, agent_identifier: str
) -> None:
    ctx = langsmith_client
    try:
        url = await ctx.push_agent(
            agent_identifier,
            files={"AGENTS.md": ls_schemas.FileEntry(content="# Test Agent\n")},
            description="integration test agent",
        )
        assert "/hub/" in url

        agent = await ctx.pull_agent(agent_identifier)
        assert isinstance(agent, ls_schemas.AgentContext)
        assert "AGENTS.md" in agent.files
        entry = agent.files["AGENTS.md"]
        assert isinstance(entry, ls_schemas.FileEntry)
        assert entry.content == "# Test Agent\n"
    finally:
        try:
            await ctx.delete_agent(agent_identifier)
        except Exception:
            pass


@skip_if_rate_limited
async def test_push_and_pull_skill_roundtrip(
    langsmith_client: AsyncClient, skill_identifier: str
) -> None:
    ctx = langsmith_client
    try:
        url = await ctx.push_skill(
            skill_identifier,
            files={"SKILL.md": ls_schemas.FileEntry(content="# Test Skill\n")},
            description="integration test skill",
        )
        assert "/hub/" in url

        skill = await ctx.pull_skill(skill_identifier)
        assert isinstance(skill, ls_schemas.SkillContext)
        assert "SKILL.md" in skill.files
        entry = skill.files["SKILL.md"]
        assert isinstance(entry, ls_schemas.FileEntry)
        assert entry.content == "# Test Skill\n"
    finally:
        try:
            await ctx.delete_skill(skill_identifier)
        except Exception:
            pass


@skip_if_rate_limited
async def test_agent_exists_reflects_create_delete_lifecycle(
    langsmith_client: AsyncClient, agent_identifier: str
) -> None:
    ctx = langsmith_client
    try:
        assert await ctx.agent_exists(agent_identifier) is False

        await ctx.push_agent(
            agent_identifier,
            files={"AGENTS.md": ls_schemas.FileEntry(content="x")},
        )
        assert await ctx.agent_exists(agent_identifier) is True

        await ctx.delete_agent(agent_identifier)
        assert await ctx.agent_exists(agent_identifier) is False
    finally:
        try:
            await ctx.delete_agent(agent_identifier)
        except Exception:
            pass


@skip_if_rate_limited
async def test_skill_exists_reflects_create_delete_lifecycle(
    langsmith_client: AsyncClient, skill_identifier: str
) -> None:
    ctx = langsmith_client
    try:
        assert await ctx.skill_exists(skill_identifier) is False

        await ctx.push_skill(
            skill_identifier,
            files={"SKILL.md": ls_schemas.FileEntry(content="x")},
        )
        assert await ctx.skill_exists(skill_identifier) is True

        await ctx.delete_skill(skill_identifier)
        assert await ctx.skill_exists(skill_identifier) is False
    finally:
        try:
            await ctx.delete_skill(skill_identifier)
        except Exception:
            pass


@skip_if_rate_limited
async def test_push_agent_null_entry_deletes_file(
    langsmith_client: AsyncClient, agent_identifier: str
) -> None:
    ctx = langsmith_client
    try:
        await ctx.push_agent(
            agent_identifier,
            files={
                "keep.md": ls_schemas.FileEntry(content="keep"),
                "remove.md": ls_schemas.FileEntry(content="remove"),
            },
        )
        agent = await ctx.pull_agent(agent_identifier)
        assert "keep.md" in agent.files
        assert "remove.md" in agent.files

        await ctx.push_agent(agent_identifier, files={"remove.md": None})
        agent = await ctx.pull_agent(agent_identifier)
        assert "keep.md" in agent.files
        assert "remove.md" not in agent.files
    finally:
        try:
            await ctx.delete_agent(agent_identifier)
        except Exception:
            pass


@skip_if_rate_limited
async def test_push_agent_second_commit_updates_content(
    langsmith_client: AsyncClient, agent_identifier: str
) -> None:
    ctx = langsmith_client
    try:
        await ctx.push_agent(
            agent_identifier,
            files={"AGENTS.md": ls_schemas.FileEntry(content="v1")},
        )
        await ctx.push_agent(
            agent_identifier,
            files={"AGENTS.md": ls_schemas.FileEntry(content="v2")},
        )

        agent = await ctx.pull_agent(agent_identifier)
        entry = agent.files["AGENTS.md"]
        assert isinstance(entry, ls_schemas.FileEntry)
        assert entry.content == "v2"
    finally:
        try:
            await ctx.delete_agent(agent_identifier)
        except Exception:
            pass


@skip_if_rate_limited
async def test_delete_agent_removes_repo(
    langsmith_client: AsyncClient, agent_identifier: str
) -> None:
    ctx = langsmith_client
    await ctx.push_agent(
        agent_identifier,
        files={"AGENTS.md": ls_schemas.FileEntry(content="x")},
    )
    await ctx.pull_agent(agent_identifier)

    await ctx.delete_agent(agent_identifier)

    with pytest.raises(ls_utils.LangSmithNotFoundError):
        await ctx.pull_agent(agent_identifier)


@skip_if_rate_limited
async def test_list_agents_returns_pushed_agent(
    langsmith_client: AsyncClient, agent_identifier: str
) -> None:
    ctx = langsmith_client
    _, handle = agent_identifier.split("/", 1)
    try:
        await ctx.push_agent(
            agent_identifier,
            files={"AGENTS.md": ls_schemas.FileEntry(content="x")},
        )
        response = await ctx.list_agents(query=handle)
        assert any(repo.repo_handle == handle for repo in response.repos)
    finally:
        try:
            await ctx.delete_agent(agent_identifier)
        except Exception:
            pass


@skip_if_rate_limited
async def test_delete_skill_removes_repo(
    langsmith_client: AsyncClient, skill_identifier: str
) -> None:
    ctx = langsmith_client
    await ctx.push_skill(
        skill_identifier,
        files={"SKILL.md": ls_schemas.FileEntry(content="x")},
    )
    await ctx.pull_skill(skill_identifier)

    await ctx.delete_skill(skill_identifier)

    with pytest.raises(ls_utils.LangSmithNotFoundError):
        await ctx.pull_skill(skill_identifier)


@skip_if_rate_limited
async def test_list_skills_returns_pushed_skill(
    langsmith_client: AsyncClient, skill_identifier: str
) -> None:
    ctx = langsmith_client
    _, handle = skill_identifier.split("/", 1)
    try:
        await ctx.push_skill(
            skill_identifier,
            files={"SKILL.md": ls_schemas.FileEntry(content="x")},
        )
        response = await ctx.list_skills(query=handle)
        assert any(repo.repo_handle == handle for repo in response.repos)
    finally:
        try:
            await ctx.delete_skill(skill_identifier)
        except Exception:
            pass
