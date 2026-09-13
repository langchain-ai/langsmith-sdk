"""Wrapped LLM provider calls, with the HTTP transport faked.

Both masking mechanisms run on the caller's thread inside `Client.create_run`
(`_hide_run_inputs` and `serialize_run_dict`), so the timed call covers them
and nothing has to wait on the background thread.
"""

from unittest.mock import MagicMock

import anthropic
import httpx
import openai

from langsmith.anonymizer import create_secret_anonymizer
from langsmith.client import Client
from langsmith.run_helpers import tracing_context
from langsmith.secret import LangSmithSecret
from langsmith.wrappers import wrap_anthropic, wrap_openai

FAKE_KEY = "sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"

_TEXT = (
    "Sure -- to rotate the key, call the admin endpoint with the current "
    "credential in the Authorization header, then re-deploy."
)

_CHAT_RESPONSE = {
    "id": "chatcmpl-bench",
    "object": "chat.completion",
    "created": 1700000000,
    "model": "gpt-4o-mini",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": _TEXT,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "rotate_key",
                            "arguments": '{"scope": "org", "confirm": true}',
                        },
                    }
                ],
            },
            "finish_reason": "tool_calls",
            "logprobs": None,
        }
    ],
    "usage": {"prompt_tokens": 120, "completion_tokens": 48, "total_tokens": 168},
}

_MESSAGE_RESPONSE = {
    "id": "msg_bench",
    "type": "message",
    "role": "assistant",
    "model": "claude-sonnet-4-5",
    "content": [
        {"type": "text", "text": _TEXT},
        {
            "type": "tool_use",
            "id": "toolu_1",
            "name": "rotate_key",
            "input": {"scope": "org", "confirm": True},
        },
    ],
    "stop_reason": "tool_use",
    "stop_sequence": None,
    "usage": {"input_tokens": 120, "output_tokens": 48},
}

_MESSAGES = [
    {"role": "system", "content": "You are a helpful operations assistant."},
    {"role": "user", "content": "How do I rotate the vendor API key?"},
    {"role": "assistant", "content": _TEXT},
    {"role": "user", "content": "Do it for the whole org, and confirm."},
]

_CLIENT_INFO = {
    "batch_ingest_config": {
        "use_multipart_endpoint": False,
        "scale_up_qsize_trigger": 1000,
        "scale_up_nthreads_limit": 16,
        "scale_down_nempty_trigger": 4,
        "size_limit": 100,
        "size_limit_bytes": 20971520,
    },
}


class _CannedClient(httpx.Client):
    """Answers every request in-process.

    `vcr.patch` hijacks `httpx.MockTransport.handle_request`, and this repo's
    conftest applies an autouse VCR fixture to every test, so a transport mock
    gets intercepted. `send` is above the patched layer.
    """

    def __init__(self, payload: dict):
        super().__init__()
        self._payload = payload

    def send(self, request: httpx.Request, **kwargs) -> httpx.Response:
        return httpx.Response(200, json=self._payload, request=request)


def _ls_client(anonymizer=None) -> Client:
    return Client(
        session=MagicMock(),
        info=_CLIENT_INFO,
        api_key="fake",
        anonymizer=anonymizer,
    )


def _auth_header(variant: str) -> str:
    # Wrap the finished value: `f"Bearer {secret}"` yields a plain `str`.
    if variant == "langsmith_secret":
        secret = LangSmithSecret(FAKE_KEY)
    else:
        secret = FAKE_KEY
    return "Bearer %s" % secret


def _ls_for(variant: str) -> Client:
    anonymizer = create_secret_anonymizer() if variant == "secret_anonymizer" else None
    return _ls_client(anonymizer)


def make_openai_case(variant: str, n: int):
    client = wrap_openai(
        openai.OpenAI(api_key=FAKE_KEY, http_client=_CannedClient(_CHAT_RESPONSE)),
        tracing_extra={"client": _ls_for(variant)},
    )
    kwargs = {
        "model": "gpt-4o-mini",
        "messages": _MESSAGES,
        "extra_headers": {"Authorization": _auth_header(variant)},
    }
    return client.chat.completions.create, kwargs, n


def make_anthropic_case(variant: str, n: int):
    client = wrap_anthropic(
        anthropic.Anthropic(
            api_key=FAKE_KEY, http_client=_CannedClient(_MESSAGE_RESPONSE)
        ),
        tracing_extra={"client": _ls_for(variant)},
    )
    kwargs = {
        "model": "claude-sonnet-4-5",
        "max_tokens": 1024,
        "messages": _MESSAGES[1:],
        "system": _MESSAGES[0]["content"],
        "extra_headers": {"Authorization": _auth_header(variant)},
    }
    return client.messages.create, kwargs, n


def run_wrapped_calls(case) -> None:
    create, kwargs, n = case
    with tracing_context(enabled=True):
        for _ in range(n):
            create(**kwargs)


if __name__ == "__main__":
    import langsmith.client as lc

    expected = {
        "baseline": FAKE_KEY.encode(),
        "secret_anonymizer": b"[SECRET_DETECTED]",
        "langsmith_secret": b"[LANGSMITH SECRET]",
    }
    for maker in (make_openai_case, make_anthropic_case):
        for variant, marker in expected.items():
            seen = []
            orig = lc.serialize_run_dict

            def spy(operation, payload, *a, _orig=orig, _seen=seen, **kw):
                op = _orig(operation, payload, *a, **kw)
                _seen.append(b" ".join(filter(None, (op.inputs, op.outputs, op._none))))
                return op

            lc.serialize_run_dict = spy
            try:
                run_wrapped_calls(maker(variant, n=1))
            finally:
                lc.serialize_run_dict = orig
            blob = b" ".join(seen)
            assert marker in blob, (maker.__name__, variant)
            if variant != "baseline":
                assert FAKE_KEY.encode() not in blob, (maker.__name__, variant)
    print("ok")
