from enum import Enum
from itertools import product
from typing import Literal

import instructor  # type: ignore
import pytest
from anthropic import AsyncAnthropic  # type: ignore
from openai import AsyncOpenAI
from pydantic import BaseModel

from langsmith import test


class Models(str, Enum):
    GPT35TURBO = "gpt-3.5-turbo"
    GPT4TURBO = "gpt-4-turbo"
    CLAUDE3_SONNET = "claude-3-sonnet-20240229"
    CLAUDE3_OPUS = "claude-3-opus-20240229"
    CLAUDE3_HAIKU = "claude-3-haiku-20240307"


clients = (
    instructor.from_openai(
        AsyncOpenAI(),
        model=Models.GPT35TURBO,
    ),
    instructor.from_openai(
        AsyncOpenAI(),
        model=Models.GPT4TURBO,
    ),
    instructor.from_anthropic(
        AsyncAnthropic(),
        model=Models.CLAUDE3_OPUS,
        max_tokens=4000,
    ),
    instructor.from_anthropic(
        AsyncAnthropic(),
        model=Models.CLAUDE3_SONNET,
        max_tokens=4000,
    ),
    instructor.from_anthropic(
        AsyncAnthropic(),
        model=Models.CLAUDE3_HAIKU,
        max_tokens=4000,
    ),
)


class ClassifySpam(BaseModel):
    label: Literal["spam", "not_spam"]


data = [
    ("I am a spammer who sends many emails every day", "spam"),
    ("I am a responsible person who does not spam", "not_spam"),
]
d = list(product(clients, data))


@pytest.mark.asyncio_cooperative
@test()
@pytest.mark.parametrize("client, data", d[:3])
async def test_classification(client, data):
    input, expected = data
    prediction = await client.create(
        response_model=ClassifySpam,
        messages=[
            {
                "role": "system",
                "content": "Classify this text as 'spam' or 'not_spam'.",
            },
            {
                "role": "user",
                "content": input,
            },
        ],
    )
    assert prediction.label == expected
