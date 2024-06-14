import re
from uuid import uuid4

from langsmith.anonymizer import StringNodeRule, replace_sensitive_data

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
UUID_REGEX = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def test_replacer_function():
    def replacer(text: str, _: list[str | int]):
        text = EMAIL_REGEX.sub("[email address]", text)
        text = UUID_REGEX.sub("[uuid]", text)
        return text

    assert replace_sensitive_data(
        {
            "message": "Hello, this is my email: hello@example.com",
            "metadata": str(uuid4()),
        },
        replacer,
    ) == {
        "message": "Hello, this is my email: [email address]",
        "metadata": "[uuid]",
    }

    assert replace_sensitive_data(["human", "hello@example.com"], replacer) == [
        "human",
        "[email address]",
    ]
    assert replace_sensitive_data("hello@example.com", replacer) == "[email address]"


def test_replacer_declared():
    replacers = [
        StringNodeRule(pattern=EMAIL_REGEX, replace="[email address]"),
        StringNodeRule(pattern=UUID_REGEX, replace="[uuid]"),
    ]

    assert replace_sensitive_data(
        {
            "message": "Hello, this is my email: hello@example.com",
            "metadata": str(uuid4()),
        },
        replacers,
    ) == {
        "message": "Hello, this is my email: [email address]",
        "metadata": "[uuid]",
    }

    assert replace_sensitive_data(["human", "hello@example.com"], replacers) == [
        "human",
        "[email address]",
    ]

    assert replace_sensitive_data("hello@example.com", replacers) == "[email address]"
