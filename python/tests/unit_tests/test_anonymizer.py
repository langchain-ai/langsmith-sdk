# mypy: disable-error-code="annotation-unchecked"
import json
import re
import uuid
from typing import List, Union, cast
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import BaseModel

from langsmith import Client, traceable, tracing_context
from langsmith.anonymizer import (
    DEFAULT_SECRET_RULES,
    SECRET_PLACEHOLDER,
    RuleNodeProcessor,
    StringNodeRule,
    create_anonymizer,
    create_secret_anonymizer,
)

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


# ── create_secret_anonymizer (curated preset) ────────────────────────────────

# Fixtures are assembled at runtime so no literal secret-shaped string sits in
# source (the repo secret-scanner would otherwise rewrite them).
SECRET_SAMPLES = {
    "anthropic": "sk-ant-api03-" + "A" * 30,
    "openai_project": "sk-proj-" + "a" * 30,
    "openai_legacy": "sk-" + "a" * 48,
    "langsmith_lsv2": "lsv2_pt_" + "a" * 36 + "_" + "b" * 10,
    "langsmith_legacy": "ls__" + "a" * 24,
    "github_pat": "ghp_" + "A" * 36,
    "github_fine_grained": "github_pat_" + "A" * 82,
    "gitlab": "glpat-" + "a" * 20,
    "aws": "AKIA" + "IOSFODNN7EXAMPLE",
    "aws_a3t": "A3TX" + "A" * 16,
    "google_api": "AIza" + "A" * 35,
    "google_oauth": "ya29.A0ARrdaM-abcdef1234567890",
    "slack_token": "-".join(["xoxb", "ABCDEFGHIJ0123456789xy"]),
    "slack_app": "xapp-1-" + "A" * 16,
    "slack_webhook": "https://hooks.slack.com/services/T00000000/B00000000/abcdef1234",
    "stripe": "sk_live_" + "a" * 24,
    "npm": "npm_" + "a" * 36,
    "pypi": "pypi-AgEIcHlwaS" + "A" * 50,
    "sendgrid": "SG." + "a" * 22 + "." + "b" * 43,
    "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NSJ9.SflKxwRJSMeKKF2QT4fwpMeJf36",
}


@pytest.mark.parametrize("secret", SECRET_SAMPLES.values(), ids=SECRET_SAMPLES.keys())
def test_secret_anonymizer_redacts(secret):
    redact = create_secret_anonymizer()
    out = redact(f"value is {secret} end")
    assert secret not in out
    assert SECRET_PLACEHOLDER in out


def test_secret_anonymizer_redacts_pem_block():
    redact = create_secret_anonymizer()
    begin = " ".join(["-----BEGIN", "RSA", "PRIVATE", "KEY-----"])
    end = " ".join(["-----END", "RSA", "PRIVATE", "KEY-----"])
    pem = "\n".join([begin, "a" * 64, end])
    assert redact({"file": pem}) == {"file": SECRET_PLACEHOLDER}


def test_secret_anonymizer_redacts_multi_segment_langsmith_key():
    redact = create_secret_anonymizer()
    key = "lsv2_pt_" + "a" * 36 + "_" + "b" * 10
    # Bare context (no assignment); exact equality catches a leaked tail.
    assert redact(f"using {key} now") == f"using {SECRET_PLACEHOLDER} now"


def test_secret_anonymizer_redacts_pgp_block():
    redact = create_secret_anonymizer()
    begin = " ".join(["-----BEGIN", "PGP", "PRIVATE", "KEY", "BLOCK-----"])
    end = " ".join(["-----END", "PGP", "PRIVATE", "KEY", "BLOCK-----"])
    block = "\n".join([begin, "a" * 64, end])
    assert redact({"file": block}) == {"file": SECRET_PLACEHOLDER}


@pytest.mark.parametrize(
    "value",
    [
        "123e4567-e89b-12d3-a456-426614174000",  # UUID
        "e83c5163316f89bfbde7d9ab23ca2e25604af290",  # 40-char git SHA
        "total = compute_sum(items) + 42",  # ordinary code
        "The deployment finished successfully in 12 seconds.",  # prose
        'tokenizer: "cl100k_base"',  # no provider-key prefix
        "tokens_used: 123456",  # no provider-key prefix
        "MY_SERVICE_TOKEN=abcdef1234567890",  # structural rule removed
        '{"api_key": "abcdef1234567890"}',  # structural rule removed
        "Authorization: Bearer aB3xY7zQ1234567890",  # structural rule removed
        "postgres://user:sup3rs3cretpw@db.example.com:5432/app",  # structural rule removed
    ],
)
def test_secret_anonymizer_precision_guards(value):
    redact = create_secret_anonymizer()
    assert redact(value) == value


def test_secret_anonymizer_nested_payload():
    redact = create_secret_anonymizer()
    payload = {
        "messages": [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_call",
                        "args": {"command": "export OPENAI_API_KEY=sk-" + "a" * 48},
                    }
                ],
            }
        ]
    }
    out = redact(payload)
    command = out["messages"][0]["content"][0]["args"]["command"]
    assert SECRET_PLACEHOLDER in command
    assert "aaaa" not in command


def test_secret_anonymizer_extra_rules():
    redact = create_secret_anonymizer(
        extra_rules=[
            StringNodeRule(
                pattern=re.compile(r"INTERNAL-[0-9]{6}"), replace=SECRET_PLACEHOLDER
            )
        ]
    )
    assert redact("ticket INTERNAL-123456") == f"ticket {SECRET_PLACEHOLDER}"
    # Defaults still active.
    assert SECRET_PLACEHOLDER in redact("key sk-ant-" + "a" * 24)


def test_default_secret_rules_all_set_explicit_token():
    for rule in DEFAULT_SECRET_RULES:
        assert SECRET_PLACEHOLDER in (rule.get("replace") or "")


def test_secret_anonymizer_in_traceable():
    anonymizer = create_secret_anonymizer()
    mock_client = Client(
        session=MagicMock(),
        auto_batch_tracing=False,
        anonymizer=anonymizer,
        api_url="http://localhost:1984",
        api_key="123",
    )

    aws_key = "AKIA" + "IOSFODNN7EXAMPLE"
    anthropic_key = "sk-ant-api03-" + "A" * 30

    @traceable(client=mock_client)
    def my_func(api_key: str) -> dict:
        return {"note": f"leaked {anthropic_key} here"}

    with tracing_context(enabled=True):
        my_func(aws_key)

    posts = [
        json.loads(call[2]["data"])
        for call in mock_client.session.request.mock_calls
        if call.args and call.args[1].endswith("runs")
    ]
    assert len(posts) == 1
    blob = json.dumps(posts[0])
    assert aws_key not in blob
    assert anthropic_key not in blob
    assert SECRET_PLACEHOLDER in blob


# ── default-on secret redaction (no explicit anonymizer) ─────────────────────


def _make_mock_client(**kwargs) -> Client:
    return Client(
        session=MagicMock(),
        auto_batch_tracing=False,
        api_url="http://localhost:1984",
        api_key="123",
        **kwargs,
    )


def test_default_redact_secrets_on():
    """Secrets are redacted by default with no explicit anonymizer."""
    client = _make_mock_client()
    aws_key = "AKIA" + "IOSFODNN7EXAMPLE"
    anthropic_key = "sk-ant-api03-" + "A" * 30

    @traceable(client=client)
    def my_func(api_key: str) -> dict:
        return {"note": f"leaked {anthropic_key} here"}

    with tracing_context(enabled=True):
        my_func(aws_key)

    posts = [
        json.loads(call[2]["data"])
        for call in client.session.request.mock_calls
        if call.args and call.args[1].endswith("runs")
    ]
    assert len(posts) == 1
    blob = json.dumps(posts[0])
    assert aws_key not in blob
    assert anthropic_key not in blob
    assert SECRET_PLACEHOLDER in blob


def test_redact_secrets_disabled_by_constructor():
    """redact_secrets=False opts out of default redaction."""
    client = _make_mock_client(redact_secrets=False)
    aws_key = "AKIA" + "IOSFODNN7EXAMPLE"

    @traceable(client=client)
    def my_func(api_key: str) -> dict:
        return {"note": "no secrets here"}

    with tracing_context(enabled=True):
        my_func(aws_key)

    posts = [
        json.loads(call[2]["data"])
        for call in client.session.request.mock_calls
        if call.args and call.args[1].endswith("runs")
    ]
    assert len(posts) == 1
    # Without redaction, the key passes through untouched.
    assert aws_key in json.dumps(posts[0])
    assert SECRET_PLACEHOLDER not in json.dumps(posts[0])


def test_custom_anonymizer_takes_precedence_over_redact_secrets():
    """A custom anonymizer overrides the default secret redaction."""
    custom = create_anonymizer(
        [StringNodeRule(pattern=re.compile(r"REPLACE_ME"), replace="[done]")]
    )
    client = _make_mock_client(anonymizer=custom)

    @traceable(client=client)
    def my_func() -> dict:
        return {"note": "leaked REPLACE_ME and sk-ant-api03-" + "A" * 30}

    with tracing_context(enabled=True):
        my_func()

    posts = [
        json.loads(call[2]["data"])
        for call in client.session.request.mock_calls
        if call.args and call.args[1].endswith("runs")
    ]
    patches = [
        json.loads(call[2]["data"])
        for call in client.session.request.mock_calls
        if call.args
        and cast(str, call.args[0]).lower() == "patch"
        and "/runs" in call.args[1]
    ]
    blob = json.dumps(posts + patches)
    # Custom anonymizer ran, but the secret was NOT redacted (it's not the
    # secret preset).
    assert "[done]" in blob
    assert "sk-ant-api03-" + "A" * 30 in blob


def test_default_redact_secrets_applies_to_metadata():
    """The default anonymizer also redacts secrets in run metadata."""
    client = _make_mock_client()
    api_key = "sk-ant-api03-" + "A" * 30

    @traceable(client=client, metadata={"config": f"key={api_key}"})
    def my_func() -> dict:
        return {"ok": True}

    with tracing_context(enabled=True):
        my_func()

    posts = [
        json.loads(call[2]["data"])
        for call in client.session.request.mock_calls
        if call.args and call.args[1].endswith("runs")
    ]
    assert len(posts) == 1
    blob = json.dumps(posts[0])
    assert api_key not in blob
    assert SECRET_PLACEHOLDER in blob


def test_redact_secrets_env_var_opt_out(monkeypatch):
    """LANGSMITH_REDACT_SECRETS=false disables default redaction."""
    from langsmith import utils as ls_utils

    ls_utils.get_env_var.cache_clear()
    monkeypatch.setenv("LANGSMITH_REDACT_SECRETS", "false")
    client = _make_mock_client()
    aws_key = "AKIA" + "IOSFODNN7EXAMPLE"

    @traceable(client=client)
    def my_func(api_key: str) -> dict:
        return {"note": "no secrets here"}

    with tracing_context(enabled=True):
        my_func(aws_key)

    posts = [
        json.loads(call[2]["data"])
        for call in client.session.request.mock_calls
        if call.args and call.args[1].endswith("runs")
    ]
    assert len(posts) == 1
    assert aws_key in json.dumps(posts[0])
    assert SECRET_PLACEHOLDER not in json.dumps(posts[0])
    ls_utils.get_env_var.cache_clear()


def test_redact_secrets_env_var_overridden_by_constructor(monkeypatch):
    """Constructor redact_secrets=True overrides LANGSMITH_REDACT_SECRETS=false."""
    from langsmith import utils as ls_utils

    ls_utils.get_env_var.cache_clear()
    monkeypatch.setenv("LANGSMITH_REDACT_SECRETS", "false")
    client = _make_mock_client(redact_secrets=True)
    anthropic_key = "sk-ant-api03-" + "A" * 30

    @traceable(client=client)
    def my_func() -> dict:
        return {"note": f"leaked {anthropic_key} here"}

    with tracing_context(enabled=True):
        my_func()

    patches = [
        json.loads(call[2]["data"])
        for call in client.session.request.mock_calls
        if call.args
        and cast(str, call.args[0]).lower() == "patch"
        and "/runs" in call.args[1]
    ]
    blob = json.dumps(patches)
    assert anthropic_key not in blob
    assert SECRET_PLACEHOLDER in blob
    ls_utils.get_env_var.cache_clear()


# ── base64 skip optimization ────────────────────────────────────────────────


def test_secret_anonymizer_skips_large_base64_blob():
    """Large base64 blobs are skipped for performance, but secrets in
    adjacent text fields are still redacted."""
    from langsmith.anonymizer import _is_likely_base64

    # A large base64 blob (simulated image data)
    blob = "A" * 5000  # long, pure base64 alphabet
    assert _is_likely_base64(blob) is True

    redact = create_secret_anonymizer()
    payload = {
        "image_data": blob,
        "text": f"Here is a secret: sk-ant-api03-{'A' * 30}",
    }
    result = redact(payload)
    # Base64 blob is untouched
    assert result["image_data"] == blob
    # Secret in text field is still redacted
    assert SECRET_PLACEHOLDER in result["text"]


def test_secret_anonymizer_does_not_skip_short_strings():
    """Short strings are never classified as base64, even if they look base64."""
    from langsmith.anonymizer import _is_likely_base64

    assert _is_likely_base64("short") is False
    assert _is_likely_base64("A" * 99) is False
    assert _is_likely_base64("A" * 100) is True


def test_secret_anonymizer_skips_base64_with_whitespace():
    """Base64 blobs with newlines (common in PEM-like data) are still skipped."""
    from langsmith.anonymizer import _is_likely_base64

    blob = ("A" * 76 + "\n") * 10  # 760 chars + newlines
    assert _is_likely_base64(blob) is True


def test_secret_anonymizer_does_not_flag_prose_as_base64():
    """Normal text with spaces and punctuation is not flagged as base64."""
    from langsmith.anonymizer import _is_likely_base64

    text = "The quick brown fox jumps over the lazy dog. " * 20
    assert _is_likely_base64(text) is False
