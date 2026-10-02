"""Addresses that name where runs are sent.

!!! warning "Beta"
    Addressing runs to an address is enabled per workspace. A workspace
    without it rejects the runs, so tracing is lost rather than falling back
    to a project. This API may change without notice.

An address is a plain string, `lrn:agents/{id}/environments/{environment}`. The
constructors here validate one and return it as an `Address`; anywhere an
address is accepted, any `str` is validated the same way. The environment is
one of `local`, `development`, `staging` or `production`, and is always
rendered lowercase.

Example:
    ```python
    import langsmith as ls

    support = ls.address.agent("customer-support", "production")


    @ls.traceable(address=support)
    def handle(order): ...


    with ls.tracing_context(
        address="lrn:agents/customer-support/environments/staging"
    ):
        handle(order)
    ```
"""

from __future__ import annotations

import re
from typing import NewType, Optional

from langsmith import utils

__all__ = ["Address", "agent", "from_env", "parse"]

Address = NewType("Address", str)
"""(beta) A validated address string."""

# The server's agent id rule: a DNS label, so a hostname can carry the id.
_AGENT_ID_PATTERN = re.compile(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?")
_ENVIRONMENTS = ("local", "development", "staging", "production")
_ADDRESS_PATTERN = re.compile(r"lrn:agents/([^/]*)/environments/([^/]*)")


class EnvAddressError(utils.LangSmithUserError):
    """The `LANGSMITH_AGENT_*` / project env vars can't address a run.

    Raised for half an address, an invalid one, or an address beside a project.
    Tracing entry points (`@traceable`, `trace`, `tracing_context`,
    `create_run`) catch it, log it and leave the call untraced, so a bad
    environment never breaks the code being traced. Explicit ingestion calls
    (`batch_ingest_runs`, `multipart_ingest`) let it raise for runs that name no
    destination, rather than drop part of a batch the caller built.
    """


def agent(agent_id: str, agent_environment: str) -> Address:
    """(beta) Build the address of an agent's environment.

    Args:
        agent_id: The agent's ID: 1 to 63 lowercase ASCII letters, digits or
            hyphens, starting with a letter and ending with a letter or digit.
            The server creates the agent on first use.
        agent_environment: One of `local`, `development`, `staging` or
            `production`, in any case.

    Raises:
        LangSmithUserError: If a value is invalid.
    """
    if not isinstance(agent_id, str) or not _AGENT_ID_PATTERN.fullmatch(agent_id):
        raise utils.LangSmithUserError(
            "Address agent id must be 1 to 63 lowercase ASCII letters, digits, "
            "or hyphens, start with a letter, and end with a letter or digit, "
            f"got {agent_id!r}. Use an id such as 'support-agent'."
        )
    environment = (
        agent_environment.lower() if isinstance(agent_environment, str) else None
    )
    if environment not in _ENVIRONMENTS:
        raise utils.LangSmithUserError(
            f"Address environment must be one of {', '.join(_ENVIRONMENTS)}, "
            f"got {agent_environment!r}."
        )
    return Address(f"lrn:agents/{agent_id}/environments/{environment}")


def parse(address: str) -> Address:
    """(beta) Validate an address string, lowercasing its environment.

    Only agent addresses, `lrn:agents/{id}/environments/{environment}`, exist.

    Raises:
        LangSmithUserError: If `address` is not a valid agent address.
    """
    match = _ADDRESS_PATTERN.fullmatch(address) if isinstance(address, str) else None
    if match is None:
        raise utils.LangSmithUserError(
            "An address must be a string like "
            f"'lrn:agents/{{id}}/environments/{{environment}}', got {address!r}."
        )
    return agent(*match.groups())


def from_env() -> Optional[Address]:
    """(beta) Read the address named by the `LANGSMITH_AGENT_*` env vars.

    Reads `LANGSMITH_AGENT_ID` and `LANGSMITH_AGENT_ENVIRONMENT`, and returns
    `None` if neither is set.

    Raises:
        EnvAddressError: If only one is set, or a value is invalid.
    """
    values = env_values()
    if not any(values.values()):
        return None
    missing = [name for name, value in values.items() if not value]
    try:
        if missing:
            raise utils.LangSmithUserError(
                f"An address needs {' and '.join(missing)} as well."
            )
        return agent(*values.values())  # type: ignore[arg-type]
    except utils.LangSmithUserError as e:
        present = ", ".join(
            f"{name}={value!r}" for name, value in values.items() if value
        )
        raise EnvAddressError(
            f"The LANGSMITH_AGENT_* env vars can't address a run ({present}): {e}"
        ) from e


def env_values() -> dict[str, Optional[str]]:
    """Return each `LANGSMITH_AGENT_*` env var an address reads, with its value."""
    return {
        f"LANGSMITH_{name}": utils.get_env_var(name, namespaces=("LANGSMITH",))
        for name in ("AGENT_ID", "AGENT_ENVIRONMENT")
    }
