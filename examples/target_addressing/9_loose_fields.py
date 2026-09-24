"""Loose fields: `agent_id` / `agent_environment` are folded into a Target.

A missing half is read from its env var; one still missing raises here
instead of failing at ingest.
"""

import langsmith as ls


@ls.traceable
def answer(question: str) -> str:
    """Echo the question; names no destination of its own."""
    return f"echo: {question}"


with ls.tracing_context(agent_id="customer-support", agent_environment="dev"):
    answer("hello")  # same as target=ls.target("customer-support", ...)
