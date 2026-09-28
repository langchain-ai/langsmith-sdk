"""A handle that names where runs are sent.

!!! warning "Beta"
    Addressing runs to an address is enabled per workspace. A workspace
    without it rejects the runs, so tracing is lost rather than falling back
    to a project. This API may change without notice.

The handle is propagated whole -- through context variables, run trees,
replicas and distributed-tracing headers -- and only unpacked into wire fields
where a run or feedback is serialized. Every dimension is a dataclass field
whose `wire` metadata names its payload key; the env var, header and payload
handling below are derived from the fields, so a new dimension is a new field.

Example:
    ```python
    import langsmith as ls

    support = ls.address(
        agent_id="customer-support", agent_environment="production"
    )


    @ls.traceable(address=support)
    def handle(order): ...


    with ls.tracing_context(address=support.with_agent_environment("staging")):
        handle(order)
    ```
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping
from typing import Any, Optional

from langsmith import utils

# The server's agent id rule: a DNS label, so a hostname can carry the id.
_AGENT_ID_PATTERN = re.compile(r"[a-z]([a-z0-9-]{0,61}[a-z0-9])?")


class EnvAddressError(utils.LangSmithUserError):
    """The `LANGSMITH_AGENT_*` / project env vars can't address a run.

    Raised for half an address, or an address beside a project. Tracing entry
    points (`@traceable`, `trace`, `tracing_context`, `create_run`) catch it,
    log it and leave the call untraced, so a bad environment never breaks the
    code being traced. Explicit ingestion calls (`batch_ingest_runs`,
    `multipart_ingest`) let it raise for runs that name no destination, rather
    than drop part of a batch the caller built.
    """


def _wire(name: str, *, required: bool) -> dict[str, Any]:
    return {"wire": name, "required": required}


@dataclasses.dataclass(frozen=True, kw_only=True)
class Address:
    """(beta) A destination that runs can be addressed to.

    Build one with `langsmith.address`. Required fields must be set at
    construction; which values exist is left to the server.
    """

    agent_id: str = dataclasses.field(metadata=_wire("agent_id", required=True))
    """The agent's immutable ID."""
    agent_environment: str = dataclasses.field(
        metadata=_wire("agent_environment", required=True)
    )
    """The agent's environment, passed to the server as given."""

    def __post_init__(self) -> None:
        for f in dataclasses.fields(self):
            value = getattr(self, f.name)
            if value is None and not f.metadata["required"]:
                continue
            if not isinstance(value, str) or not value:
                raise utils.LangSmithUserError(
                    f"Address {f.name} must be a non-empty string, got {value!r}."
                )
        _validate_agent_id(self.agent_id)

    # -- Generic over the fields: the only code that knows what an address holds.

    @classmethod
    def _wire_keys(cls) -> tuple[str, ...]:
        """Return the payload keys an address renders to."""
        return tuple(f.metadata["wire"] for f in dataclasses.fields(cls))

    def _to_wire(self) -> dict[str, str]:
        """Render as run / feedback payload fields, omitting unset ones."""
        return {
            f.metadata["wire"]: value
            for f in dataclasses.fields(self)
            if (value := getattr(self, f.name)) is not None
        }

    @classmethod
    def _from_wire(cls, values: Mapping[str, Any]) -> Optional[Address]:
        """Build from payload-keyed values, or `None` if none are set.

        Raises:
            LangSmithUserError: If some but not all required fields are set.
        """
        fields = {
            f.name: values.get(f.metadata["wire"]) for f in dataclasses.fields(cls)
        }
        if all(v is None for v in fields.values()):
            return None
        missing = [
            f.metadata["wire"]
            for f in dataclasses.fields(cls)
            if f.metadata["required"] and fields[f.name] is None
        ]
        if missing:
            raise utils.LangSmithUserError(
                f"An address needs {' and '.join(missing)} as well."
            )
        return cls(**fields)  # type: ignore[arg-type]

    @classmethod
    def _from_env(cls) -> Optional[Address]:
        """Read the address named by `LANGSMITH_AGENT_*` env vars, if any.

        Raises:
            EnvAddressError: If only some of the required ones are set, or a
                value is invalid.
        """
        try:
            return cls._from_wire(
                {
                    f.metadata["wire"]: _env_value(f.name)
                    for f in dataclasses.fields(cls)
                }
            )
        except EnvAddressError:
            raise
        except utils.LangSmithUserError as e:
            present = ", ".join(
                f"{name}={value!r}"
                for name, value in cls._env_values().items()
                if value
            )
            raise EnvAddressError(
                f"The LANGSMITH_AGENT_* env vars can't address a run ({present}): {e}"
            ) from e

    @classmethod
    def _env_values(cls) -> dict[str, Optional[str]]:
        """Return each `LANGSMITH_AGENT_*` env var an address reads, with its value."""
        return {_env_name(f.name): _env_value(f.name) for f in dataclasses.fields(cls)}

    def _seed(self) -> str:
        """Identify this destination for deterministic replica run ids."""
        return "/".join(["agent", *self._to_wire().values()])

    def with_agent_environment(self, agent_environment: str) -> Address:
        """Return a handle to the same agent in another environment."""
        return dataclasses.replace(self, agent_environment=agent_environment)


def _validate_agent_id(agent_id: str) -> None:
    """Raise unless `agent_id` is one the server accepts.

    Raises:
        LangSmithUserError: If `agent_id` is not 1 to 63 lowercase ASCII
            letters, digits or hyphens, starting with a letter and ending with
            a letter or digit.
    """
    if not _AGENT_ID_PATTERN.fullmatch(agent_id):
        raise utils.LangSmithUserError(
            f"Address agent_id must be 1 to 63 lowercase ASCII letters, digits, "
            f"or hyphens, start with a letter, and end with a letter or digit, "
            f"got {agent_id!r}. Use an id such as 'support-agent'."
        )


def _env_name(field_name: str) -> str:
    return f"LANGSMITH_{field_name.upper()}"


def _env_value(field_name: str) -> Optional[str]:
    return utils.get_env_var(field_name.upper(), namespaces=("LANGSMITH",))


def address(*, agent_id: str, agent_environment: str) -> Address:
    """(beta) Build an address to send runs to.

    Args:
        agent_id: The agent's ID: 1 to 63 lowercase ASCII letters, digits or
            hyphens, starting with a letter and ending with a letter or digit.
            The server creates the agent on first use.
        agent_environment: The agent's environment. Not validated
            client-side; the server decides which environments are accepted.

    Raises:
        LangSmithUserError: If a value is invalid.
    """
    return Address(agent_id=agent_id, agent_environment=agent_environment)
