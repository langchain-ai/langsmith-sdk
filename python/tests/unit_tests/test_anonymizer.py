import re
from typing import List, Union
from uuid import uuid4

from langsmith.anonymizer import StringNodeRule, create_anonymizer

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
UUID_REGEX = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def test_replacer_function():
    def replacer(text: str, _: List[Union[str, int]]):
        text = EMAIL_REGEX.sub("[email address]", text)
        text = UUID_REGEX.sub("[uuid]", text)
        return text

    assert create_anonymizer(replacer)(
        {
            "message": "Hello, this is my email: hello@example.com",
            "metadata": str(uuid4()),
        }
    ) == {
        "message": "Hello, this is my email: [email address]",
        "metadata": "[uuid]",
    }

    assert create_anonymizer(replacer)(["human", "hello@example.com"]) == [
        "human",
        "[email address]",
    ]
    assert create_anonymizer(replacer)("hello@example.com") == "[email address]"


def test_replacer_lambda():
    assert create_anonymizer(lambda text: EMAIL_REGEX.sub("[email address]", text))(
        {
            "message": "Hello, this is my email: hello@example.com",
        }
    ) == {
        "message": "Hello, this is my email: [email address]",
    }


def test_replacer_declared():
    replacers = [
        StringNodeRule(pattern=EMAIL_REGEX, replace="[email address]"),
        StringNodeRule(pattern=UUID_REGEX, replace="[uuid]"),
    ]

    assert create_anonymizer(replacers)(
        {
            "message": "Hello, this is my email: hello@example.com",
            "metadata": str(uuid4()),
        }
    ) == {
        "message": "Hello, this is my email: [email address]",
        "metadata": "[uuid]",
    }

    assert create_anonymizer(replacers)(["human", "hello@example.com"]) == [
        "human",
        "[email address]",
    ]

    assert create_anonymizer(replacers)("hello@example.com") == "[email address]"
