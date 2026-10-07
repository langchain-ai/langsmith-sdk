"""Addresses that name features that hold traces in a tracing project.

!!! warning "Beta"
    Addressing runs to an agent is enabled per workspace. A workspace without
    it rejects the runs, so tracing is lost rather than falling back to a
    project. This API may change without notice.

An `Address` names the tracing project of a feature: an `Agent`'s environment,
an `Experiment`, or the workspace's `Evaluator` traces. Query APIs resolve an
address to its project (`client.sessions.resolve`). Only an `Agent` can receive
traces, so tracing entry points take an `Agent`, and anything else is rejected.
The environment of an agent is one of `local`, `development`, `staging` or
`production`, and is always lowercase.

Example:
    ```python
    import langsmith as ls

    support = ls.Agent(id="customer-support", environment="production")


    @ls.traceable(address=support)
    def handle(order): ...


    with ls.tracing_context(address=ls.Agent("customer-support", "staging")):
        handle(order)
    ```
"""

from __future__ import annotations

import dataclasses
import re
from typing import Any, Optional, Protocol, cast, runtime_checkable

from typing_extensions import Literal, Required, TypedDict

from langsmith import utils

__all__ = [
    "Address",
    "Agent",
    "ApiAddress",
    "Evaluator",
    "EnvAddressError",
    "Experiment",
]

# The server's agent id rule: a DNS label, so a hostname can carry the id.
_AGENT_ID_PATTERN = re.compile(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?")
_ENVIRONMENTS = ("local", "development", "staging", "production")
# The canonical, hyphenated UUID. Other spellings of one are not accepted, so the
# Python and JS SDKs take the same experiment ids.
_UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)
# The wire form of an agent address. The parts are validated by `Agent`.
_LRN_PATTERN = re.compile(r"lrn:agents/([^/]+)/environments/([^/]+)")


class ApiAddress(TypedDict, total=False):
    """(beta) An address as `client.sessions.resolve` takes it."""

    kind: Required[Literal["AGENT", "EXPERIMENT", "EVALUATOR"]]
    id: str
    environment: Literal["LOCAL", "DEVELOPMENT", "STAGING", "PRODUCTION"]


@runtime_checkable
class Address(Protocol):
    """(beta) Names the tracing project of a feature, such as an agent."""

    def to_api_address(self) -> ApiAddress:
        """Return the address as the query APIs take it."""
        ...


class EnvAddressError(utils.LangSmithUserError):
    """(beta) The `LANGSMITH_AGENT_*` / project env vars can't address a run.

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
        environment: One of `local`, `development`, `staging` or `production`, in any
            case.

    Raises:
        LangSmithUserError: If a value is invalid.
    """

    id: str
    environment: str

    def __post_init__(self) -> None:
        """Validate the fields and lowercase the environment."""
        if not isinstance(self.id, str) or not _AGENT_ID_PATTERN.fullmatch(self.id):
            raise utils.LangSmithUserError(
                "Address agent id must be 1 to 63 lowercase ASCII letters, digits, "
                "or hyphens, start with a letter, and end with a letter or digit, "
                f"got {self.id!r}. Use an id such as 'support-agent'."
            )
        environment = (
            self.environment.lower() if isinstance(self.environment, str) else None
        )
        if environment not in _ENVIRONMENTS:
            raise utils.LangSmithUserError(
                f"Address environment must be one of {', '.join(_ENVIRONMENTS)}, "
                f"got {self.environment!r}."
            )
        object.__setattr__(self, "environment", environment)

    def _lrn(self) -> str:
        """Return `lrn:agents/{id}/environments/{environment}`. Wire format only."""
        return f"lrn:agents/{self.id}/environments/{self.environment}"

    @classmethod
    def _from_lrn(cls, value: Any) -> Agent:
        """Parse an LRN read from the wire, such as a `baggage` header.

        The value is untrusted, so it is not echoed in the error.

        Raises:
            LangSmithUserError: If `value` is not an agent LRN, or names an
                invalid id or environment.
        """
        match = _LRN_PATTERN.fullmatch(value) if isinstance(value, str) else None
        if match is None:
            raise utils.LangSmithUserError("Not an agent address.")
        return cls(*match.groups())

    def to_api_address(self) -> ApiAddress:
        """Return this agent as the address the query APIs take."""
        return cast(
            "ApiAddress",
            {"kind": "AGENT", "id": self.id, "environment": self.environment.upper()},
        )

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


@dataclasses.dataclass(frozen=True)
class Experiment:
    """(beta) The tracing project of an experiment, by its id.

    Query APIs take it; it cannot be sent traces.

    Args:
        id: The experiment's UUID.

    Raises:
        LangSmithUserError: If `id` is not a UUID.
    """

    id: str

    def __post_init__(self) -> None:
        """Validate the id and lowercase it."""
        if not isinstance(self.id, str) or not _UUID_PATTERN.fullmatch(self.id):
            raise utils.LangSmithUserError(
                "An experiment id must be a UUID with hyphens, such as "
                f"'0190c3d4-0000-7000-8000-0000000000b1', got {self.id!r}."
            )
        object.__setattr__(self, "id", self.id.lower())

    def to_api_address(self) -> ApiAddress:
        """Return this experiment as the address the query APIs take."""
        return cast("ApiAddress", {"kind": "EXPERIMENT", "id": self.id})


@dataclasses.dataclass(frozen=True)
class Evaluator:
    """(beta) The tracing project of the workspace's evaluators.

    Evaluator traces share one project per workspace. Query APIs take it; it
    cannot be sent traces.
    """

    def to_api_address(self) -> ApiAddress:
        """Return the address the query APIs take."""
        return cast("ApiAddress", {"kind": "EVALUATOR"})


def ensure_agent(address: Any) -> Agent:
    """Return `address` if it is an `Agent`: the only address that takes traces.

    The one place an address given to a tracing entry point is checked; the SDK
    then carries it as is. A string is not an address.

    Raises:
        LangSmithUserError: If `address` is not an `Agent`.
    """
    if isinstance(address, Agent):
        return address
    if isinstance(address, Address) and not isinstance(address, str):
        raise utils.LangSmithUserError(
            f"Only an `Agent` can receive traces, got {address!r}."
        )
    raise utils.LangSmithUserError(
        "An address must be an `Agent` such as `ls.Agent(id, environment)`, "
        f"got {address!r}."
    )


def env_values() -> dict[str, Optional[str]]:
    """Return each `LANGSMITH_AGENT_*` env var an address reads, with its value."""
    return {
        f"LANGSMITH_{name}": utils.get_env_var(name, namespaces=("LANGSMITH",))
        for name in ("AGENT_ID", "AGENT_ENVIRONMENT")
    }
