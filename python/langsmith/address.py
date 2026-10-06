"""Addresses that name where runs are sent.

!!! warning "Beta"
    Addressing runs to an address is enabled per workspace. A workspace
    without it rejects the runs, so tracing is lost rather than falling back
    to a project. This API may change without notice.

An `Address` is anything that names a destination for runs and can render
itself as an LRN, a string like `lrn:agents/{id}/environments/{environment}`.
`Agent` is the implementation that names an agent's environment; others can
follow without changing the tracing API. The environment is one of `local`,
`development`, `staging` or `production`, and is always rendered lowercase.

Anywhere an address is accepted, an `Address` is; it is validated once at that
entry point. The LRN is only the wire format: it is what is sent in the
`address` field of a payload and in trace headers, and is never taken as input.

Example:
    ```python
    import langsmith as ls

    support = ls.Agent(id="customer-support", env="production")


    @ls.traceable(address=support)
    def handle(order): ...


    with ls.tracing_context(address=ls.Agent("customer-support", "staging")):
        handle(order)
    ```
"""

from __future__ import annotations

import dataclasses
import re
from typing import Any, Optional, Protocol, runtime_checkable

from langsmith import utils

__all__ = ["Address", "Agent", "EnvAddressError"]

# The server's agent id rule: a DNS label, so a hostname can carry the id.
_AGENT_ID_PATTERN = re.compile(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?")
_ENVIRONMENTS = ("local", "development", "staging", "production")
_LRN_PATTERN = re.compile(r"lrn:agents/([^/]*)/environments/([^/]*)")


@runtime_checkable
class Address(Protocol):
    """(beta) A destination that runs can be addressed to."""

    def lrn(self) -> str:
        """Return this address as an LRN string."""
        ...


class EnvAddressError(utils.LangSmithUserError):
    """The `LANGSMITH_AGENT_*` / project env vars can't address a run.

    Raised for half an address, an invalid one, or an address beside a project.
    Tracing entry points (`@traceable`, `trace`, `tracing_context`,
    `create_run`) catch it, log it and leave the call untraced, so a bad
    environment never breaks the code being traced. Explicit ingestion calls
    (`batch_ingest_runs`, `multipart_ingest`) let it raise for runs that name no
    destination, rather than drop part of a batch the caller built.
    """


@dataclasses.dataclass(frozen=True)
class Agent:
    """(beta) The address of an agent's environment.

    Args:
        id: The agent's ID: 1 to 63 lowercase ASCII letters, digits or
            hyphens, starting with a letter and ending with a letter or digit.
            The server creates the agent on first use.
        env: One of `local`, `development`, `staging` or `production`, in any
            case.

    Raises:
        LangSmithUserError: If a value is invalid.
    """

    id: str
    env: str

    def __post_init__(self) -> None:
        """Validate the fields and lowercase the environment."""
        if not isinstance(self.id, str) or not _AGENT_ID_PATTERN.fullmatch(self.id):
            raise utils.LangSmithUserError(
                "Address agent id must be 1 to 63 lowercase ASCII letters, digits, "
                "or hyphens, start with a letter, and end with a letter or digit, "
                f"got {self.id!r}. Use an id such as 'support-agent'."
            )
        env = self.env.lower() if isinstance(self.env, str) else None
        if env not in _ENVIRONMENTS:
            raise utils.LangSmithUserError(
                f"Address environment must be one of {', '.join(_ENVIRONMENTS)}, "
                f"got {self.env!r}."
            )
        object.__setattr__(self, "env", env)

    def lrn(self) -> str:
        """Return `lrn:agents/{id}/environments/{env}`."""
        return f"lrn:agents/{self.id}/environments/{self.env}"

    def __str__(self) -> str:
        """Return the LRN."""
        return self.lrn()

    @classmethod
    def parse(cls, lrn: str) -> Agent:
        """Build from an agent LRN read off the wire, lowercasing its environment.

        Raises:
            LangSmithUserError: If `lrn` is not a valid agent LRN.
        """
        match = _LRN_PATTERN.fullmatch(lrn) if isinstance(lrn, str) else None
        if match is None:
            raise utils.LangSmithUserError(
                "Expected an LRN like "
                f"'lrn:agents/{{id}}/environments/{{environment}}', got {lrn!r}."
            )
        return cls(*match.groups())

    @classmethod
    def from_env(cls) -> Optional[Agent]:
        """Read the agent named by the `LANGSMITH_AGENT_*` env vars.

        Reads `LANGSMITH_AGENT_ID` and `LANGSMITH_AGENT_ENVIRONMENT`, and
        returns `None` if neither is set.

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
            return cls(*values.values())  # type: ignore[arg-type]
        except utils.LangSmithUserError as e:
            present = ", ".join(
                f"{name}={value!r}" for name, value in values.items() if value
            )
            raise EnvAddressError(
                f"The LANGSMITH_AGENT_* env vars can't address a run ({present}): {e}"
            ) from e


def check(address: Any) -> Agent:
    """Validate an `Address` and return it as an `Agent`.

    The one place an address is checked and normalized; the SDK carries the
    result, and renders its LRN only where it goes on the wire. An LRN string
    is not an address.

    Raises:
        LangSmithUserError: If `address` is not an `Address` that renders a
            valid agent LRN.
    """
    if isinstance(address, Agent):
        return address
    if isinstance(address, str) or not isinstance(address, Address):
        raise utils.LangSmithUserError(
            "An address must be an `Address` such as `ls.Agent(id, env)`, "
            f"got {address!r}."
        )
    return Agent.parse(address.lrn())


def env_values() -> dict[str, Optional[str]]:
    """Return each `LANGSMITH_AGENT_*` env var an address reads, with its value."""
    return {
        f"LANGSMITH_{name}": utils.get_env_var(name, namespaces=("LANGSMITH",))
        for name in ("AGENT_ID", "AGENT_ENVIRONMENT")
    }
