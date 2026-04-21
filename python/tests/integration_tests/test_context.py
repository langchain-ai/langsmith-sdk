import json
import uuid

import pytest

import langsmith.schemas as ls_schemas
import langsmith.utils as ls_utils
from langsmith.client import Client
from tests.integration_tests.conftest import skip_if_rate_limited


TOOLS_JSON = json.dumps(
    {
        "tools": [{"name": "read_file", "type": "builtin"}],
        "interrupt_config": {},
    }
)


@pytest.fixture
def langsmith_client() -> Client:
    return Client(timeout_ms=(50_000, 90_000))


@pytest.fixture
def agent_identifier() -> str:
    return f"-/ctx-test-agent-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def skill_identifier() -> str:
    return f"-/ctx-test-skill-{uuid.uuid4().hex[:8]}"


@skip_if_rate_limited
def test_push_and_pull_agent_roundtrip(
    langsmith_client: Client, agent_identifier: str
) -> None:
    ctx = langsmith_client.context
    try:
        url = ctx.push_agent(
            agent_identifier,
            files={"AGENTS.md": ls_schemas.FileEntry(content="# Test Agent\n")},
            description="integration test agent",
        )
        assert "/hub/" in url

        agent = ctx.pull_agent(agent_identifier)
        assert isinstance(agent, ls_schemas.AgentContext)
        assert "AGENTS.md" in agent.files
        entry = agent.files["AGENTS.md"]
        assert isinstance(entry, ls_schemas.FileEntry)
        assert entry.content == "# Test Agent\n"
    finally:
        try:
            ctx.delete_agent(agent_identifier)
        except Exception:
            pass


@skip_if_rate_limited
def test_push_and_pull_agent_tools_json_roundtrip(
    langsmith_client: Client, agent_identifier: str
) -> None:
    ctx = langsmith_client.context
    try:
        url = ctx.push_agent(
            agent_identifier,
            files={"tools.json": ls_schemas.FileEntry(content=TOOLS_JSON)},
            description="integration test agent tools",
        )
        assert "/hub/" in url

        agent = ctx.pull_agent(agent_identifier)
        assert isinstance(agent, ls_schemas.AgentContext)
        assert "tools.json" in agent.files
        entry = agent.files["tools.json"]
        assert isinstance(entry, ls_schemas.FileEntry)
        assert entry.content == TOOLS_JSON
    finally:
        try:
            ctx.delete_agent(agent_identifier)
        except Exception:
            pass


@skip_if_rate_limited
def test_push_and_pull_skill_roundtrip(
    langsmith_client: Client, skill_identifier: str
) -> None:
    ctx = langsmith_client.context
    try:
        url = ctx.push_skill(
            skill_identifier,
            files={"SKILL.md": ls_schemas.FileEntry(content="# Test Skill\n")},
            description="integration test skill",
        )
        assert "/hub/" in url

        skill = ctx.pull_skill(skill_identifier)
        assert isinstance(skill, ls_schemas.SkillContext)
        assert "SKILL.md" in skill.files
        entry = skill.files["SKILL.md"]
        assert isinstance(entry, ls_schemas.FileEntry)
        assert entry.content == "# Test Skill\n"
    finally:
        try:
            ctx.delete_skill(skill_identifier)
        except Exception:
            pass


@skip_if_rate_limited
def test_agent_exists_reflects_create_delete_lifecycle(
    langsmith_client: Client, agent_identifier: str
) -> None:
    ctx = langsmith_client.context
    try:
        assert ctx.agent_exists(agent_identifier) is False

        ctx.push_agent(
            agent_identifier,
            files={"AGENTS.md": ls_schemas.FileEntry(content="x")},
        )
        assert ctx.agent_exists(agent_identifier) is True

        ctx.delete_agent(agent_identifier)
        assert ctx.agent_exists(agent_identifier) is False
    finally:
        try:
            ctx.delete_agent(agent_identifier)
        except Exception:
            pass


@skip_if_rate_limited
def test_skill_exists_reflects_create_delete_lifecycle(
    langsmith_client: Client, skill_identifier: str
) -> None:
    ctx = langsmith_client.context
    try:
        assert ctx.skill_exists(skill_identifier) is False

        ctx.push_skill(
            skill_identifier,
            files={"SKILL.md": ls_schemas.FileEntry(content="x")},
        )
        assert ctx.skill_exists(skill_identifier) is True

        ctx.delete_skill(skill_identifier)
        assert ctx.skill_exists(skill_identifier) is False
    finally:
        try:
            ctx.delete_skill(skill_identifier)
        except Exception:
            pass


@skip_if_rate_limited
def test_push_agent_null_entry_deletes_file(
    langsmith_client: Client, agent_identifier: str
) -> None:
    ctx = langsmith_client.context
    try:
        ctx.push_agent(
            agent_identifier,
            files={
                "keep.md": ls_schemas.FileEntry(content="keep"),
                "remove.md": ls_schemas.FileEntry(content="remove"),
            },
        )
        agent = ctx.pull_agent(agent_identifier)
        assert "keep.md" in agent.files
        assert "remove.md" in agent.files

        ctx.push_agent(agent_identifier, files={"remove.md": None})
        agent = ctx.pull_agent(agent_identifier)
        assert "keep.md" in agent.files
        assert "remove.md" not in agent.files
    finally:
        try:
            ctx.delete_agent(agent_identifier)
        except Exception:
            pass


@skip_if_rate_limited
def test_push_agent_second_commit_updates_content(
    langsmith_client: Client, agent_identifier: str
) -> None:
    ctx = langsmith_client.context
    try:
        ctx.push_agent(
            agent_identifier,
            files={"AGENTS.md": ls_schemas.FileEntry(content="v1")},
        )
        ctx.push_agent(
            agent_identifier,
            files={"AGENTS.md": ls_schemas.FileEntry(content="v2")},
        )

        agent = ctx.pull_agent(agent_identifier)
        entry = agent.files["AGENTS.md"]
        assert isinstance(entry, ls_schemas.FileEntry)
        assert entry.content == "v2"
    finally:
        try:
            ctx.delete_agent(agent_identifier)
        except Exception:
            pass


@skip_if_rate_limited
def test_delete_agent_removes_repo(
    langsmith_client: Client, agent_identifier: str
) -> None:
    ctx = langsmith_client.context
    ctx.push_agent(
        agent_identifier,
        files={"AGENTS.md": ls_schemas.FileEntry(content="x")},
    )
    # confirm it exists
    ctx.pull_agent(agent_identifier)

    ctx.delete_agent(agent_identifier)

    with pytest.raises(ls_utils.LangSmithNotFoundError):
        ctx.pull_agent(agent_identifier)


@skip_if_rate_limited
def test_list_agents_returns_pushed_agent(
    langsmith_client: Client, agent_identifier: str
) -> None:
    ctx = langsmith_client.context
    _, handle = agent_identifier.split("/", 1)
    try:
        ctx.push_agent(
            agent_identifier,
            files={"AGENTS.md": ls_schemas.FileEntry(content="x")},
        )
        response = ctx.list_agents(query=handle)
        assert any(repo.repo_handle == handle for repo in response.repos)
    finally:
        try:
            ctx.delete_agent(agent_identifier)
        except Exception:
            pass


@skip_if_rate_limited
def test_delete_skill_removes_repo(
    langsmith_client: Client, skill_identifier: str
) -> None:
    ctx = langsmith_client.context
    ctx.push_skill(
        skill_identifier,
        files={"SKILL.md": ls_schemas.FileEntry(content="x")},
    )
    ctx.pull_skill(skill_identifier)

    ctx.delete_skill(skill_identifier)

    with pytest.raises(ls_utils.LangSmithNotFoundError):
        ctx.pull_skill(skill_identifier)


@skip_if_rate_limited
def test_list_skills_returns_pushed_skill(
    langsmith_client: Client, skill_identifier: str
) -> None:
    ctx = langsmith_client.context
    _, handle = skill_identifier.split("/", 1)
    try:
        ctx.push_skill(
            skill_identifier,
            files={"SKILL.md": ls_schemas.FileEntry(content="x")},
        )
        response = ctx.list_skills(query=handle)
        assert any(repo.repo_handle == handle for repo in response.repos)
    finally:
        try:
            ctx.delete_skill(skill_identifier)
        except Exception:
            pass
