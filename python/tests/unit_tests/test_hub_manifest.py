"""Tests for Hub prompt manifest wrapping."""

import pytest

from langsmith._internal._hub import wrap_manifest_for_hub_push

_FLAT_STRUCTURED_PROMPT = {
    "lc": 1,
    "type": "constructor",
    "id": ["langchain_core", "prompts", "structured", "StructuredPrompt"],
    "kwargs": {
        "input_variables": ["input"],
        "messages": [],
        "schema_": {
            "type": "object",
            "properties": {"score": {"type": "boolean"}},
        },
    },
}


def test_wrap_manifest_for_hub_push_wraps_flat_structured_prompt() -> None:
    wrapped = wrap_manifest_for_hub_push(_FLAT_STRUCTURED_PROMPT)

    assert wrapped["id"] == ["langsmith", "playground", "PromptPlayground"]
    assert wrapped["kwargs"]["first"] == _FLAT_STRUCTURED_PROMPT
    assert wrapped["kwargs"]["last"]["id"][-1] == "RunnableBinding"


@pytest.mark.parametrize(
    "manifest",
    [
        {
            "lc": 1,
            "type": "constructor",
            "id": ["langsmith", "playground", "PromptPlayground"],
            "kwargs": {"first": {"id": ["prompt"]}, "last": {"id": ["model"]}},
        },
        {
            "lc": 1,
            "type": "constructor",
            "id": ["langchain", "schema", "runnable", "RunnableSequence"],
            "kwargs": {"first": {"id": ["prompt"]}, "last": {"id": ["model"]}},
        },
    ],
)
def test_wrap_manifest_for_hub_push_leaves_wrapped_manifests_unchanged(
    manifest: dict,
) -> None:
    assert wrap_manifest_for_hub_push(manifest) is manifest
