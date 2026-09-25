"""Fan-out: write replicas send one run to several addresses, or projects."""

import langsmith as ls

support = ls.address("customer-support", agent_environment="production")


@ls.traceable
def answer(question: str) -> str:
    """Echo the question; names no destination of its own."""
    return f"echo: {question}"


with ls.tracing_context(
    replicas=[
        support,  # a bare Address is a replica
        support.with_agent_environment("staging").replica(
            updates={"metadata": {"mirrored": True}}
        ),
        {"project_name": "audit-log"},  # projects still work
    ]
):
    answer("hello")  # written three times
