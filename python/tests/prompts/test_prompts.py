import pytest
from uuid import uuid4
from langsmith.client import Client
from langsmith.schemas import Prompt, ListPromptsResponse
from langchain_core.prompts import ChatPromptTemplate


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


def test_list_prompts(langsmith_client: Client):
    # Test listing prompts
    response = langsmith_client.list_prompts(limit=10, offset=0)
    assert isinstance(response, ListPromptsResponse)
    assert len(response.repos) <= 10


def test_get_prompt(langsmith_client: Client, prompt_template_1: ChatPromptTemplate):
    # First, create a prompt to test with
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"
    langsmith_client.push_prompt(prompt_name, prompt_template_1)

    # Now test getting the prompt
    prompt = langsmith_client.get_prompt(prompt_name)
    assert isinstance(prompt, Prompt)
    assert prompt.repo_handle == prompt_name

    # Clean up
    langsmith_client.delete_prompt(prompt_name)
    assert not langsmith_client.prompt_exists(prompt_name)


def test_prompt_exists(langsmith_client: Client, prompt_template_2: ChatPromptTemplate):
    # Test with a non-existent prompt
    non_existent_prompt = f"non_existent_{uuid4().hex[:8]}"
    assert not langsmith_client.prompt_exists(non_existent_prompt)

    # Create a prompt and test again
    existent_prompt = f"existent_{uuid4().hex[:8]}"
    langsmith_client.push_prompt(existent_prompt, prompt_template_2)
    assert langsmith_client.prompt_exists(existent_prompt)

    # Clean up
    langsmith_client.delete_prompt(existent_prompt)
    assert not langsmith_client.prompt_exists(existent_prompt)


def test_push_and_pull_prompt(langsmith_client: Client, prompt_template_2: ChatPromptTemplate):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"

    # Test pushing a prompt
    push_result = langsmith_client.push_prompt(prompt_name, prompt_template_2)
    assert isinstance(push_result, str)  # Should return a URL

    # Test pulling the prompt
    langsmith_client.pull_prompt(prompt_name)

    # Clean up
    langsmith_client.delete_prompt(prompt_name)


def test_push_prompt_manifest(langsmith_client: Client, prompt_template_2: ChatPromptTemplate):
    prompt_name = f"test_prompt_manifest_{uuid4().hex[:8]}"

    # Test pushing a prompt manifest
    result = langsmith_client.push_prompt_manifest(prompt_name, prompt_template_2)
    assert isinstance(result, str)  # Should return a URL

    # Verify the pushed manifest
    pulled_prompt_manifest = langsmith_client.pull_prompt_manifest(prompt_name)
    latest_commit_hash = langsmith_client._get_latest_commit_hash(f"-/{prompt_name}")
    assert pulled_prompt_manifest.commit_hash == latest_commit_hash

    # Clean up
    langsmith_client.delete_prompt(prompt_name)
