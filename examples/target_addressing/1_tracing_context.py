"""1 · tracing_context: ambient, wins over every tier below.

Sets the context variable, so it beats `langsmith_extra`, the decorator,
`configure` and the env vars for every root run started inside it.
"""

import langsmith as ls

staging = ls.target("customer-support", agent_environment="staging")


@ls.traceable
def answer(question: str) -> str:
    """Echo the question; names no destination of its own."""
    return f"echo: {question}"


with ls.tracing_context(target=staging):
    answer("hello")  # -> customer-support / staging

# Same thing, from the handle.
with staging.tracing_context():
    answer("hello")  # -> customer-support / staging
