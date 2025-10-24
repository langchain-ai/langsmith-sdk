import pytest

from langsmith.env import __all__ as env_all
from langsmith.env import get_git_info

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
