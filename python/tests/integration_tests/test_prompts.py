from typing import Literal, Tuple
from uuid import uuid4

import pytest
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

import langsmith.schemas as ls_schemas
import langsmith.utils as ls_utils
from langsmith.client import Client


@pytest.fixture
def langsmith_client() -> Client:
    return Client(timeout_ms=Tuple[20_000, 90_000])


@pytest.fixture
def prompt_template_1() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_template("tell me a joke about {topic}")


@pytest.fixture
def prompt_template_2() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", "You are a helpful assistant."),
            ("human", "{question}"),
        ]
    )


@pytest.fixture
def prompt_template_3() -> PromptTemplate:
    return PromptTemplate.from_template("Summarize the following text: {text}")


def test_current_tenant_is_owner(langsmith_client: Client):
    settings = langsmith_client._get_settings()
    assert langsmith_client._current_tenant_is_owner(settings["tenant_handle"])
    assert langsmith_client._current_tenant_is_owner("-")
    assert not langsmith_client._current_tenant_is_owner("non_existent_owner")


def test_list_prompts(langsmith_client: Client):
    response = langsmith_client.list_prompts(limit=10, offset=0)
    assert isinstance(response, ls_schemas.ListPromptsResponse)
    assert len(response.repos) <= 10


def test_get_prompt(langsmith_client: Client, prompt_template_1: ChatPromptTemplate):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"
    langsmith_client.push_prompt(prompt_name, object=prompt_template_1)

    prompt = langsmith_client.get_prompt(prompt_name)
    assert isinstance(prompt, ls_schemas.Prompt)
    assert prompt.repo_handle == prompt_name

    langsmith_client.delete_prompt(prompt_name)


def test_prompt_exists(langsmith_client: Client, prompt_template_2: ChatPromptTemplate):
    non_existent_prompt = f"non_existent_{uuid4().hex[:8]}"
    assert not langsmith_client._prompt_exists(non_existent_prompt)

    existent_prompt = f"existent_{uuid4().hex[:8]}"
    langsmith_client.push_prompt(existent_prompt, object=prompt_template_2)
    assert langsmith_client._prompt_exists(existent_prompt)

    langsmith_client.delete_prompt(existent_prompt)


def test_update_prompt(langsmith_client: Client, prompt_template_1: ChatPromptTemplate):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"
    langsmith_client.push_prompt(prompt_name, object=prompt_template_1)

    updated_data = langsmith_client.update_prompt(
        prompt_name,
        description="Updated description",
        is_public=True,
        tags=["test", "update"],
    )
    assert isinstance(updated_data, dict)

    updated_prompt = langsmith_client.get_prompt(prompt_name)
    assert isinstance(updated_prompt, ls_schemas.Prompt)
    assert updated_prompt.description == "Updated description"
    assert updated_prompt.is_public
    assert set(updated_prompt.tags) == set(["test", "update"])

    langsmith_client.delete_prompt(prompt_name)


def test_delete_prompt(langsmith_client: Client, prompt_template_1: ChatPromptTemplate):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"
    langsmith_client.push_prompt(prompt_name, object=prompt_template_1)

    assert langsmith_client._prompt_exists(prompt_name)
    langsmith_client.delete_prompt(prompt_name)
    assert not langsmith_client._prompt_exists(prompt_name)


def test_pull_prompt_object(
    langsmith_client: Client, prompt_template_1: ChatPromptTemplate
):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"
    langsmith_client.push_prompt(prompt_name, object=prompt_template_1)

    manifest = langsmith_client.pull_prompt_object(prompt_name)
    assert isinstance(manifest, ls_schemas.PromptObject)
    assert manifest.repo == prompt_name

    langsmith_client.delete_prompt(prompt_name)


def test_pull_prompt(langsmith_client: Client, prompt_template_1: ChatPromptTemplate):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"
    langsmith_client.push_prompt(prompt_name, object=prompt_template_1)

    # test pulling with just prompt name
    pulled_prompt = langsmith_client.pull_prompt(prompt_name)
    assert isinstance(pulled_prompt, ChatPromptTemplate)
    assert (
        pulled_prompt.metadata and pulled_prompt.metadata["lc_hub_repo"] == prompt_name
    )

    # test pulling with private owner (-) and name
    pulled_prompt_2 = langsmith_client.pull_prompt(f"-/{prompt_name}")
    assert pulled_prompt == pulled_prompt_2

    # test pulling with tenant handle and name
    tenant_handle = langsmith_client._get_settings()["tenant_handle"]
    pulled_prompt_3 = langsmith_client.pull_prompt(f"{tenant_handle}/{prompt_name}")
    assert pulled_prompt.metadata and pulled_prompt_3.metadata
    assert (
        pulled_prompt.metadata["lc_hub_commit_hash"]
        == pulled_prompt_3.metadata["lc_hub_commit_hash"]
    )
    assert pulled_prompt_3.metadata["lc_hub_owner"] == tenant_handle

    # test pulling with handle, name and commit hash
    tenant_handle = langsmith_client._get_settings()["tenant_handle"]
    pulled_prompt_4 = langsmith_client.pull_prompt(
        f"{tenant_handle}/{prompt_name}:latest"
    )
    assert pulled_prompt_3 == pulled_prompt_4

    # test pulling without handle, with commit hash
    assert pulled_prompt_4.metadata
    pulled_prompt_5 = langsmith_client.pull_prompt(
        f"{prompt_name}:{pulled_prompt_4.metadata['lc_hub_commit_hash']}"
    )
    assert pulled_prompt_5.metadata
    assert (
        pulled_prompt_4.metadata["lc_hub_commit_hash"]
        == pulled_prompt_5.metadata["lc_hub_commit_hash"]
    )

    langsmith_client.delete_prompt(prompt_name)


def test_push_and_pull_prompt(
    langsmith_client: Client, prompt_template_2: ChatPromptTemplate
):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"

    push_result = langsmith_client.push_prompt(prompt_name, object=prompt_template_2)
    assert isinstance(push_result, str)

    pulled_prompt = langsmith_client.pull_prompt(prompt_name)
    assert isinstance(pulled_prompt, ChatPromptTemplate)

    langsmith_client.delete_prompt(prompt_name)

    # should fail
    with pytest.raises(ls_utils.LangSmithUserError):
        langsmith_client.push_prompt(
            f"random_handle/{prompt_name}", object=prompt_template_2
        )


def test_like_unlike_prompt(
    langsmith_client: Client, prompt_template_1: ChatPromptTemplate
):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"
    langsmith_client.push_prompt(prompt_name, object=prompt_template_1)

    langsmith_client.like_prompt(prompt_name)
    prompt = langsmith_client.get_prompt(prompt_name)
    assert isinstance(prompt, ls_schemas.Prompt)
    assert prompt.num_likes == 1

    langsmith_client.unlike_prompt(prompt_name)
    prompt = langsmith_client.get_prompt(prompt_name)
    assert isinstance(prompt, ls_schemas.Prompt)
    assert prompt.num_likes == 0

    langsmith_client.delete_prompt(prompt_name)


def test_get_latest_commit_hash(
    langsmith_client: Client, prompt_template_1: ChatPromptTemplate
):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"
    langsmith_client.push_prompt(prompt_name, object=prompt_template_1)

    commit_hash = langsmith_client._get_latest_commit_hash(f"-/{prompt_name}")
    assert isinstance(commit_hash, str)
    assert len(commit_hash) > 0

    langsmith_client.delete_prompt(prompt_name)


def test_create_prompt(langsmith_client: Client):
    prompt_name = f"test_create_prompt_{uuid4().hex[:8]}"
    created_prompt = langsmith_client.create_prompt(
        prompt_name,
        description="Test description",
        readme="Test readme",
        tags=["test", "create"],
        is_public=False,
    )
    assert isinstance(created_prompt, ls_schemas.Prompt)
    assert created_prompt.repo_handle == prompt_name
    assert created_prompt.description == "Test description"
    assert created_prompt.readme == "Test readme"
    assert set(created_prompt.tags) == set(["test", "create"])
    assert not created_prompt.is_public

    langsmith_client.delete_prompt(prompt_name)


def test_create_commit(
    langsmith_client: Client,
    prompt_template_2: ChatPromptTemplate,
    prompt_template_3: PromptTemplate,
):
    prompt_name = f"test_create_commit_{uuid4().hex[:8]}"
    try:
        # this should fail because the prompt does not exist
        commit_url = langsmith_client.create_commit(
            prompt_name, object=prompt_template_2
        )
        pytest.fail("Expected LangSmithNotFoundError was not raised")
    except ls_utils.LangSmithNotFoundError as e:
        assert str(e) == "Prompt does not exist, you must create it first."
    except Exception as e:
        pytest.fail(f"Unexpected exception raised: {e}")

    langsmith_client.push_prompt(prompt_name, object=prompt_template_3)
    commit_url = langsmith_client.create_commit(prompt_name, object=prompt_template_2)
    assert isinstance(commit_url, str)
    assert prompt_name in commit_url

    prompt = langsmith_client.get_prompt(prompt_name)
    assert isinstance(prompt, ls_schemas.Prompt)
    assert prompt.num_commits == 2

    langsmith_client.delete_prompt(prompt_name)


def test_push_prompt(langsmith_client: Client, prompt_template_3: PromptTemplate):
    prompt_name = f"test_push_new_{uuid4().hex[:8]}"
    url = langsmith_client.push_prompt(
        prompt_name,
        object=prompt_template_3,
        is_public=True,
        description="New prompt",
        tags=["new", "test"],
    )

    assert isinstance(url, str)
    assert prompt_name in url

    prompt = langsmith_client.get_prompt(prompt_name)
    assert isinstance(prompt, ls_schemas.Prompt)
    assert prompt.is_public
    assert prompt.description == "New prompt"
    assert "new" in prompt.tags
    assert "test" in prompt.tags
    assert prompt.num_commits == 1

    # test updating prompt metadata but not manifest
    url = langsmith_client.push_prompt(
        prompt_name,
        is_public=False,
        description="Updated prompt",
    )

    updated_prompt = langsmith_client.get_prompt(prompt_name)
    assert isinstance(updated_prompt, ls_schemas.Prompt)
    assert updated_prompt.description == "Updated prompt"
    assert not updated_prompt.is_public
    assert updated_prompt.num_commits == 1

    langsmith_client.delete_prompt(prompt_name)


@pytest.mark.parametrize("is_public,expected_count", [(True, 1), (False, 1)])
def test_list_prompts_filter(
    langsmith_client: Client,
    prompt_template_1: ChatPromptTemplate,
    is_public: bool,
    expected_count: int,
):
    prompt_name = f"test_list_filter_{uuid4().hex[:8]}"
    langsmith_client.push_prompt(
        prompt_name, object=prompt_template_1, is_public=is_public
    )

    response = langsmith_client.list_prompts(is_public=is_public, query=prompt_name)

    assert response.total == expected_count
    if expected_count > 0:
        assert response.repos[0].repo_handle == prompt_name

    langsmith_client.delete_prompt(prompt_name)


def test_update_prompt_archive(
    langsmith_client: Client, prompt_template_1: ChatPromptTemplate
):
    prompt_name = f"test_archive_{uuid4().hex[:8]}"
    langsmith_client.push_prompt(prompt_name, object=prompt_template_1)

    langsmith_client.update_prompt(prompt_name, is_archived=True)
    archived_prompt = langsmith_client.get_prompt(prompt_name)
    assert isinstance(archived_prompt, ls_schemas.Prompt)
    assert archived_prompt.is_archived

    langsmith_client.update_prompt(prompt_name, is_archived=False)
    unarchived_prompt = langsmith_client.get_prompt(prompt_name)
    assert isinstance(unarchived_prompt, ls_schemas.Prompt)
    assert not unarchived_prompt.is_archived

    langsmith_client.delete_prompt(prompt_name)


@pytest.mark.parametrize(
    "sort_field, sort_direction",
    [
        (ls_schemas.PromptSortField.updated_at, "desc"),
    ],
)
def test_list_prompts_sorting(
    langsmith_client: Client,
    prompt_template_1: ChatPromptTemplate,
    sort_field: ls_schemas.PromptSortField,
    sort_direction: Literal["asc", "desc"],
):
    prompt_names = [f"test_sort_{i}_{uuid4().hex[:8]}" for i in range(3)]
    for name in prompt_names:
        langsmith_client.push_prompt(name, object=prompt_template_1)

    response = langsmith_client.list_prompts(
        sort_field=sort_field, sort_direction=sort_direction, limit=10
    )

    assert len(response.repos) >= 3
    sorted_names = [
        repo.repo_handle for repo in response.repos if repo.repo_handle in prompt_names
    ]
    assert sorted_names == sorted(sorted_names, reverse=(sort_direction == "desc"))

    for name in prompt_names:
        langsmith_client.delete_prompt(name)
