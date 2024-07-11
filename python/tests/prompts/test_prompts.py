import asyncio
from typing import Sequence

import pytest

from langsmith import Client
from langsmith.schemas import Prompt

from langchain_core.prompts import ChatPromptTemplate

@pytest.fixture
def basic_fstring_prompt():
    return ChatPromptTemplate.from_messages(
        [
            ("system", "You are a helpful asssistant."),
            ("human", "{question}"),
        ]
    )

def test_push_prompt(
    basic_fstring_prompt,
):
    prompt_name = "basic_fstring_prompt"
    langsmith_client = Client()
    url = langsmith_client.push_prompt_manifest(
        prompt_name,
        basic_fstring_prompt
    )
    assert prompt_name in url

    res = langsmith_client.push_prompt_manifest(
        prompt_name,
        basic_fstring_prompt
    )
    assert res.status_code == 409

    prompt = langsmith_client.pull_prompt_manifest(prompt_identifier=prompt_name)
    assert prompt.repo == prompt_name

