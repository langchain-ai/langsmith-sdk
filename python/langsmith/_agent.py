"""A handle that addresses runs to an agent environment.

!!! warning "Experimental"
    Agent addressing is in beta and enabled per workspace. A workspace without
    it rejects the runs, so tracing is lost rather than falling back to a
    project. This API may change without notice.

The handle holds `(agent_id, environment)` as one value, so an address can't be
set half-way. It renders onto the existing `agent_id` / `agent_environment`
parameters and takes the same place in the resolution chain they do.

Example:
    ```python
    import langsmith as ls

    support = ls.agent("customer-support", environment="production")


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

_MAX_AGENT_ID_LENGTH = 255
_ADDRESSING_KWARGS = ("agent", "project_name", "agent_id", "agent_environment")


@dataclasses.dataclass(frozen=True)
class Agent:
    """(experimental) An agent environment that runs can be addressed to.

    Build one with `langsmith.agent`. Both values are required at construction;
    which environments exist is left to the server.
    """

    id: str
    """The agent's immutable ID, as used by the rest of the Agent API."""
    environment: str
    """The agent environment, passed to the server as given."""

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not (
            0 < len(self.id) <= _MAX_AGENT_ID_LENGTH
        ):
            raise utils.LangSmithUserError(
                f"Agent id must be a string of 1 to {_MAX_AGENT_ID_LENGTH} "
                f"characters, got {self.id!r}."
            )
        if not isinstance(self.environment, str) or not self.environment:
            raise utils.LangSmithUserError(
                f"Agent environment must be a non-empty string, got "
                f"{self.environment!r}."
            )

    def with_environment(self, environment: str) -> Agent:
        """Return a handle to the same agent in another environment."""
        return dataclasses.replace(self, environment=environment)

    def _with_address(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        named = [k for k in _ADDRESSING_KWARGS if k in kwargs]
        if named:
            raise utils.LangSmithUserError(
                f"An Agent handle already addresses the run; drop {named}, or "
                "use another handle (e.g. `agent.with_environment(...)`) to change it."
            )
        return {**kwargs, "agent": self}

    def traceable(self, func: Optional[Callable] = None, /, **kwargs: Any) -> Any:
        """`langsmith.traceable`, addressed to this agent environment.

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
        """`langsmith.trace`, addressed to this agent environment."""
        from langsmith import run_helpers

        return run_helpers.trace(name, run_type, **self._with_address(kwargs))

    def tracing_context(self, **kwargs: Any) -> AbstractContextManager[None]:
        """`langsmith.tracing_context`, addressed to this agent environment.

        Sets the context variables, so it beats an `@traceable` binding inside
        it. Like any address, it can't move a child of a run already in flight.
        """
        from langsmith import run_helpers

        return run_helpers.tracing_context(**self._with_address(kwargs))

    def replica(self, **kwargs: Any) -> WriteReplica:
        """Build a `WriteReplica` that sends runs to this agent environment.

        Only needed to set other replica fields; the handle itself can be
        passed in `replicas`.
        """
        self._with_address(kwargs)
        return {**kwargs, **self._replica()}  # type: ignore[typeddict-item]

    def _replica(self) -> WriteReplica:
        return {"agent_id": self.id, "agent_environment": self.environment}


def agent(agent_id: str, *, environment: str) -> Agent:
    """(experimental) Build a handle that addresses runs to an agent environment.

    Args:
        agent_id: The agent's ID. The server creates the agent on first use.
        environment: The agent environment. Not validated client-side; the
            server decides which environments are accepted.

    Raises:
        LangSmithUserError: If either value is invalid.
    """
    return Agent(agent_id, environment)
