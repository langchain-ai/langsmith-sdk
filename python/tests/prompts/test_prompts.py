from uuid import uuid4

import pytest
from langchain_core.prompts import ChatPromptTemplate

from langsmith.client import Client
from langsmith.schemas import ListPromptsResponse, Prompt, PromptManifest


@pytest.fixture
def langsmith_client() -> Client:
    return Client()


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


def test_current_tenant_is_owner(langsmith_client: Client):
    settings = langsmith_client.get_settings()
    assert langsmith_client.current_tenant_is_owner(settings["tenant_handle"])
    assert langsmith_client.current_tenant_is_owner("-")
    assert not langsmith_client.current_tenant_is_owner("non_existent_owner")


def test_list_prompts(langsmith_client: Client):
    response = langsmith_client.list_prompts(limit=10, offset=0)
    assert isinstance(response, ListPromptsResponse)
    assert len(response.repos) <= 10


def test_get_prompt(langsmith_client: Client, prompt_template_1: ChatPromptTemplate):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"
    langsmith_client.push_prompt(prompt_name, prompt_template_1)

    prompt = langsmith_client.get_prompt(prompt_name)
    assert isinstance(prompt, Prompt)
    assert prompt.repo_handle == prompt_name

    langsmith_client.delete_prompt(prompt_name)


def test_prompt_exists(langsmith_client: Client, prompt_template_2: ChatPromptTemplate):
    non_existent_prompt = f"non_existent_{uuid4().hex[:8]}"
    assert not langsmith_client.prompt_exists(non_existent_prompt)

    existent_prompt = f"existent_{uuid4().hex[:8]}"
    langsmith_client.push_prompt(existent_prompt, prompt_template_2)
    assert langsmith_client.prompt_exists(existent_prompt)

    langsmith_client.delete_prompt(existent_prompt)


def test_update_prompt(langsmith_client: Client, prompt_template_1: ChatPromptTemplate):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"
    langsmith_client.push_prompt(prompt_name, prompt_template_1)

    updated_data = langsmith_client.update_prompt(
        prompt_name,
        description="Updated description",
        is_public=True,
        tags=["test", "update"],
    )
    assert isinstance(updated_data, dict)

    updated_prompt = langsmith_client.get_prompt(prompt_name)
    assert updated_prompt.description == "Updated description"
    assert updated_prompt.is_public
    assert set(updated_prompt.tags) == set(["test", "update"])

    langsmith_client.delete_prompt(prompt_name)


def test_delete_prompt(langsmith_client: Client, prompt_template_1: ChatPromptTemplate):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"
    langsmith_client.push_prompt(prompt_name, prompt_template_1)

    assert langsmith_client.prompt_exists(prompt_name)
    langsmith_client.delete_prompt(prompt_name)
    assert not langsmith_client.prompt_exists(prompt_name)


def test_pull_prompt_manifest(
    langsmith_client: Client, prompt_template_1: ChatPromptTemplate
):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"
    langsmith_client.push_prompt(prompt_name, prompt_template_1)

    manifest = langsmith_client.pull_prompt_manifest(prompt_name)
    assert isinstance(manifest, PromptManifest)
    assert manifest.repo == prompt_name

    langsmith_client.delete_prompt(prompt_name)


def test_pull_prompt(langsmith_client: Client, prompt_template_1: ChatPromptTemplate):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"
    langsmith_client.push_prompt(prompt_name, prompt_template_1)

    pulled_prompt = langsmith_client.pull_prompt(prompt_name)
    assert isinstance(pulled_prompt, ChatPromptTemplate)

    langsmith_client.delete_prompt(prompt_name)


def test_push_and_pull_prompt(
    langsmith_client: Client, prompt_template_2: ChatPromptTemplate
):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"

    push_result = langsmith_client.push_prompt(prompt_name, prompt_template_2)
    assert isinstance(push_result, str)

    pulled_prompt = langsmith_client.pull_prompt(prompt_name)
    assert isinstance(pulled_prompt, ChatPromptTemplate)

    langsmith_client.delete_prompt(prompt_name)

    # should fail
    with pytest.raises(ValueError):
        langsmith_client.push_prompt(f"random_handle/{prompt_name}", prompt_template_2)


def test_like_unlike_prompt(
    langsmith_client: Client, prompt_template_1: ChatPromptTemplate
):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"
    langsmith_client.push_prompt(prompt_name, prompt_template_1)

    langsmith_client.like_prompt(prompt_name)
    prompt = langsmith_client.get_prompt(prompt_name)
    assert prompt.num_likes == 1

    langsmith_client.unlike_prompt(prompt_name)
    prompt = langsmith_client.get_prompt(prompt_name)
    assert prompt.num_likes == 0

    langsmith_client.delete_prompt(prompt_name)


def test_get_latest_commit_hash(
    langsmith_client: Client, prompt_template_1: ChatPromptTemplate
):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"
    langsmith_client.push_prompt(prompt_name, prompt_template_1)

    commit_hash = langsmith_client._get_latest_commit_hash(f"-/{prompt_name}")
    assert isinstance(commit_hash, str)
    assert len(commit_hash) > 0

    langsmith_client.delete_prompt(prompt_name)
