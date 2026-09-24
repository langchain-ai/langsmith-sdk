"""A handle that names where runs are sent.

!!! warning "Experimental"
    Addressing runs to a target is in beta and enabled per workspace. A
    workspace without it rejects the runs, so tracing is lost rather than
    falling back to a project. This API may change without notice.

The handle is propagated whole -- through context variables, run trees,
replicas and distributed-tracing headers -- and only unpacked into wire fields
where a run or feedback is serialized. Every dimension is a dataclass field
whose `wire` metadata names its payload key; the env var, header and payload
handling below are derived from the fields, so a new dimension is a new field.

Example:
    ```python
    import langsmith as ls

    support = ls.target("customer-support", agent_environment="production")


    @support.traceable
    def handle(order): ...


    with support.with_agent_environment("staging").tracing_context():
        handle(order)
    ```
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from contextlib import AbstractContextManager
from typing import TYPE_CHECKING, Any, Callable, Optional

from langsmith import utils

if TYPE_CHECKING:
    # Imported lazily below: the tracing modules import this one.
    from langsmith import run_helpers
    from langsmith.run_trees import WriteReplica

_MAX_ID_LENGTH = 255


class EnvTargetError(utils.LangSmithUserError):
    """The `LANGSMITH_AGENT_*` / project env vars can't address a run.

    Raised for half a target, or a target beside a project. Tracing entry
    points catch it, log it and leave the call untraced, so a bad environment
    never breaks the code being traced.
    """


def _wire(name: str, *, required: bool) -> dict[str, Any]:
    return {"wire": name, "required": required}


@dataclasses.dataclass(frozen=True)
class Target:
    """(experimental) A destination that runs can be addressed to.

    Build one with `langsmith.target`. Required fields must be set at
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
                    f"Target {f.name} must be a non-empty string, got {value!r}."
                )
        if len(self.agent_id) > _MAX_ID_LENGTH:
            raise utils.LangSmithUserError(
                f"Target agent_id must be at most {_MAX_ID_LENGTH} characters."
            )

    # -- Generic over the fields: the only code that knows what a target holds.

    @classmethod
    def wire_keys(cls) -> tuple[str, ...]:
        """Return the payload keys a target renders to."""
        return tuple(f.metadata["wire"] for f in dataclasses.fields(cls))

    def to_wire(self) -> dict[str, str]:
        """Render as run / feedback payload fields, omitting unset ones."""
        return {
            f.metadata["wire"]: value
            for f in dataclasses.fields(self)
            if (value := getattr(self, f.name)) is not None
        }

    @classmethod
    def from_wire(cls, values: Mapping[str, Any]) -> Optional[Target]:
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
                f"A target needs {' and '.join(missing)} as well."
            )
        return cls(**fields)  # type: ignore[arg-type]

    @classmethod
    def from_env(cls) -> Optional[Target]:
        """Read the target named by `LANGSMITH_AGENT_*` env vars, if any.

        Raises:
            EnvTargetError: If only some of the required ones are set.
        """
        try:
            return cls.from_wire(
                {
                    f.metadata["wire"]: _env_value(f.name)
                    for f in dataclasses.fields(cls)
                }
            )
        except EnvTargetError:
            raise
        except utils.LangSmithUserError as e:
            present = ", ".join(
                f"{name}={value!r}" for name, value in cls.env_values().items() if value
            )
            raise EnvTargetError(
                f"The LANGSMITH_AGENT_* env vars name an incomplete target "
                f"({present}): {e}"
            ) from e

    @classmethod
    def env_values(cls) -> dict[str, Optional[str]]:
        """Return each `LANGSMITH_AGENT_*` env var a target reads, with its value."""
        return {_env_name(f.name): _env_value(f.name) for f in dataclasses.fields(cls)}

    def seed(self) -> str:
        """Identify this destination for deterministic replica run ids."""
        return "/".join(["agent", *self.to_wire().values()])

    # -- Sugar.

    def with_agent_environment(self, agent_environment: str) -> Target:
        """Return a handle to the same agent in another environment."""
        return dataclasses.replace(self, agent_environment=agent_environment)

    def _with_address(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        named = [k for k in ("target", "project_name") if k in kwargs]
        if named:
            raise utils.LangSmithUserError(
                f"A Target already addresses the run; drop {named}, or use "
                "another one (e.g. `target.with_agent_environment(...)`) to change it."
            )
        return {**kwargs, "target": self}

    def traceable(self, func: Optional[Callable] = None, /, **kwargs: Any) -> Any:
        """`langsmith.traceable`, addressed to this target.

        Usable bare (`@support.traceable`) or with arguments
        (`@support.traceable(run_type="llm")`). Binds at decorator time, so an
        enclosing `tracing_context` still wins, as with `project_name`.
        """
        from langsmith import run_helpers

        kwargs = self._with_address(kwargs)
        if func is None:
            return run_helpers.traceable(**kwargs)
        return run_helpers.traceable(**kwargs)(func)

    def trace(
        self, name: str, run_type: Any = "chain", **kwargs: Any
    ) -> run_helpers.trace:
        """`langsmith.trace`, addressed to this target."""
        from langsmith import run_helpers

        return run_helpers.trace(name, run_type, **self._with_address(kwargs))

    def tracing_context(self, **kwargs: Any) -> AbstractContextManager[None]:
        """`langsmith.tracing_context`, addressed to this target.

        Sets the context variables, so it beats an `@traceable` binding inside
        it. Like any address, it can't move a child of a run already in flight.
        """
        from langsmith import run_helpers

        return run_helpers.tracing_context(**self._with_address(kwargs))

    def replica(self, **kwargs: Any) -> WriteReplica:
        """Build a `WriteReplica` that sends runs to this target.

        Only needed to set other replica fields; the handle itself can be
        passed in `replicas`.
        """
        return self._with_address(kwargs)  # type: ignore[return-value]


def _env_name(field_name: str) -> str:
    return f"LANGSMITH_{field_name.upper()}"


def _env_value(field_name: str) -> Optional[str]:
    return utils.get_env_var(field_name.upper(), namespaces=("LANGSMITH",))


def target(
    agent_id: str, *, agent_environment: str, **dimensions: Optional[str]
) -> Target:
    """(experimental) Build a handle that addresses runs to a target.

    Args:
        agent_id: The agent's ID. The server creates it on first use.
        agent_environment: The agent's environment. Not validated
            client-side; the server decides which environments are accepted.
        **dimensions: Any further `Target` fields.

    Raises:
        LangSmithUserError: If a value is invalid.
    """
    return Target(agent_id, agent_environment, **dimensions)
