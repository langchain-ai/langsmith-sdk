import pytest

import langsmith.env._git as git_env
from langsmith.env import __all__ as env_all
from langsmith.env import get_git_info, get_langchain_env_var_metadata

_EXPECTED = [
    "get_docker_compose_command",
    "get_docker_compose_version",
    "get_docker_environment",
    "get_docker_version",
    "get_langchain_env_var_metadata",
    "get_langchain_env_vars",
    "get_langchain_environment",
    "get_release_shas",
    "get_runtime_and_metrics",
    "get_runtime_environment",
    "get_system_metrics",
    "get_git_info",
]


def test_public_api() -> None:
    assert env_all == _EXPECTED


def test_git_info() -> None:
    git_info = get_git_info()
    try:
        assert git_info is not None
        assert git_info["commit"] is not None
        assert git_info["remote_url"] is not None
        assert "langsmith-sdk" in git_info["remote_url"]
    except AssertionError:
        pytest.skip("Git information is not available, skipping test.")


def _patch_git_remote(
    monkeypatch: pytest.MonkeyPatch, remote_url: str
) -> list[list[str]]:
    calls: list[list[str]] = []
    outputs = {
        ("rev-parse", "--is-inside-work-tree"): "true",
        ("remote", "get-url", "origin"): remote_url,
        ("rev-parse", "HEAD"): "abc123",
        ("log", "-1", "--format=%ct"): "1720000000",
        ("rev-parse", "--abbrev-ref", "HEAD"): "main",
        ("describe", "--tags", "--exact-match", "--always", "--dirty"): "abc123",
        ("status", "--porcelain"): "",
        ("log", "-1", "--format=%an"): "LangSmith",
        ("log", "-1", "--format=%ae"): "langsmith@example.com",
        ("rev-parse", "--show-toplevel"): "/workspace/langsmith-sdk",
    }

    def fake_exec_git(command: list[str]) -> str | None:
        calls.append(command)
        return outputs.get(tuple(command))

    monkeypatch.setattr(git_env, "exec_git", fake_exec_git)
    get_git_info.cache_clear()
    return calls


@pytest.mark.parametrize(
    ("remote_url", "expected_remote_url"),
    [
        (
            "https://user:token@github.com/langchain-ai/langsmith-sdk.git",
            "https://github.com/langchain-ai/langsmith-sdk.git",
        ),
        (
            "https://user%40example.com:p%40ss%2Fword@github.com/org/repo.git",
            "https://github.com/org/repo.git",
        ),
        (
            "https://github.com/langchain-ai/langsmith-sdk.git",
            "https://github.com/langchain-ai/langsmith-sdk.git",
        ),
        (
            "ssh://git@github.com/langchain-ai/langsmith-sdk.git",
            "ssh://git@github.com/langchain-ai/langsmith-sdk.git",
        ),
        (
            "git@github.com:langchain-ai/langsmith-sdk.git",
            "git@github.com:langchain-ai/langsmith-sdk.git",
        ),
    ],
)
def test_git_info_sanitizes_remote_urls(
    monkeypatch: pytest.MonkeyPatch, remote_url: str, expected_remote_url: str
) -> None:
    _patch_git_remote(monkeypatch, remote_url)
    try:
        git_info = get_git_info()
        assert git_info["remote_url"] == expected_remote_url
    finally:
        get_git_info.cache_clear()


def test_git_info_caches_sanitized_remote_url(monkeypatch: pytest.MonkeyPatch) -> None:
    remote_url = "https://user:token@github.com/langchain-ai/langsmith-sdk.git"
    calls = _patch_git_remote(monkeypatch, remote_url)
    try:
        assert get_git_info()["remote_url"] == (
            "https://github.com/langchain-ai/langsmith-sdk.git"
        )
        assert get_git_info()["remote_url"] == (
            "https://github.com/langchain-ai/langsmith-sdk.git"
        )
        assert calls.count(["remote", "get-url", "origin"]) == 1
    finally:
        get_git_info.cache_clear()


@pytest.mark.parametrize(
    "secret_var",
    ["LANGSMITH_SIGNING_JWKS", "LANGSMITH_SANDBOX_CALLBACK_SIGNING_JWK"],
)
def test_env_var_metadata_excludes_signing_secrets(
    monkeypatch: pytest.MonkeyPatch, secret_var: str
) -> None:
    monkeypatch.setenv(secret_var, "super-secret-value")
    monkeypatch.setenv("LANGSMITH_LANGGRAPH_API_VARIANT", "local")
    monkeypatch.setenv("LANGCHAIN_REVISION_ID", "abc123")
    get_langchain_env_var_metadata.cache_clear()
    metadata = get_langchain_env_var_metadata()
    assert secret_var not in metadata
    assert metadata["LANGSMITH_LANGGRAPH_API_VARIANT"] == "local"
    assert metadata["revision_id"] == "abc123"
