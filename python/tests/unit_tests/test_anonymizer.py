# mypy: disable-error-code="annotation-unchecked"
import json
import re
import uuid
from typing import List, Union, cast
from unittest.mock import MagicMock
from uuid import uuid4

from pydantic import BaseModel

from langsmith import Client, traceable, tracing_context
from langsmith.anonymizer import RuleNodeProcessor, StringNodeRule, create_anonymizer

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


def test_replacer_declared_in_traceable():
    replacers = [
        StringNodeRule(pattern=EMAIL_REGEX, replace="[email address]"),
        StringNodeRule(pattern=UUID_REGEX, replace="[uuid]"),
    ]
    anonymizer = create_anonymizer(replacers)
    mock_client = Client(
        session=MagicMock(),
        auto_batch_tracing=False,
        anonymizer=anonymizer,
        api_url="http://localhost:1984",
        api_key="123",
    )

    user_email = "my-test@langchain.ai"
    user_id = "4ae21a90-d43b-4017-bb21-4fd9add235ff"

    class MyOutput(BaseModel):
        user_email: str
        user_id: uuid.UUID
        body: str

    class MyInput(BaseModel):
        from_email: str

    @traceable(client=mock_client)
    def my_func(body: str, from_: MyInput) -> MyOutput:
        return MyOutput(user_email=user_email, user_id=user_id, body=body)

    body_ = "Hello from Pluto"
    with tracing_context(enabled=True):
        res = my_func(body_, from_=MyInput(from_email="my-from-test@langchain.ai"))
    expected = MyOutput(user_email=user_email, user_id=uuid.UUID(user_id), body=body_)
    assert res == expected
    # get posts
    posts = [
        json.loads(call[2]["data"])
        for call in mock_client.session.request.mock_calls
        if call.args and call.args[1].endswith("runs")
    ]

    patches = [
        json.loads(call[2]["data"])
        for call in mock_client.session.request.mock_calls
        if call.args
        and cast(str, call.args[0]).lower() == "patch"
        and "/runs" in call.args[1]
    ]

    expected_inputs = {"from_": {"from_email": "[email address]"}, "body": body_}
    expected_outputs = {
        "user_email": "[email address]",
        "user_id": "[uuid]",
        "body": body_,
    }

    assert len(posts) == 1
    posted_data = posts[0]
    assert posted_data["inputs"] == expected_inputs
    assert len(patches) == 1
    patched_data = patches[0]
    if "inputs" in patched_data:
        assert patched_data["inputs"] == expected_inputs
    assert patched_data["outputs"] == expected_outputs


def test_rule_node_processor_scrub_sensitive_info():
    rules = [
        StringNodeRule(pattern=re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), replace="[ssn]"),
        StringNodeRule(
            pattern=re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
            replace="[email]",
        ),
        StringNodeRule(
            pattern=re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"), replace="[phone]"
        ),
    ]
    processor = RuleNodeProcessor(rules)

    nodes = [
        {"value": "My SSN is 123-45-6789.", "path": ["field1"]},
        {"value": "Contact me at john.doe@example.com.", "path": ["field2"]},
        {"value": "Call me on 123-456-7890.", "path": ["field3"]},
    ]

    expected = [
        {"value": "My SSN is [ssn].", "path": ["field1"]},
        {"value": "Contact me at [email].", "path": ["field2"]},
        {"value": "Call me on [phone].", "path": ["field3"]},
    ]

    result = processor.mask_nodes(nodes)

    assert result == expected


def test_rule_node_processor_default_replace():
    rules = [
        StringNodeRule(pattern=re.compile(r"sensitive")),
    ]
    processor = RuleNodeProcessor(rules)

    nodes = [
        {"value": "This contains sensitive data", "path": ["field1"]},
    ]

    expected = [
        {"value": "This contains [redacted] data", "path": ["field1"]},
    ]

    result = processor.mask_nodes(nodes)
    assert result == expected
