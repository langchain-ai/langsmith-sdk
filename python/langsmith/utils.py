"""Generic utility functions."""
import platform
import subprocess
from functools import lru_cache
from typing import Any, Callable, List, Tuple

from requests import HTTPError, Response


class LangSmithAPIError(Exception):
    """An error occurred while communicating with the LangSmith API."""


class LangSmithUserError(Exception):
    """An error occurred while communicating with the LangSmith API."""


class LangSmithError(Exception):
    """An error occurred while communicating with the LangSmith API."""


class LangSmithConnectionError(Exception):
    """Couldn't connect to the LangSmith API."""


def xor_args(*arg_groups: Tuple[str, ...]) -> Callable:
    """Validate specified keyword args are mutually exclusive."""

    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Callable:
            """Validate exactly one arg in each group is not None."""
            counts = [
                sum(1 for arg in arg_group if kwargs.get(arg) is not None)
                for arg_group in arg_groups
            ]
            invalid_groups = [i for i, count in enumerate(counts) if count != 1]
            if invalid_groups:
                invalid_group_names = [", ".join(arg_groups[i]) for i in invalid_groups]
                raise ValueError(
                    "Exactly one argument in each of the following"
                    " groups must be defined:"
                    f" {', '.join(invalid_group_names)}"
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def raise_for_status_with_text(response: Response) -> None:
    """Raise an error with the response text."""
    try:
        response.raise_for_status()
    except HTTPError as e:
        raise ValueError(response.text) from e


@lru_cache(maxsize=1)
def get_runtime_environment() -> dict:
    """Get information about the environment."""
    # Lazy import to avoid circular imports
    from langsmith import __version__

    return {
        "sdk_version": __version__,
        "library": "langsmith",
        "platform": platform.platform(),
        "runtime": "python",
        "runtime_version": platform.python_version(),
    }


@lru_cache
def get_docker_compose_command() -> List[str]:
    """Get the correct docker compose command for this system."""
    try:
        subprocess.check_call(
            ["docker", "compose", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return ["docker", "compose"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            subprocess.check_call(
                ["docker-compose", "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return ["docker-compose"]
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise ValueError(
                "Neither 'docker compose' nor 'docker-compose'"
                " commands are available. Please install the Docker"
                " server following the instructions for your operating"
                " system at https://docs.docker.com/engine/install/"
            )


@lru_cache
def get_docker_environment() -> dict:
    """Get information about the environment."""
    # Try to get the docker CLI version via subprocess
    import subprocess

    try:
        docker_version = (
            subprocess.check_output(["docker", "--version"]).decode("utf-8").strip()
        )
    except FileNotFoundError:
        docker_version = "unknown"
    try:
        compose_command = get_docker_compose_command()
    except ValueError as e:
        compose_command = [f"NOT INSTALLED: {e}"]
    try:
        docker_compose_version = (
            subprocess.check_output(["docker-compose", "--version"])
            .decode("utf-8")
            .strip()
        )
    except FileNotFoundError:
        docker_compose_version = "unknown"

    return {
        "docker_version": docker_version,
        "docker_compose_command": " ".join(compose_command),
        "docker_compose_version": docker_compose_version,
    }
