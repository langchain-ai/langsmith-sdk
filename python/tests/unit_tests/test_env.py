from typing import Dict

from langsmith.env import __all__ as env_all
from langsmith.env import get_git_info, get_runtime_environment, set_package_version

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
    "set_package_version",
]


def test_public_api() -> None:
    assert env_all == _EXPECTED


def test_git_info() -> None:
    git_info = get_git_info()
    assert git_info is not None
    assert git_info["commit"] is not None
    assert git_info["remote_url"] is not None
    assert "langsmith-sdk" in git_info["remote_url"]


def test_package_versions() -> None:
    def _get_package_versions() -> Dict[str, str]:
        return {
            k: v
            for k, v in get_runtime_environment().items()
            if k.startswith("package_version_")
        }

    assert len(_get_package_versions()) == 0
    set_package_version("foo", "1.2.3")
    set_package_version("bar", "4.5.6")
    set_package_version("foo-bar", "7.8.9")

    assert _get_package_versions() == {
        "package_version_foo": "1.2.3",
        "package_version_bar": "4.5.6",
        "package_version_foo-bar": "7.8.9",
    }
