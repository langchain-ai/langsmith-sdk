"""Inherit: below the root, the address is copied, never re-resolved."""

import langsmith as ls
from langsmith.run_trees import RunTree

support = ls.address(agent_id="customer-support", agent_environment="production")


@ls.traceable
def answer(question: str) -> str:
    """Echo the question; names no destination of its own."""
    return f"echo: {question}"


@support.traceable
def root() -> None:
    """Start a trace, then try to move a child elsewhere."""
    with support.with_agent_environment("staging").tracing_context():
        answer("child")  # still customer-support / production


root()

# Built by hand, a child copies its parent's address too.
parent = RunTree(name="manual", address=support)
child = parent.create_child(name="step")
assert child.address == support
