"""A handle that names where runs are sent.

!!! warning "Experimental"
    Addressing runs to a target is in beta and enabled per workspace. A
    workspace without it rejects the runs, so tracing is lost rather than
    falling back to a project. This API may change without notice.

The handle holds `(id, environment)` as one value, so an address can't be set
half-way. It renders onto the existing `agent_id` / `agent_environment`
parameters and takes the same place in the resolution chain they do.

Example:
    ```python
    import langsmith as ls

    support = ls.target("customer-support", environment="production")


    @support.traceable
    def handle(order): ...


    with support.with_environment("staging").tracing_context():
        handle(order)
    ```
"""

from __future__ import annotations

import dataclasses
from contextlib import AbstractContextManager
from typing import TYPE_CHECKING, Any, Callable, Optional

from langsmith import utils

if TYPE_CHECKING:
    # Imported lazily below: the tracing modules import this one.
    from langsmith import run_helpers
    from langsmith.run_trees import WriteReplica

_MAX_ID_LENGTH = 255
_ADDRESSING_KWARGS = ("target", "project_name", "agent_id", "agent_environment")


@dataclasses.dataclass(frozen=True)
class Target:
    """(experimental) A destination that runs can be addressed to.

    Build one with `langsmith.target`. Both values are required at
    construction; which environments exist is left to the server.
    """

    id: str
    """The target's immutable ID."""
    environment: str
    """The target's environment, passed to the server as given."""

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not (0 < len(self.id) <= _MAX_ID_LENGTH):
            raise utils.LangSmithUserError(
                f"Target id must be a string of 1 to {_MAX_ID_LENGTH} "
                f"characters, got {self.id!r}."
            )
        if not isinstance(self.environment, str) or not self.environment:
            raise utils.LangSmithUserError(
                f"Target environment must be a non-empty string, got "
                f"{self.environment!r}."
            )

    def with_environment(self, environment: str) -> Target:
        """Return a handle to the same target in another environment."""
        return dataclasses.replace(self, environment=environment)

    def _with_address(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        named = [k for k in _ADDRESSING_KWARGS if k in kwargs]
        if named:
            raise utils.LangSmithUserError(
                f"A Target already addresses the run; drop {named}, or use "
                "another one (e.g. `target.with_environment(...)`) to change it."
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
        self._with_address(kwargs)
        return {**kwargs, **self._replica()}  # type: ignore[typeddict-item]

    def _replica(self) -> WriteReplica:
        return {"agent_id": self.id, "agent_environment": self.environment}


def target(id: str, *, environment: str) -> Target:
    """(experimental) Build a handle that addresses runs to a target.

    Args:
        id: The target's ID. The server creates it on first use.
        environment: The target's environment. Not validated client-side; the
            server decides which environments are accepted.

    Raises:
        LangSmithUserError: If either value is invalid.
    """
    return Target(id, environment)
