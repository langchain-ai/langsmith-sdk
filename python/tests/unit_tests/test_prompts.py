import pytest
from langchain_core.prompts import ChatPromptTemplate

from langsmith.client import convert_to_anthropic_format, convert_to_openai_format


@pytest.fixture
def chat_prompt_template():
    return ChatPromptTemplate.from_messages(
        [
            ("system", "You are a chatbot"),
            ("user", "{question}"),
        ]
    )


def test_convert_to_openai_format(chat_prompt_template: ChatPromptTemplate):
    invoked = chat_prompt_template.invoke({"question": "What is the meaning of life?"})

    res = convert_to_openai_format(
        invoked,
    )

    assert res == {
        "messages": [
            {"content": "You are a chatbot", "role": "system"},
            {"content": "What is the meaning of life?", "role": "user"},
        ],
        "model": "gpt-3.5-turbo",
        "stream": False,
        "n": 1,
        "temperature": 0.7,
    }


def test_convert_to_anthropic_format(chat_prompt_template: ChatPromptTemplate):
    invoked = chat_prompt_template.invoke({"question": "What is the meaning of life?"})

    res = convert_to_anthropic_format(
        invoked,
    )

    print("Res: ", res)

    assert res == {
        "model": "claude-2",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": "What is the meaning of life?"}],
        "system": "You are a chatbot",
    }
